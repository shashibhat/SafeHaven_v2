import os
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .config import ROI


@dataclass
class Sample:
    camera: str
    frame: np.ndarray
    captured_ts: float


def crop_roi(frame: np.ndarray, roi: ROI) -> np.ndarray:
    h, w = frame.shape[:2]
    x1 = int(roi.x * w) if roi.x <= 1 else int(roi.x)
    y1 = int(roi.y * h) if roi.y <= 1 else int(roi.y)
    rw = int(roi.w * w) if roi.w <= 1 else int(roi.w)
    rh = int(roi.h * h) if roi.h <= 1 else int(roi.h)
    x2 = min(w, max(x1 + 1, x1 + rw))
    y2 = min(h, max(y1 + 1, y1 + rh))
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    return frame[y1:y2, x1:x2]


def sample_stream(stream_url: str, sample_fps: float):
    interval = 1.0 / max(sample_fps, 0.1)
    backoff = 1.0
    cap = None
    if stream_url.startswith("rtsp://"):
        transport = os.getenv("RTSP_TRANSPORT", "tcp").strip().lower()
        if transport in ("tcp", "udp"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"

    while True:
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(stream_url)
            if not cap.isOpened():
                time.sleep(backoff)
                backoff = min(10.0, backoff * 2)
                continue
            backoff = 1.0

        start = time.time()
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            cap = None
            time.sleep(backoff)
            backoff = min(10.0, backoff * 2)
            continue

        yield frame, start

        elapsed = time.time() - start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
