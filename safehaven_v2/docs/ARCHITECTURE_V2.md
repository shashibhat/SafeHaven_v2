# SafeHaven v2 Architecture (Dual-Path Metis + Frigate)

SafeHaven v2 separates concerns:

- **Frigate (stock):** NVR, recordings, timeline UI for the sidecar path
- **Frigate host fork:** cloned Frigate source with direct Metis worker support
- **Metis detector sidecar:** local inference sidecar (`POST /detect`) retained for stock Frigate compatibility
- **SafeHaven core:** semantic state machines + timers + event injection

## Main flow

1. Cameras stream to Frigate for recording/UI.
2. SafeHaven samples low-rate frames (or substreams), crops ROIs, and calls Metis over the sidecar path.
3. State machines track `garage`, `gate`, `latch` semantics with debounce.
4. On transitions and left-open timers, SafeHaven calls Frigate Create Event API:
   - `POST /api/events/{camera}/{label}/create`
5. Events appear on Frigate timeline even without motion.

## Direct `frigate-host` path

The cloned Frigate source also supports direct detector execution:

1. Frigate detector config uses `type: metis` with `execution: voyager`.
2. The detector plugin starts or connects to a local Unix-socket worker.
3. The worker runs under the Voyager SDK Python environment and feeds JPEG frames into Axelera's `create_inference_stream(...)` data-source pipeline.
4. Detection results return to Frigate without the HTTP sidecar hop.

This is the preferred path for Orange Pi host deployments where Voyager SDK behavior is sensitive to container boundaries.

Deployment assets for this path now live under:

- `deploy/frigate-host/install_host.sh`
- `deploy/frigate-host/config/frigate-host.yml`
- `deploy/frigate-host/env.example`
- `deploy/frigate-host/check_host.sh`

## Why Create Event API matters

“Left open” is a **time-based semantic condition**, often with no new motion. Frigate’s normal event pipeline is motion/object-centric. By injecting semantic events through the official Create Event API, SafeHaven preserves stock Frigate behavior while making persistent risk states visible in timeline/history.

## Reliability controls

- Bounded per-camera queue
- Prefer freshest samples under load
- Prometheus metrics:
  - `safehaven_infer_ms`
  - `safehaven_e2e_ms`
  - `safehaven_queue_depth`
  - `safehaven_dropped_samples`
  - `safehaven_semantic_events`

## Security notes

- Offline-first design: no cloud dependency required.
- Local-only processing and event generation by default.
- Video remains local in Frigate storage.
- Semantic metadata is minimal and does not require external identity services.
