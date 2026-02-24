import datetime
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import List
import sys

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

app = FastAPI(title="metis-detector", version="0.1.0")
_model_lock = Lock()
_model = None
LOGGER = logging.getLogger("metis-detector")


class Config:
    mock = os.getenv("MOCK", "1") == "1"
    model_dir = os.getenv("MODEL_DIR", "")
    log_format = os.getenv("LOG_FORMAT", "text")
    log_level = os.getenv("LOG_LEVEL", "INFO")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def _setup_logging() -> None:
    level = getattr(logging, Config.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if Config.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def _resolve_model_path(model_dir: str) -> str:
    path = Path(model_dir)
    if path.is_file():
        return str(path)
    if path.is_dir():
        candidates = list(path.glob("*.pt")) + list(path.glob("*.onnx"))
        if candidates:
            return str(candidates[0])
    raise FileNotFoundError(f"No YOLO model found under MODEL_DIR={model_dir}")


def _get_model():
    global _model
    if _model is not None:
        return _model
    if YOLO is None:
        raise RuntimeError("ultralytics is not available")
    with _model_lock:
        if _model is None:
            model_path = _resolve_model_path(Config.model_dir)
            _model = YOLO(model_path)
    return _model


def _mock_detection() -> List[List[float]]:
    return [[0, 0.95, 0.2, 0.2, 0.8, 0.8]]


@app.on_event("startup")
def on_startup():
    _setup_logging()
    LOGGER.info("metis-detector startup mock=%s model_dir=%s", Config.mock, Config.model_dir)


@app.get("/healthz")
def healthz():
    return {"ok": True, "mock": Config.mock}


@app.get("/readyz")
def readyz():
    if Config.mock:
        return {"ready": True, "mode": "mock"}
    try:
        _get_model()
        return {"ready": True, "mode": "inference"}
    except Exception as exc:
        LOGGER.warning("readyz failed err=%s", exc)
        raise HTTPException(status_code=503, detail=f"Model not ready: {exc}")


@app.post("/detect")
async def detect(request: Request):
    content_type = request.headers.get("content-type", "")
    if "image/jpeg" not in content_type:
        raise HTTPException(status_code=415, detail="Only image/jpeg is supported")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty image payload")

    if Config.mock:
        return _mock_detection()

    image_array = np.frombuffer(body, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid JPEG payload")

    model = _get_model()
    results = model.predict(image, verbose=False)
    if not results:
        return []

    result = results[0]
    h, w = image.shape[:2]
    detections = []
    for box in result.boxes:
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = xyxy
        class_id = int(box.cls[0].item())
        score = float(box.conf[0].item())
        detections.append([
            class_id,
            score,
            max(0.0, min(1.0, x1 / w)),
            max(0.0, min(1.0, y1 / h)),
            max(0.0, min(1.0, x2 / w)),
            max(0.0, min(1.0, y2 / h)),
        ])

    return detections
