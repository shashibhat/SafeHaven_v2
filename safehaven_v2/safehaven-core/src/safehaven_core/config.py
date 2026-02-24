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

    return AppConfig(
        frigate_base_url=os.getenv("FRIGATE_BASE_URL", "http://frigate:5000"),
        metis_detector_url=os.getenv("METIS_DETECTOR_URL", "http://metis-detector:8090/detect"),
        mqtt_broker=os.getenv("MQTT_BROKER", yaml_data.get("mqtt_broker")),
        sample_fps=float(os.getenv("SAMPLE_FPS", yaml_data.get("sample_fps", 1))),
        left_open_minutes=int(os.getenv("LEFT_OPEN_MINUTES", yaml_data.get("left_open_minutes", 7))),
        queue_max=int(os.getenv("QUEUE_MAX", yaml_data.get("queue_max", 50))),
        metrics_port=int(os.getenv("METRICS_PORT", yaml_data.get("metrics_port", 9108))),
        cameras=cameras,
    )
