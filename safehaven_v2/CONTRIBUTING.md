# Contributing

## Development Principles

- Keep Frigate stock (no Frigate fork)
- Preserve Metis-first semantic pipeline
- Maintain offline-first and privacy-first defaults
- Prefer explicit state machine changes over implicit behavior

## Local Setup

1. Install Docker + Docker Compose
2. Copy `.env.example` to `.env`
3. Populate runtime values for camera connectivity and model paths
4. Start the stack:
   ```bash
   docker compose up --build
   ```
5. Validate configuration assets:
   ```bash
   make lint-configs
   ```

## Pull Request Checklist

- Add or update tests when behavior changes
- Update docs for API/config/architecture changes
- Validate `/metrics` still exposes required metrics
- Ensure Frigate Create Event API behavior remains compatible
- Keep Python compatibility at 3.10+

## Commit Guidance

- Use focused commits per concern
- Include operational impact in commit message body for infra/state-machine changes
