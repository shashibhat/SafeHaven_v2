# SafeHaven Local MacBook Runbook

## Goal

Run SafeHaven semantics locally on macOS without Pi/Metis hardware while preserving service contracts.

## Prerequisites

- Docker Desktop
- `docker-compose` available
- 8GB+ RAM recommended for Frigate mode

## Start demo mode (recommended)

```bash
cp .env.example .env
docker-compose up --build
```

Default wiring:
- `safehaven-core` -> `mock-frigate` for Create Event API
- `safehaven-core` -> `metis-detector` with `MOCK=1`

## Validate

```bash
curl http://localhost:8090/readyz
curl http://localhost:9109/readyz
curl http://localhost:9108/metrics | grep safehaven_
```

Check logs for semantic event POSTs:

```bash
docker-compose logs -f mock-frigate safehaven-core
```

## Switch to real Frigate UI

Set in `.env`:

```env
FRIGATE_BASE_URL=http://frigate:5000
```

Run:

```bash
docker-compose --profile frigate up --build
```

Then open `http://localhost:5000`.

## Troubleshooting

- `safehaven-core not ready`: verify `FRIGATE_BASE_URL` points to active target (`mock-frigate` or `frigate`)
- high CPU: reduce `SAMPLE_FPS`, reduce camera count, keep `MOCK=1`
- missing events: inspect `safehaven-core` logs for request errors to `/api/events/.../create`
