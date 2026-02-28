import io
import logging
from typing import Any

import numpy as np
import requests
from PIL import Image
from pydantic import Field
from typing_extensions import Literal

from frigate.detectors.detection_api import DetectionApi
from frigate.detectors.detector_config import BaseDetectorConfig

logger = logging.getLogger(__name__)

DETECTOR_KEY = "metis"


class MetisDetectorConfig(BaseDetectorConfig):
    type: Literal[DETECTOR_KEY]
    endpoint: str = Field(
        default="http://127.0.0.1:8090/detect", title="Metis HTTP endpoint"
    )
    timeout_ms: int = Field(default=200, title="HTTP timeout in milliseconds")


class MetisDetector(DetectionApi):
    type_key = DETECTOR_KEY

    def __init__(self, detector_config: MetisDetectorConfig):
        super().__init__(detector_config)

        self.endpoint = detector_config.endpoint
        self.timeout = detector_config.timeout_ms / 1000.0
        self.session = requests.Session()
        self._zero_result = np.zeros((20, 6), np.float32)
        self._warned_request_failure = False
        logger.info(
            "metis detector initialized: endpoint=%s timeout_ms=%s",
            self.endpoint,
            detector_config.timeout_ms,
        )

    def _encode_jpeg(self, tensor_input: np.ndarray) -> bytes | None:
        frame = np.squeeze(tensor_input)

        # Frigate can pass CHW or HWC. Normalize to HWC for encoding.
        if frame.ndim == 3 and frame.shape[0] in (1, 3, 4) and frame.shape[0] < frame.shape[-1]:
            frame = np.transpose(frame, (1, 2, 0))

        frame = np.ascontiguousarray(frame)

        if frame.dtype != np.uint8:
            frame = np.clip(frame, 0, 255).astype(np.uint8)

        # Handle common grayscale/alpha cases before JPEG conversion.
        if frame.ndim == 3 and frame.shape[2] == 1:
            frame = frame[:, :, 0]
        elif frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3]

        try:
            image = Image.fromarray(frame)
            with io.BytesIO() as output:
                image.save(output, format="JPEG")
                return output.getvalue()
        except Exception as exc:  # noqa: BLE001
            logger.debug("metis jpeg encoding failed: %s", exc)
            return None

    def _parse_detection(self, value: Any) -> list[float] | None:
        # Metis service contract: [class_id, score, x1, y1, x2, y2] normalized.
        if not isinstance(value, list) or len(value) < 6:
            return None

        try:
            class_id = float(value[0])
            score = float(value[1])
            x1 = float(value[2])
            y1 = float(value[3])
            x2 = float(value[4])
            y2 = float(value[5])
        except (TypeError, ValueError):
            return None

        x1 = max(0.0, min(1.0, x1))
        y1 = max(0.0, min(1.0, y1))
        x2 = max(0.0, min(1.0, x2))
        y2 = max(0.0, min(1.0, y2))

        # Frigate contract: [label, score, y_min, x_min, y_max, x_max]
        return [class_id, score, y1, x1, y2, x2]

    def detect_raw(self, tensor_input: np.ndarray) -> np.ndarray:
        jpeg_bytes = self._encode_jpeg(tensor_input)
        if jpeg_bytes is None:
            return self._zero_result

        try:
            response = self.session.post(
                self.endpoint,
                data=jpeg_bytes,
                headers={"Content-Type": "image/jpeg"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as exc:
            if not self._warned_request_failure:
                logger.warning(
                    "metis request failed at endpoint %s: %s",
                    self.endpoint,
                    exc,
                )
                self._warned_request_failure = True
            else:
                logger.debug("metis request failed: %s", exc)
            return self._zero_result
        except ValueError:
            logger.debug("metis response is not valid JSON")
            return self._zero_result

        if not isinstance(payload, list):
            return self._zero_result

        detections = np.zeros((20, 6), np.float32)
        write_idx = 0

        for item in payload:
            parsed = self._parse_detection(item)
            if parsed is None:
                continue
            detections[write_idx] = parsed
            write_idx += 1
            if write_idx == 20:
                break

        return detections
