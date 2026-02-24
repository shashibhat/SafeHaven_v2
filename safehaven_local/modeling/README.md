# SafeHaven Model Toolkit (MacBook)

This folder provides minimal-training model workflow for state semantics.

## Recommended model

Use **`yolov8m-cls.pt`** as base model on MacBook:
- better accuracy than nano/small for subtle latch states
- still practical on Apple Silicon with `device=mps`

For faster iteration use `yolov8s-cls.pt`.

## Why classification (not full detection)

SafeHaven core already crops per-zone ROI (`garage`, `gate`, `latch`).
For state semantics, a classifier is simpler and needs less data:
- classes: `open`, `closed`
- map low confidence to `unknown` in code

## Dataset layout

```text
dataset_root/
  train/
    open/
    closed/
  val/
    open/
    closed/
```

Train separate models per zone for best quality:
- garage model (open/closed)
- latch model (locked/unlocked; map labels to open/closed semantics as needed)

## Latch-first flow with your existing dataset

Your existing project appears to use class IDs:
- `0 = Closed`
- `1 = Open`
- `2 = Unknown` (ignored for training)

Convert your current YOLO labels into classifier crops:

```bash
cd /Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local
python3 -m venv .venv
source .venv/bin/activate
pip install ultralytics opencv-python

python modeling/prepare_latch_from_yolo.py \
  --images-dir /Users/bytedance/Downloads/image_train/project-1/images \
  --labels-dir /Users/bytedance/Downloads/image_train/project-1/labels \
  --out-dir /Users/bytedance/Downloads/image_train/project-1/latch_cls_dataset \
  --closed-class-id 0 \
  --open-class-id 1 \
  --ignore-class-ids 2 \
  --focus-roi 0.72,0.35,0.12,0.20 \
  --min-focus-overlap 0.30 \
  --pad 0.10 \
  --val-ratio 0.2 \
  --clean
```

Before conversion, you can estimate a robust focus ROI from current labels:

```bash
python modeling/suggest_focus_roi.py \
  --labels-dir /Users/bytedance/Downloads/image_train/project-1/labels \
  --images-dir /Users/bytedance/Downloads/image_train/project-1/images \
  --class-ids 0,1 \
  --pad 0.03 \
  --lower-q 0.15 \
  --upper-q 0.85
```

Use the returned `roi_csv` as `--focus-roi`.

If many labels are unmatched, rerun with:

```bash
python modeling/prepare_latch_from_yolo.py \
  --images-dir /Users/bytedance/Downloads/image_train/project-1/dataset/images \
  --labels-dir /Users/bytedance/Downloads/image_train/project-1/labels \
  --out-dir /Users/bytedance/Downloads/image_train/project-1/latch_cls_dataset \
  --closed-class-id 0 \
  --open-class-id 1 \
  --ignore-class-ids 2 \
  --focus-roi 0.72,0.35,0.12,0.20 \
  --min-focus-overlap 0.30 \
  --pad 0.10 \
  --val-ratio 0.2 \
  --clean
```

Then train latch classifier:

```bash
python modeling/train_state_classifier.py \
  --data-dir /Users/bytedance/Downloads/image_train/project-1/latch_cls_dataset \
  --model yolov8m-cls.pt \
  --epochs 50 \
  --batch 32 \
  --imgsz 224 \
  --device mps \
  --name latch_v1
```

Best checkpoint:
`runs/safehaven_cls/latch_v1/weights/best.pt`

## 1) Train model

```bash
cd /Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/safehaven_local
python3 -m venv .venv
source .venv/bin/activate
pip install ultralytics opencv-python

python modeling/train_state_classifier.py \
  --data-dir /path/to/garage_dataset \
  --model yolov8m-cls.pt \
  --epochs 40 \
  --batch 32 \
  --device mps \
  --name garage_v1
```

Output best checkpoint:
`runs/safehaven_cls/garage_v1/weights/best.pt`

## 2) Live RTSP test

First calibrate the latch ROI on live stream:

```bash
python modeling/calibrate_roi.py \
  --stream "rtsp://rtsp:12345678@192.168.1.48:554/av_stream/ch0"
```

Press `s` and drag around the latch/lockset.  
Copy printed `ROI_CSV=...` into `--roi` for inference scripts and into SafeHaven config.

```bash
python modeling/infer_rtsp_state.py \
  --model runs/safehaven_cls/latch_v1/weights/best.pt \
  --stream "rtsp://rtsp:12345678@192.168.1.48:554/av_stream/ch0" \
  --roi 0.72,0.35,0.12,0.20 \
  --device mps \
  --unknown-threshold 0.55
```

Press `q` to exit.

Popup viewer (like your `test.py`) with overlays:

Classify mode (latch ROI):

```bash
python modeling/stream_infer_view.py \
  --model runs/safehaven_cls/latch_v1/weights/best.pt \
  --stream "rtsp://rtsp:12345678@192.168.1.48:554/av_stream/ch0" \
  --task classify \
  --roi 0.72,0.35,0.12,0.20 \
  --device mps
```

Detect mode (full-frame boxes like YOLO `plot()`):

```bash
python modeling/stream_infer_view.py \
  --model /path/to/detector.pt \
  --stream "rtsp://rtsp:12345678@192.168.1.48:554/av_stream/ch0" \
  --task detect
```

## 3) Evaluate latch model quality

```bash
python modeling/evaluate_state_classifier.py \
  --model runs/safehaven_cls/latch_v1/weights/best.pt \
  --data-dir /Users/bytedance/Downloads/image_train/project-1/latch_cls_dataset \
  --split val \
  --device mps \
  --unknown-threshold 0.55
```

This prints:
- overall accuracy
- confusion matrix
- per-class precision/recall/F1

## If latch is still not detected

1. Verify ROI first with popup viewer (`--task classify --roi ...`).
2. Lower threshold temporarily (`--unknown-threshold 0.40`) and observe confidence.
3. Rebuild dataset with stricter focus ROI (`--min-focus-overlap 0.5`) so only latch-like crops remain.
4. Ensure class mapping is correct:
   - if dataset labels are `Closed=0`, `Open=1`, then latch mapping should be `latch: {open: 1, closed: 0}`.
5. Add hard examples:
   - night frames
   - glare/reflections
   - partially occluded latch
   - motion blur

## 4) Plug model into `metis-detector`

In `.env`:

```env
MOCK=0
MODEL_TASK=classify
MODEL_DIR=/absolute/path/to/best.pt
```

Then restart stack:

```bash
docker-compose up --build
```

## 5) Class ID contract with SafeHaven core

`metis-detector` returns top-1 prediction in Frigate row format:

`[class_id, score, 0.0, 0.0, 1.0, 1.0]`

Map class IDs to semantic states in:
- `safehaven-core/config/safehaven.yml` (`zone_class_map`)
- or env `ZONE_CLASS_MAP`

Example:

```yaml
zone_class_map:
  garage: {open: 1, closed: 0}
  gate: {open: 1, closed: 0}
  latch: {open: 1, closed: 0}
```

If latch model classes are `locked=0`, `unlocked=1`, keep:

```yaml
zone_class_map:
  latch: {open: 1, closed: 0}
```
