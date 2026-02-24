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
- `LOG_FORMAT=json|text` and `LOG_LEVEL=INFO|...` control logging output

## Run locally

```bash
pip install -r requirements.txt
MOCK=1 uvicorn app:app --host 0.0.0.0 --port 8090
```

For real inference:

```bash
MOCK=0 MODEL_DIR=/path/to/axelera_exported_model uvicorn app:app --host 0.0.0.0 --port 8090
```
