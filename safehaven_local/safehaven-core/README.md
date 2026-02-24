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
- `STATE_CONF_THRESHOLD` (default `0.5`, recommended `0.05-0.15` for weak early models)
- `ZONE_CLASS_MAP` (optional JSON mapping zone to `{open,closed}` class IDs)
- `EVIDENCE_DIR` (default `/tmp/safehaven_evidence`)
- `SAVE_EVENT_MEDIA` (`1/0`, default `1`) save ROI/full snapshots and fetch Frigate snapshot/clip per semantic event
- `DEMO_EMIT_INTERVAL_S` (`0` disables) emit periodic demo events for a zone even without transition
- `DEMO_ZONE` (default `latch`) zone used for periodic demo events

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

## How state is decided

- For each configured ROI (`garage`, `gate`, `latch`), core calls `POST /detect`.
- Detector returns rows as `[class_id, score, x1, y1, x2, y2]`.
- Class IDs are mapped per zone using `ZONE_CLASS_MAP` / `zone_class_map`.
- Debounce requires consecutive samples before transition.
- If a zone remains open/ajar for `LEFT_OPEN_MINUTES`, `*_left_open` event is emitted.
