# SafeHaven Local Architecture (MacBook-first)

SafeHaven v2 separates concerns:

- **Frigate (stock):** NVR, recordings, timeline UI
- **Metis detector:** local inference sidecar (`POST /detect`)
- **SafeHaven core:** semantic state machines + timers + event injection

This local distribution preserves the same contracts as the edge deployment while allowing two laptop-friendly modes:
- **Demo mode (default):** mock Frigate endpoint + mock Metis detections
- **Full mode:** stock Frigate enabled via compose profile

## Main flow

1. Cameras stream to Frigate for recording/UI.
2. SafeHaven samples low-rate frames (or substreams), crops ROIs, and calls Metis.
3. State machines track `garage`, `gate`, `latch` semantics with debounce.
4. On transitions and left-open timers, SafeHaven calls Frigate Create Event API:
   - `POST /api/events/{camera}/{label}/create`
5. Events appear on Frigate timeline even without motion.

## Why Create Event API matters

“Left open” is a **time-based semantic condition**, often with no new motion. Frigate’s normal event pipeline is motion/object-centric. By injecting semantic events through the official Create Event API, SafeHaven preserves stock Frigate behavior while making persistent risk states visible in timeline/history.

## Reliability controls

- Bounded per-camera queue
- Drop stale samples (newest frame wins)
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
