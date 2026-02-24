# SafeHaven v2 Architecture
Metis-first semantic security + Frigate as NVR/UI (stock) + optional Metis detector plugin

---

## 1. Executive summary

SafeHaven v2 is an **offline, privacy-first home security system** focused on *entry-point state* — not just motion.

- **Metis (Axelera AIPU)** is the intelligence plane: it infers **door/garage/gate state** and optional identity, and it decides when something is important.
- **Frigate (stock)** is the **NVR + timeline UI + recording manager**.
- SafeHaven writes **semantic events into Frigate** using the official **Create Event API**, so events like `garage_left_open` appear on the Frigate timeline even when there is **no motion**.
- As an engineering stretch (and ecosystem contribution), we also implement a **Metis detector plugin for Frigate** (sidecar-based), enabling Frigate’s standard object detection pipeline to offload inference to Metis.

This design preserves Frigate upgradeability, keeps sensitive data local, and makes “left-open / ajar” semantics first-class.

---

## 2. Problem statement

Nearly **30% of home break-ins happen through unlocked doors or open garages** (commonly cited stat used as product narrative).

Real-life pain:
- After a long day: “Did you close the garage door?”
- Backyard gate left open after taking out trash.
- Door latch accidentally left unlocked.

Classic “motion-only” systems miss the core issue:
- Once a garage is left open, there may be **no motion**, yet the risk persists.
- We need **state** (open/closed/ajar/locked/unlocked) and **time-based semantics** (“open for 7 minutes”).

---

## 3. Goals and non-goals

### Goals (v2)
1. **Left-open semantics** (Wow Option 1)
   - Garage door open/closed with a robust state machine
   - Backyard gate ajar/closed
   - Door latch locked/unlocked
   - Time-based triggers: `left_open` if open > X minutes

2. **Metis-first processing**
   - ROI-centric, low-rate sampling
   - Metis performs the heavy inference (classification/detection)
   - System continues working **offline**

3. **Frigate-native visibility**
   - SafeHaven creates **Frigate events via API** so semantic events show up in Frigate UI.

4. **Engineering-grade reliability**
   - Bounded queues
   - Drop policy for stale updates
   - Metrics: p95 inference latency, dropped updates, end-to-end event time

5. **Extensible “monitor anything” framework**
   - Add new monitors (stove-left-on, package delivery, pet door) via plugin interface.

### Non-goals (v2)
- Cloud dependency (explicitly out)
- Complex multi-user mobile app (HA / local UI is sufficient for hackathon)
- Full Frigate fork (avoid for maintainability)

---

## 4. Architecture overview

### 4.1 Components

**A) Frigate (stock)**
- Records RTSP streams
- Provides timeline playback and event UI
- Publishes standard MQTT topics (optional)
- Accepts externally-created events via HTTP API (Create Event)

**B) Mosquitto (optional but recommended)**
- Event bus for HA + internal messages

**C) SafeHaven Core (`safehaven-core`)**
- State sampling + state machines per camera/zone
- Calls Metis inference
- Emits semantic events (MQTT + Frigate Create Event)
- Backpressure + metrics

**D) Metis Inference Service (`metis-detector`)**
- Local API service that runs inference on Metis
- Can support multiple models:
  - object detector (person, vehicle)
  - state classifier/detector for garage/door/gate
  - latch-angle/keypoint model (optional)

**E) Local UI (HDMI) + local actuators**
- On-screen alerts
- Sonoff relay / buzzer / light triggers
- Optional auto-close / lock (fail-safe gated by confidence + safety rules)

**F) Home Assistant integration (optional, “nice-to-have”)**
- MQTT discovery + automations
- Notifications with snapshot + action buttons

### 4.2 High-level flow

```
[Cameras RTSP] 
   ├──> [Frigate (stock)]  ──> [Recordings + Timeline UI]
   │           │
   │           └──> (optional) publishes standard Frigate MQTT events
   │
   └──> [SafeHaven State Sampler] ──> [Metis Inference Service]
                      │
                      └──> [State Machines + Timers]
                               │
                               ├──> MQTT: safehaven/events/semantic
                               └──> Frigate Create Event API (timeline events)
```

Key point:
- **State detection does not depend on motion.**
- SafeHaven continues sampling even when the scene is static.

