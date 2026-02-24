import datetime
import json
import logging
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

import cv2
import numpy as np
import requests

from .config import AppConfig, CameraConfig, load_config
from .frigate_api import FrigateApi
from .metrics import DROPPED_SAMPLES, E2E_MS, INFER_MS, QUEUE_DEPTH, SEMANTIC_EVENTS, start_metrics_server
from .rtsp_sampler import crop_roi, sample_stream
from .state_machines import DebouncedStateMachine, ZoneState

LOGGER = logging.getLogger(__name__)


ZONE_SPECS = {
    "garage": {
        "open_event": "garage_opened",
        "close_event": "garage_closed",
        "left_open_event": "garage_left_open",
    },
    "gate": {
        "open_event": "gate_ajar",
        "close_event": "gate_closed",
        "left_open_event": "gate_left_open",
    },
    "latch": {
        "open_event": "latch_unlocked",
        "close_event": "latch_locked",
        "left_open_event": "latch_left_open",
    },
}


@dataclass
class CameraRuntime:
    camera: CameraConfig
    queue: queue.Queue


@dataclass
class ReadinessState:
    ready: bool = False
    details: dict[str, bool] = field(default_factory=dict)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "thread": record.threadName,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def _setup_logging(log_level: str, log_format: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def _metis_health_url(detect_url: str) -> str:
    parsed = urlsplit(detect_url)
    path = parsed.path
    if path.endswith("/detect"):
        path = f"{path.rsplit('/', 1)[0]}/healthz"
    else:
        path = "/healthz"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _is_http_up(url: str, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except requests.RequestException:
        return False


def _start_health_server(port: int, readiness: ReadinessState) -> None:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/healthz":
                self._send(200, {"ok": True})
                return
            if self.path == "/readyz":
                status = 200 if readiness.ready else 503
                self._send(status, {"ready": readiness.ready, "dependencies": readiness.details})
                return
            self._send(404, {"error": "not found"})

        def _send(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="health-server").start()


def _start_dependency_probe(config: AppConfig, readiness: ReadinessState) -> None:
    def _probe_loop() -> None:
        frigate_url = f"{config.frigate_base_url.rstrip('/')}/api/version"
        metis_url = _metis_health_url(config.metis_detector_url)
        while True:
            frigate_ok = _is_http_up(frigate_url)
            metis_ok = _is_http_up(metis_url)
            readiness.details = {"frigate": frigate_ok, "metis_detector": metis_ok}
            readiness.ready = frigate_ok and metis_ok
            time.sleep(5)

    threading.Thread(target=_probe_loop, daemon=True, name="dependency-probe").start()


def _default_zone_class_ids() -> dict[str, dict[str, int]]:
    return {
        "garage": {"open": 0, "closed": 1},
        "gate": {"open": 2, "closed": 3},
        "latch": {"open": 4, "closed": 5},
    }


def _jpg_bytes(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Failed to JPEG encode frame")
    return encoded.tobytes()


def _call_metis(metis_url: str, roi_frame: np.ndarray, timeout: float = 1.0) -> list[list[float]]:
    payload = _jpg_bytes(roi_frame)
    start = time.time()
    resp = requests.post(
        metis_url,
        data=payload,
        headers={"Content-Type": "image/jpeg"},
        timeout=timeout,
    )
    elapsed_ms = (time.time() - start) * 1000.0
    INFER_MS.observe(elapsed_ms)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    return data


def _zone_state_from_detections(
    detections: list[list[float]],
    class_ids: dict[str, int],
    conf_threshold: float = 0.5,
) -> tuple[ZoneState, float]:
    best_open = 0.0
    best_closed = 0.0
    open_cls = class_ids["open"]
    closed_cls = class_ids["closed"]
    for det in detections:
        if len(det) < 6:
            continue
        cls_id = int(det[0])
        score = float(det[1])
        if cls_id == open_cls:
            best_open = max(best_open, score)
        elif cls_id == closed_cls:
            best_closed = max(best_closed, score)

    if best_open < conf_threshold and best_closed < conf_threshold:
        return ZoneState.UNKNOWN, 0.0
    if best_open >= best_closed:
        return ZoneState.OPEN, best_open
    return ZoneState.CLOSED, best_closed


def _put_latest(camera_runtime: CameraRuntime, frame: np.ndarray, ts: float) -> None:
    q = camera_runtime.queue
    dropped = 0
    while q.full():
        try:
            q.get_nowait()
            dropped += 1
        except queue.Empty:
            break
    if dropped:
        DROPPED_SAMPLES.labels(camera=camera_runtime.camera.name).inc(dropped)
    q.put_nowait((frame, ts))
    QUEUE_DEPTH.labels(camera=camera_runtime.camera.name).set(q.qsize())


def _sampler_worker(camera_runtime: CameraRuntime, sample_fps: float) -> None:
    camera = camera_runtime.camera
    for frame, ts in sample_stream(camera.stream_url, sample_fps):
        _put_latest(camera_runtime, frame, ts)


def _emit_event(
    frigate: FrigateApi,
    camera_name: str,
    label: str,
    score: float,
    duration: int,
    extra: str,
) -> None:
    SEMANTIC_EVENTS.labels(camera=camera_name, type=label).inc()
    sub_label = f"{extra} conf={score:.2f} source=metis"
    frigate.create_event(camera=camera_name, label=label, sub_label=sub_label, score=score, duration=duration)


def _camera_worker(config: AppConfig, camera_runtime: CameraRuntime, frigate: FrigateApi) -> None:
    camera = camera_runtime.camera
    left_open_seconds = float(config.left_open_minutes) * 60.0
    machines = {
        zone: DebouncedStateMachine(
            zone_name=zone,
            open_state_name="open",
            closed_state_name="closed",
            open_event=ZONE_SPECS[zone]["open_event"],
            close_event=ZONE_SPECS[zone]["close_event"],
            left_open_event=ZONE_SPECS[zone]["left_open_event"],
            left_open_seconds=left_open_seconds,
        )
        for zone in camera.rois.keys()
        if zone in ZONE_SPECS
    }

    class_map = _default_zone_class_ids()

    while True:
        frame, sampled_ts = camera_runtime.queue.get()
        QUEUE_DEPTH.labels(camera=camera.name).set(camera_runtime.queue.qsize())
        now = time.time()

        for zone, roi in camera.rois.items():
            machine = machines.get(zone)
            ids = class_map.get(zone)
            if machine is None or ids is None:
                continue
            try:
                roi_frame = crop_roi(frame, roi)
                detections = _call_metis(config.metis_detector_url, roi_frame)
                observed, score = _zone_state_from_detections(detections, ids)
            except Exception as exc:
                LOGGER.warning("Inference error camera=%s zone=%s err=%s", camera.name, zone, exc)
                observed, score = ZoneState.UNKNOWN, 0.0

            out = machine.update(observed, now)
            if out.transition_event:
                _emit_event(
                    frigate,
                    camera_name=camera.name,
                    label=out.transition_event,
                    score=score,
                    duration=15,
                    extra=f"zone={zone} state={observed.value}",
                )
            if out.left_open_event:
                _emit_event(
                    frigate,
                    camera_name=camera.name,
                    label=out.left_open_event,
                    score=max(0.5, score),
                    duration=30,
                    extra=f"zone={zone} open_for={config.left_open_minutes}m",
                )

        e2e_ms = (time.time() - sampled_ts) * 1000.0
        E2E_MS.observe(e2e_ms)


def run() -> None:
    config = load_config()
    _setup_logging(log_level=config.log_level, log_format=config.log_format)
    readiness = ReadinessState()
    _start_health_server(config.health_port, readiness)
    _start_dependency_probe(config, readiness)
    start_metrics_server(config.metrics_port)
    frigate = FrigateApi(config.frigate_base_url)

    runtimes: list[CameraRuntime] = []
    for camera in config.cameras:
        runtimes.append(CameraRuntime(camera=camera, queue=queue.Queue(maxsize=config.queue_max)))

    for runtime in runtimes:
        threading.Thread(
            target=_sampler_worker,
            args=(runtime, config.sample_fps),
            daemon=True,
            name=f"sampler-{runtime.camera.name}",
        ).start()

    for runtime in runtimes:
        threading.Thread(
            target=_camera_worker,
            args=(config, runtime, frigate),
            daemon=True,
            name=f"worker-{runtime.camera.name}",
        ).start()

    LOGGER.info(
        "safehaven-core started cameras=%s metrics_port=%s health_port=%s log_format=%s pid=%s",
        [c.name for c in config.cameras],
        config.metrics_port,
        config.health_port,
        config.log_format,
        os.getpid(),
    )
    while True:
        time.sleep(1)


if __name__ == "__main__":
    run()
