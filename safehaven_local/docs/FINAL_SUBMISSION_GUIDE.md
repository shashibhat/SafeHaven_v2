# Final Submission Guide (SafeHaven Local)

This guide is optimized for your final demo and evidence collection on MacBook.

## 1) Camera setup used in this repo

Configured stream:

- `rtsp://rtsp:12345678@192.168.1.48:554/av_stream/ch0`

Applied in:
- `safehaven-core/config/safehaven.yml`
- `frigate/config/config.yml` (for full Frigate mode)

## 2) Best model strategy on MacBook

Recommended order:

1. **Demo/reliability mode (recommended for submission):** `MOCK=1`
   - Guarantees deterministic demo behavior.
   - Lets you validate event timeline, workflows, metrics, and architecture.

2. **Real local model mode (optional for extra evidence):** `MOCK=0` with a lightweight custom model
   - Start with **YOLOv8n**-class lightweight detector (Ultralytics) trained on your ROIs.
   - Keep classes aligned to semantics.
   - On Mac CPU, keep FPS low (`SAMPLE_FPS=1`) and crop ROIs tightly.
   - Better MacBook accuracy/perf balance: use **`yolov8m-cls`** ROI classifier and run on `mps`.

See model scripts:
- `modeling/train_state_classifier.py`
- `modeling/infer_rtsp_state.py`

### Required class contract

`safehaven-core` expects detector outputs as:

`[class_id, score, x1, y1, x2, y2]`

Then maps `class_id` to semantic state with `zone_class_map` / `ZONE_CLASS_MAP`:

```yaml
zone_class_map:
  garage: {open: 0, closed: 1}
  gate: {open: 2, closed: 3}
  latch: {open: 4, closed: 5}
```

If your trained model uses different class IDs, update `ZONE_CLASS_MAP` without changing code.

## 3) How code decides door/latch status

Per sample frame:

1. `rtsp_sampler` grabs a frame.
2. For each zone ROI (`garage`, `gate`, `latch`), core sends JPEG to `POST /detect`.
3. Core selects best scores for zone `open` and `closed` classes.
4. If both scores are below threshold, state = `UNKNOWN`.
5. Otherwise higher score wins (`OPEN` or `CLOSED`).
6. Debounce requires consecutive confirmations before state transition event is emitted.

Transition events:
- garage: `garage_opened`, `garage_closed`
- gate: `gate_ajar`, `gate_closed`
- latch: `latch_unlocked`, `latch_locked`

## 4) How left-open timer triggers workflow

After a zone enters `OPEN`:

- `open_since` timestamp is recorded.
- If still open for `LEFT_OPEN_MINUTES`, emit `*_left_open` once.
- Event is sent to Frigate Create Event API:
  - `POST /api/events/{camera}/{label}/create`

Example labels:
- `garage_left_open`
- `gate_left_open`
- `latch_left_open`

This works even with no motion because it is time/state-based, not motion-based.

## 5) Evidence collection checklist

For final submission, capture all of these:

1. **Architecture proof**
   - screenshot of running containers (`docker-compose ps`)
   - screenshot of `safehaven-core` metrics endpoint

2. **State transition proof**
   - logs showing `garage_opened` / `latch_unlocked`
   - logs or Frigate event list showing Create Event API calls

3. **Left-open proof**
   - set low threshold (`LEFT_OPEN_MINUTES=1` or `2`)
   - capture generated `garage_left_open` event

4. **Frigate UI proof (full mode)**
   - Live page screenshot (camera group / Birdseye if enabled)
   - Review page screenshot with semantic event labels
   - event detail screenshot showing `subLabel` metadata

5. **Reliability proof**
   - `safehaven_dropped_samples`
   - `safehaven_queue_depth`
   - `safehaven_infer_ms` / `safehaven_e2e_ms`

## 6) Frigate customization for this project

Practical customizations you should use:

- Camera config tuning (stream roles, detect/record behavior)
- Birdseye modes/layout and camera grouping layouts
- Object filters, masks, and zones for noise reduction
- Detector selection (`cpu`, `openvino`, `onnx`, plus your `type: metis` plugin path)
- Review/alerts/detections filters and retention policies
- MQTT/Home Assistant automation workflows from semantic events

For this project specifically:
- Keep Frigate stock for recording/UI.
- Keep semantic logic in `safehaven-core`.
- Use Create Event API to inject non-motion semantics into timeline.
- Use Frigate UI pages as evidence artifacts:
  - **Live**: active camera and stream behavior
  - **Birdseye**: multi-camera overview and activity display
  - **Review**: event/history browsing and filters

### About theme customization

Frigate supports practical UI/layout configuration (Live streams, Birdseye layout, camera groups), but not a broad first-party theming system intended for brand-level restyling. For submission, focus on workflow and event clarity rather than theme skinning.

## 7) Suggested workflow automations

1. When `garage_left_open` event appears:
   - send local alert (buzzer/light)
   - optionally trigger relay after safety checks

2. When `latch_unlocked` persists after night hours:
   - push urgent local notification + display overlay

3. When repeated `gate_ajar` events occur:
   - mark as suspicious + increase sampling temporarily

## 8) Demo command plan

### Local demo mode (fast)

```bash
cd safehaven_local
cp .env.example .env
docker-compose up --build
```

### Full Frigate UI mode

```bash
# in .env set FRIGATE_BASE_URL=http://frigate:5000
docker-compose --profile frigate up --build
```

### Standalone semantic test

```bash
make demo-mock
```