---

## 5. Core design choice: Semantic events via Frigate Create Event API

### 5.1 Why we need external event injection
Frigate creates events primarily when motion/object detection triggers occur. “Left open” is fundamentally **time without motion**, so relying on Frigate’s event triggers is insufficient.

Solution:
- SafeHaven detects semantic conditions (open/ajar/unlocked and duration thresholds)
- SafeHaven **creates Frigate events via API** at the moment the semantic condition is satisfied.

### 5.2 Event injection contract (Frigate)
SafeHaven calls:

- `POST /api/events/{camera}/{label}/create`

Labels we create:
- `garage_opened`, `garage_closed`, `garage_left_open`
- `gate_ajar`, `gate_closed`
- `latch_unlocked`, `latch_locked`

We attach metadata using `subLabel` and optionally `score`/`duration`:

Example body:
```json
{
  "subLabel": "open_for=7m conf=0.92 source=metis",
  "score": 0.92,
  "duration": 30
}
```

Outcome:
- The semantic event appears on Frigate timeline and can be clicked like native events.

---

## 6. Metis-first inference strategy

### 6.1 Two pipelines per camera
**Pipeline 1: NVR/UI (Frigate)**
- Continuous recording or scheduled recording
- High-res stream for evidence-quality video

**Pipeline 2: State intelligence (SafeHaven + Metis)**
- Low-res substream for analysis
- Low duty sampling (1–2 fps typical)
- ROI crop (small region around latch/garage panel/gate)

This keeps compute bounded and aligns with the “Metis does inference” theme.

### 6.2 Sampling modes
- **Idle sampling**: 1 fps (or configurable)
- **Confirm sampling**: temporary boost (e.g., 3 fps for 10 seconds) to debounce transitions
- **Open-state monitoring**: modest sampling (e.g., 1 fps) to validate state until closed

---

## 7. State machines (Wow Option 1)

SafeHaven uses **explicit state machines** per camera/zone.

### 7.1 Garage door (Open/Closed/Unknown)
States:
- `CLOSED`
- `OPEN`
- `UNKNOWN` (unstable/low confidence)

Inputs:
- Metis inference on garage ROI (preferred)
- Fallback heuristics (frame difference / edge intensity) if confidence low

Debounce parameters:
- `OPEN` requires M consecutive “open” samples
- `CLOSED` requires K consecutive “closed” samples
- Enter `UNKNOWN` if oscillating or confidence too low

Timers:
- If state is `OPEN` continuously for `LEFT_OPEN_MINUTES` -> emit `garage_left_open`

Events emitted:
- `garage_opened`
- `garage_closed`
- `garage_left_open`

### 7.2 Gate / backyard door (Ajar/Closed)
Similar but simpler (binary + unknown):
- `CLOSED`, `AJAR`, `UNKNOWN`
- `gate_ajar` and optional `gate_left_open`

### 7.3 Door latch (Locked/Unlocked)
Approaches:
- **v2 MVP**: classifier on latch ROI (locked vs unlocked)
- **upgrade**: 2-keypoint angle method (more robust than classifying full frames)

Events:
- `latch_locked`, `latch_unlocked`

---

## 8. Backpressure, reliability, and observability

### 8.1 Why backpressure matters
RTSP streams can produce bursts; events can flood; inference can slow.
We must prevent queue growth from causing latency spikes or OOM.

### 8.2 Bounded queues + drop policy
Per camera worker:
- `QUEUE_MAX = N` (configurable)
- when full:
  - drop **stale update** items
  - keep the **latest** sample (newest frame wins)
  - never block state transitions behind old frames

This is “real system” engineering and a key differentiator.

### 8.3 Metrics (Prometheus)
Expose `/metrics` and track:
- `safehaven_infer_ms` (histogram)
- `safehaven_e2e_ms` (histogram)
- `safehaven_queue_depth` (gauge)
- `safehaven_dropped_samples_total` (counter)
- `safehaven_semantic_events_total{type=...}` (counter)
- `safehaven_state{camera=..., zone=...}` (gauge/label as needed)

This enables soak-test proof (24h run, p95 latency, drop counts).

