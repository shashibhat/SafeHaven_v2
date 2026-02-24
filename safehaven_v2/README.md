# SafeHaven v2

Metis-first semantic security with Frigate as stock NVR/UI and a Metis HTTP detector plugin.

## Quickstart

1. Copy env defaults:
   ```bash
   cp .env.example .env
   ```
2. Start services:
   ```bash
   docker compose up --build
   ```
3. Check SafeHaven metrics:
   ```bash
   curl http://localhost:9108/metrics | head
   ```
4. Verify semantic event creation calls:
   - In normal mode, check `safehaven-core` logs for `/api/events/{camera}/{label}/create` POST results.
   - For local demo without Frigate, run:
     ```bash
     make demo-mock
     ```
     This starts a mock Frigate API server and prints received Create Event requests.
