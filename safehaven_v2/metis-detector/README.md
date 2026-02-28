# metis-detector

HTTP inference sidecar for SafeHaven/Frigate Metis integration.

## API

- `POST /detect`
  - Content-Type: `image/jpeg`
  - Response format: `[[class_id, score, x1, y1, x2, y2], ...]` (normalized coords)
- `GET /healthz`
- `GET /readyz`

## Runtime configuration

- `MODEL_DIR`: path to the exported model artifact consumed by the service
- `LOG_FORMAT=json|text` and `LOG_LEVEL=INFO|...`: logging controls

## Run locally

```bash
MODEL_DIR=/path/to/axelera_exported_model uvicorn app:app --host 0.0.0.0 --port 8090
```