### 8.4 Failure handling
- Metis inference errors: degrade gracefully (UNKNOWN state)
- RTSP reconnect loops with exponential backoff
- Health endpoints:
  - `/healthz` for core liveness
  - `/readyz` for dependencies (Frigate reachable, Metis reachable)

---

## 9. Metis detector plugin for Frigate (stretch + ecosystem contribution)

### 9.1 Motivation
Frigate supports multiple detector types. A “Metis AIPU” detector plugin enables Frigate’s object detection to run on Metis without forking Frigate.

### 9.2 Design: sidecar-based plugin
Avoid importing heavy Voyager libraries directly inside Frigate.
Instead:
- Frigate plugin is an **HTTP client**
- Metis inference is a dedicated local service (`metis-detector`)

Plugin characteristics:
- `type: metis`
- `endpoint: http://metis-detector:8090/detect`
- `timeout_ms: 50–100`

`detect_raw(tensor)`:
- encode frame to JPEG or pass raw tensor
- POST to inference service
- parse detections -> return numpy array shaped to Frigate expectations:
  `[class_id, score, x1, y1, x2, y2]` normalized

This mirrors how other externalized detectors are implemented and keeps Frigate stock and upgradeable.

### 9.3 How it complements SafeHaven
- SafeHaven focuses on state semantics
- Frigate can optionally offload standard object detection to Metis
- Both share the same Metis inference service or separate endpoints/models

---

## 10. Extensibility: monitor anything later

### 10.1 Monitor plugin interface
SafeHaven treats each “thing we monitor” as a plugin:

- `subscriptions`: which camera/zone and sampling frequency
- `on_sample(frame, ts)`: update internal state
- `on_tick(now)`: timers/timeouts
- `emit_events()`: semantic outputs

Examples of future monitors:
- `package_delivery` (doorstep)
- `stove_left_on` (kitchen classifier)
- `pet_escape` (gate open + pet detected)
- `window_open` (bedroom/basement)

All produce:
- SafeHaven semantic events (MQTT)
- optional Frigate events (Create Event API)

---

## 11. Security and privacy

- Offline-first: no cloud required.
- Video stays local: Frigate stores recordings locally.
- Semantic events contain minimal data: labels + timestamps + optional snapshot.
- Optional “familiar faces” stays local:
  - embeddings stored locally
  - no cloud identity calls
  - event metadata via `subLabel=Known:<name>` (optional, future)

---

## 12. Deployment model

### 12.1 Minimal deployment (hackathon-ready)
- `frigate` container
- `mosquitto` container
- `metis-detector` container (or host service)
- `safehaven-core` host service (systemd) or container

### 12.2 Recommended runtime separation
- Keep Frigate stable and minimal.
- Keep Metis inference in its own service to isolate drivers/runtime.
- Keep SafeHaven core in its own process for easier iteration.

---

## 13. Demo plan (judge-friendly)

1) **Garage left open**
- Open garage
- Show state transition (opened)
- Wait threshold (e.g., 2 minutes for demo)
- SafeHaven injects `garage_left_open` event into Frigate timeline
- Click event in Frigate UI -> playback shows open garage
- Optional: trigger buzzer/light/relay

2) **Backyard gate ajar**
- Slightly open gate (no motion)
- SafeHaven detects `gate_ajar`
- Inject Frigate event

3) **Backpressure proof**
- Run 2–4 cameras
- Show metrics dashboard:
  - p95 inference latency
  - dropped samples near zero
  - queue depth stable

4) (Optional future) **Familiar faces**
- A known person arrives: event `person_at_entry` subLabel `Known:...`
- Unknown loitering triggers stronger alert

---

## 14. Appendix: Topic schema (recommended)

MQTT topics:
- `safehaven/events/semantic`
  - payload includes `camera`, `label`, `subLabel`, `score`, `ts`, `snapshot_url` (optional)

- `safehaven/state/<camera>/<zone>`
  - payload includes current state + confidence + last_change_ts

---

## 15. Appendix: Why this architecture is “Metis-first”
- The “meaning” (left-open, ajar, unlocked) is computed by Metis-driven inference + state machines.
- Frigate provides recording + UI and receives semantic events, but does not own the intelligence logic.
- The optional detector plugin further deepens Metis integration by enabling Frigate’s own object detection to use Metis.

---

**End of document**
