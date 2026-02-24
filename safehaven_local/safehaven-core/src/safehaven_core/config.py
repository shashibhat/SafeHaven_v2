import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ROI:
    x: float
    y: float
    w: float
    h: float


@dataclass
class CameraConfig:
    name: str
    stream_url: str
    rois: dict[str, ROI]


@dataclass
class AppConfig:
    frigate_base_url: str
    metis_detector_url: str
    mqtt_broker: str | None
    sample_fps: float
    left_open_minutes: int
    queue_max: int
    metrics_port: int
    health_port: int
    log_format: str
    log_level: str
    state_conf_threshold: float
    metis_timeout_s: float
    debug_state_every: int
    emit_boot_event: bool
    evidence_dir: str
    save_event_media: bool
    demo_emit_interval_s: int
    demo_zone: str
    zone_class_map: dict[str, dict[str, int]]
    cameras: list[CameraConfig]


def _parse_roi(raw: dict[str, Any]) -> ROI:
    return ROI(
        x=float(raw.get("x", 0.0)),
        y=float(raw.get("y", 0.0)),
        w=float(raw.get("w", 1.0)),
        h=float(raw.get("h", 1.0)),
    )


def _parse_cameras(raw_cameras: list[dict[str, Any]]) -> list[CameraConfig]:
    cameras: list[CameraConfig] = []
    for item in raw_cameras:
        rois = {k: _parse_roi(v) for k, v in item.get("rois", {}).items()}
        cameras.append(
            CameraConfig(
                name=item["name"],
                stream_url=item["stream_url"],
                rois=rois,
            )
        )
    return cameras


def _parse_zone_class_map(raw: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    default_map = {
        "garage": {"open": 0, "closed": 1},
        "gate": {"open": 2, "closed": 3},
        "latch": {"open": 4, "closed": 5},
    }
    if not raw:
        return default_map
    out: dict[str, dict[str, int]] = {}
    for zone, mapping in raw.items():
        if not isinstance(mapping, dict):
            continue
        if "open" not in mapping or "closed" not in mapping:
            continue
        out[zone] = {"open": int(mapping["open"]), "closed": int(mapping["closed"])}
    return out or default_map


def load_config() -> AppConfig:
    config_path = Path(os.getenv("SAFEHAVEN_CONFIG", "/config/safehaven.yml"))
    yaml_data: dict[str, Any] = {}
    if config_path.exists():
        yaml_data = yaml.safe_load(config_path.read_text()) or {}

    env_cameras = os.getenv("CAMERAS", "").strip()
    if env_cameras:
        raw_cameras = json.loads(env_cameras)
    else:
        raw_cameras = yaml_data.get("cameras", [])

    cameras = _parse_cameras(raw_cameras)
    if not cameras:
        raise ValueError("No cameras configured. Set CAMERAS env or SAFEHAVEN_CONFIG cameras list.")

    env_zone_class_map = os.getenv("ZONE_CLASS_MAP", "").strip()
    if env_zone_class_map:
        raw_zone_class_map = json.loads(env_zone_class_map)
    else:
        raw_zone_class_map = yaml_data.get("zone_class_map")
    zone_class_map = _parse_zone_class_map(raw_zone_class_map)

    return AppConfig(
        frigate_base_url=os.getenv("FRIGATE_BASE_URL", "http://frigate:5000"),
        metis_detector_url=os.getenv("METIS_DETECTOR_URL", "http://metis-detector:8090/detect"),
        mqtt_broker=os.getenv("MQTT_BROKER", yaml_data.get("mqtt_broker")),
        sample_fps=float(os.getenv("SAMPLE_FPS", yaml_data.get("sample_fps", 1))),
        left_open_minutes=int(os.getenv("LEFT_OPEN_MINUTES", yaml_data.get("left_open_minutes", 7))),
        queue_max=int(os.getenv("QUEUE_MAX", yaml_data.get("queue_max", 50))),
        metrics_port=int(os.getenv("METRICS_PORT", yaml_data.get("metrics_port", 9108))),
        health_port=int(os.getenv("HEALTH_PORT", yaml_data.get("health_port", 9109))),
        log_format=str(os.getenv("LOG_FORMAT", yaml_data.get("log_format", "text"))),
        log_level=str(os.getenv("LOG_LEVEL", yaml_data.get("log_level", "INFO"))),
        state_conf_threshold=float(os.getenv("STATE_CONF_THRESHOLD", yaml_data.get("state_conf_threshold", 0.5))),
        metis_timeout_s=float(os.getenv("METIS_TIMEOUT_S", yaml_data.get("metis_timeout_s", 2.5))),
        debug_state_every=int(os.getenv("DEBUG_STATE_EVERY", yaml_data.get("debug_state_every", 0))),
        emit_boot_event=os.getenv("EMIT_BOOT_EVENT", str(yaml_data.get("emit_boot_event", 0))).strip() in ("1", "true", "True"),
        evidence_dir=str(os.getenv("EVIDENCE_DIR", yaml_data.get("evidence_dir", "/tmp/safehaven_evidence"))),
        save_event_media=os.getenv("SAVE_EVENT_MEDIA", str(yaml_data.get("save_event_media", 1))).strip() in ("1", "true", "True"),
        demo_emit_interval_s=int(os.getenv("DEMO_EMIT_INTERVAL_S", yaml_data.get("demo_emit_interval_s", 0))),
        demo_zone=str(os.getenv("DEMO_ZONE", yaml_data.get("demo_zone", "latch"))),
        zone_class_map=zone_class_map,
        cameras=cameras,
    )
