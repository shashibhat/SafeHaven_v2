# SafeHaven Local

SafeHaven Local is the MacBook-first distribution of SafeHaven v2.

It keeps the same core architecture:
- `safehaven-core` semantic state engine
- `metis-detector` inference service API (`POST /detect`)
- Frigate Create Event API integration (`POST /api/events/{camera}/{label}/create`)

But defaults are tuned for local development on macOS (no Pi + no Metis hardware required).

## Why this variant exists

SafeHaven’s original target is edge hardware (Orange Pi + Axelera Metis). For local dev, iteration speed matters more than hardware acceleration. `safehaven_local` gives you:
- quick startup on MacBook
- mock-friendly defaults
- same APIs and state-machine semantics
- easy switch to full Frigate UI mode

## Modes

### 1) Local Demo Mode (default)

- Uses `mock-frigate` service at `http://mock-frigate:5001`
- Uses `metis-detector` with `MOCK=1`
- Validates semantic event creation without running full Frigate

### 2) Full Frigate Mode

- Starts real Frigate with `--profile frigate`
- Set `FRIGATE_BASE_URL=http://frigate:5000`
- Keeps all other components identical

## Quickstart (MacBook)

1. Prepare env
```bash
cp .env.example .env
```

Default camera stream is preconfigured in:
- `safehaven-core/config/safehaven.yml`
- `frigate/config/config.yml`

2. Start default local demo stack
```bash
docker-compose up --build
```

3. Validate services
```bash
curl http://localhost:8090/healthz
curl http://localhost:9108/metrics | head
curl http://localhost:9109/healthz
curl http://localhost:9109/readyz
```

4. Verify Create Event API calls are happening
```bash
docker-compose logs -f mock-frigate safehaven-core
```
You should see `POST /api/events/{camera}/{label}/create` entries.

## Full Frigate UI Mode

1. Update `.env`:
```env
FRIGATE_BASE_URL=http://frigate:5000
```

2. Start with Frigate profile:
```bash
docker-compose --profile frigate up --build
```

3. Open Frigate UI: [http://localhost:5000](http://localhost:5000)

## Local-only quick semantic demo (no compose)

```bash
make demo-mock
```

This runs:
- generated local MP4 source
- mock Frigate server
- `safehaven-core` and real semantic state transitions

## Repository Layout

```text
safehaven_local/
  docker-compose.yml
  .env.example
  metis-detector/
  safehaven-core/
  frigate-metis-plugin/
  docs/
```

## Notes for MacBook performance

- Keep `MOCK=1` unless you specifically test local CPU model inference.
- Lower `SAMPLE_FPS` when running multiple streams.
- Use smaller ROI boxes to reduce detector request payloads.
- Frigate on laptops can be heavy; use demo mode for day-to-day development.
- For real state-model testing, use the toolkit:
  - [Model Toolkit](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/modeling/README.md)

## Security baseline

- Non-root app containers (`safehaven-core`, `metis-detector`)
- Read-only filesystems + `tmpfs` for writable temp data
- `no-new-privileges` + dropped capabilities
- Local-first/offline-friendly defaults

## References

- [Architecture V2](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/docs/ARCHITECTURE_V2.md)
- [Final Submission Guide](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/docs/FINAL_SUBMISSION_GUIDE.md)
- [MacBook Runbook](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/docs/MACBOOK_RUNBOOK.md)
- [SafeHaven Core](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/safehaven-core/README.md)
- [Metis Detector](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/metis-detector/README.md)
- [Frigate Plugin](/Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local/frigate-metis-plugin/README.md)
