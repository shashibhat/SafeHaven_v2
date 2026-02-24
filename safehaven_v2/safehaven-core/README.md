# safehaven-core

State semantics service for SafeHaven v2.

## Features

- Per-camera workers with bounded queue and stale-frame drop policy
- Debounced state machines for:
  - `garage_open/closed`
  - `gate_ajar/closed`
  - `latch_locked/unlocked`
- Left-open timer events (`*_left_open`) after configurable minutes
- Frigate Create Event API integration (`POST /api/events/{camera}/{label}/create`)
- Prometheus metrics on `/metrics`

## Config

Reads env + YAML (`SAFEHAVEN_CONFIG`, default `/config/safehaven.yml`):

- `FRIGATE_BASE_URL` (default `http://frigate:5000`)
- `METIS_DETECTOR_URL` (default `http://metis-detector:8090/detect`)
- `MQTT_BROKER` (optional)
- `CAMERAS` (JSON list override)
- `SAMPLE_FPS` (default `1`)
- `LEFT_OPEN_MINUTES` (default `7`)
- `QUEUE_MAX` (default `50`)
- `METRICS_PORT` (default `9108`)
- `HEALTH_PORT` (default `9109`)
- `LOG_FORMAT` (`text` or `json`, default `text`)
- `LOG_LEVEL` (default `INFO`)

## Local run

```bash
pip install -e .
safehaven-core
```

## Demo

```bash
./scripts/demo_mock.sh
```

Requires `metis-detector` running with `MOCK=1` on `:8090`.

## Health endpoints

- `/healthz`: process liveness
- `/readyz`: dependency readiness (`frigate`, `metis-detector`)
