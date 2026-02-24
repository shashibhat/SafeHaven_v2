import dataclasses
from typing import Any

import cv2
import numpy as np
import requests
from pydantic import Field
from typing_extensions import Literal

try:
    from frigate.detectors.detection_api import DetectionApi
    from frigate.detectors.detector_config import BaseDetectorConfig
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "This plugin must run inside a Frigate runtime where detector classes are available"
    ) from exc


DETECTOR_KEY = "metis"


@dataclasses.dataclass(frozen=True)
class MetisDetectorConfig(BaseDetectorConfig):
    type: Literal[DETECTOR_KEY]
    endpoint: str = Field(default="http://metis-detector:8090/detect", title="HTTP endpoint for Metis detector")
    timeout_ms: int = Field(default=100, title="HTTP timeout in milliseconds")


class MetisDetector(DetectionApi):
    type_key = DETECTOR_KEY

    def __init__(self, detector_config: MetisDetectorConfig):
        self.detector_config = detector_config

    def detect_raw(self, tensor_input: np.ndarray):
        # Frigate typically passes CHW or HWC uint8. Normalize to HWC for JPEG encoding.
        frame = tensor_input
        if frame.ndim == 3 and frame.shape[0] in (1, 3, 4) and frame.shape[0] < frame.shape[-1]:
            frame = np.transpose(frame, (1, 2, 0))
        frame = np.ascontiguousarray(frame)

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return np.empty((0, 6), dtype=np.float32)

        try:
            resp = requests.post(
                self.detector_config.endpoint,
                data=encoded.tobytes(),
                headers={"Content-Type": "image/jpeg"},
                timeout=self.detector_config.timeout_ms / 1000.0,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException:
            return np.empty((0, 6), dtype=np.float32)

        if not isinstance(payload, list):
            return np.empty((0, 6), dtype=np.float32)

        rows: list[list[float]] = []
        for det in payload:
            if isinstance(det, list) and len(det) >= 6:
                rows.append([
                    float(det[0]),
                    float(det[1]),
                    float(det[2]),
                    float(det[3]),
                    float(det[4]),
                    float(det[5]),
                ])

        if not rows:
            return np.empty((0, 6), dtype=np.float32)
        return np.asarray(rows, dtype=np.float32)
