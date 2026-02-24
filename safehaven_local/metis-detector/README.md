# metis-detector

HTTP inference sidecar for SafeHaven/Frigate Metis integration.

## API

- `POST /detect`
  - Content-Type: `image/jpeg`
  - Response format: `[[class_id, score, x1, y1, x2, y2], ...]` (normalized coords)
- `GET /healthz`
- `GET /readyz`

## Modes

- `MOCK=1` (default): returns a fixed detection for easy bring-up
- `MOCK=0`: runs Ultralytics YOLO using `MODEL_DIR`
- `MODEL_TASK=detect|classify` selects inference output mode
- `LOG_FORMAT=json|text` and `LOG_LEVEL=INFO|...` control logging output

## Run locally

```bash
pip install -r requirements.txt
MOCK=1 uvicorn app:app --host 0.0.0.0 --port 8090
```

For real inference:

```bash
MOCK=0 MODEL_TASK=detect MODEL_DIR=/path/to/detector_model uvicorn app:app --host 0.0.0.0 --port 8090
```

For ROI classification workflow:

```bash
MOCK=0 MODEL_TASK=classify MODEL_DIR=/path/to/state_classifier.pt uvicorn app:app --host 0.0.0.0 --port 8090
```

## Docker path note

When running in Docker, `MODEL_DIR` must be a path **inside the container**.
Mount host directory to `/models` and point `MODEL_DIR` there, for example:

- `MODEL_HOST_DIR=/Users/bytedance/Downloads/image_train/project-1`
- `MODEL_DIR=/models/best.pt`
