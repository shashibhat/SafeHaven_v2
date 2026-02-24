#!/usr/bin/env python3
"""Build a latch classification dataset from existing YOLO labels.

Supports YOLO bbox labels and YOLO segmentation polygon labels.
Outputs Ultralytics classify layout:

out_dir/
  train/
    open/
    closed/
  val/
    open/
    closed/
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import cv2

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare latch classification dataset from YOLO labels")
    parser.add_argument("--images-dir", required=True, help="Directory with source images")
    parser.add_argument("--labels-dir", required=True, help="Directory with YOLO txt labels")
    parser.add_argument("--out-dir", required=True, help="Output classify dataset root")
    parser.add_argument("--open-class-id", type=int, default=1, help="YOLO class id representing OPEN/UNLOCKED")
    parser.add_argument("--closed-class-id", type=int, default=0, help="YOLO class id representing CLOSED/LOCKED")
    parser.add_argument("--ignore-class-ids", default="2", help="Comma list of class ids to skip")
    parser.add_argument("--pad", type=float, default=0.08, help="BBox padding ratio around labeled object")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument("--min-size", type=int, default=24, help="Minimum crop width/height")
    parser.add_argument(
        "--focus-roi",
        default="",
        help="Optional normalized ROI x,y,w,h to keep only objects intersecting that area (recommended for latch)",
    )
    parser.add_argument(
        "--min-focus-overlap",
        type=float,
        default=0.3,
        help="Minimum overlap ratio (object area intersection) with focus ROI",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clean", action="store_true", help="Delete out-dir before writing")
    return parser.parse_args()


def _find_image(stem: str, images_dir: Path) -> Path | None:
    for ext in IMG_EXTS:
        cand = images_dir / f"{stem}{ext}"
        if cand.exists():
            return cand
    matches = [p for p in images_dir.rglob("*") if p.suffix.lower() in IMG_EXTS and p.stem == stem]
    return matches[0] if matches else None


def _line_to_xyxy(parts: list[float], w: int, h: int) -> tuple[int, int, int, int] | None:
    coords = parts[1:]
    if len(coords) < 4:
        return None

    # bbox format: cls cx cy bw bh
    if len(coords) == 4:
        cx, cy, bw, bh = coords
        x1 = int((cx - bw / 2.0) * w)
        y1 = int((cy - bh / 2.0) * h)
        x2 = int((cx + bw / 2.0) * w)
        y2 = int((cy + bh / 2.0) * h)
        return x1, y1, x2, y2

    # segmentation polygon format: cls x1 y1 x2 y2 ...
    xs = []
    ys = []
    for i in range(0, len(coords) - 1, 2):
        xs.append(coords[i] * w)
        ys.append(coords[i + 1] * h)
    if not xs or not ys:
        return None
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _pad_clip(x1: int, y1: int, x2: int, y2: int, w: int, h: int, pad: float) -> tuple[int, int, int, int]:
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    px = int(bw * pad)
    py = int(bh * pad)
    x1 = max(0, x1 - px)
    y1 = max(0, y1 - py)
    x2 = min(w, x2 + px)
    y2 = min(h, y2 + py)
    return x1, y1, x2, y2


def _norm_roi_to_xyxy(roi: tuple[float, float, float, float], w: int, h: int) -> tuple[int, int, int, int]:
    x, y, rw, rh = roi
    x1 = max(0, min(w - 1, int(x * w)))
    y1 = max(0, min(h - 1, int(y * h)))
    x2 = max(x1 + 1, min(w, int((x + rw) * w)))
    y2 = max(y1 + 1, min(h, int((y + rh) * h)))
    return x1, y1, x2, y2


def _overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    a_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    return inter / a_area


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    images_dir = Path(args.images_dir).expanduser().resolve()
    labels_dir = Path(args.labels_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    ignore_ids = {int(x.strip()) for x in args.ignore_class_ids.split(",") if x.strip()}
    focus_roi = None
    if args.focus_roi.strip():
        vals = [float(v.strip()) for v in args.focus_roi.split(",")]
        if len(vals) != 4:
            raise ValueError("--focus-roi must be x,y,w,h")
        focus_roi = tuple(vals)

    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)

    for split in ("train", "val"):
        for klass in ("open", "closed"):
            (out_dir / split / klass).mkdir(parents=True, exist_ok=True)

    label_files = sorted(labels_dir.glob("*.txt"))
    samples_by_label: dict[str, list[Path]] = {"open": [], "closed": []}
    skipped_missing_img = 0
    skipped_unknown_cls = 0
    skipped_tiny = 0
    skipped_focus = 0

    for lbl in label_files:
        img_path = _find_image(lbl.stem, images_dir)
        if img_path is None:
            skipped_missing_img += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        focus_xyxy = _norm_roi_to_xyxy(focus_roi, w, h) if focus_roi else None

        lines = [ln.strip() for ln in lbl.read_text().splitlines() if ln.strip()]
        for idx, line in enumerate(lines):
            toks = line.split()
            if len(toks) < 5:
                continue
            try:
                cls_id = int(float(toks[0]))
                parts = [float(x) for x in toks]
            except ValueError:
                continue

            if cls_id in ignore_ids:
                skipped_unknown_cls += 1
                continue

            if cls_id == args.open_class_id:
                label = "open"
            elif cls_id == args.closed_class_id:
                label = "closed"
            else:
                skipped_unknown_cls += 1
                continue

            box = _line_to_xyxy(parts, w, h)
            if box is None:
                continue
            if focus_xyxy is not None and _overlap_ratio(box, focus_xyxy) < args.min_focus_overlap:
                skipped_focus += 1
                continue
            x1, y1, x2, y2 = _pad_clip(*box, w, h, args.pad)
            if (x2 - x1) < args.min_size or (y2 - y1) < args.min_size:
                skipped_tiny += 1
                continue

            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            out_name = f"{lbl.stem}_{idx}.jpg"
            tmp_path = out_dir / "_tmp" / label / out_name
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(tmp_path), crop)
            samples_by_label[label].append(tmp_path)

    for label, paths in samples_by_label.items():
        random.shuffle(paths)
        if not paths:
            continue
        val_count = int(len(paths) * args.val_ratio)
        if len(paths) >= 2 and val_count == 0:
            val_count = 1
        if val_count >= len(paths):
            val_count = len(paths) - 1
        for idx, src in enumerate(paths):
            split = "val" if idx < val_count else "train"
            dst = out_dir / split / label / src.name
            shutil.move(str(src), str(dst))

    tmp_dir = out_dir / "_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    def count(split: str, label: str) -> int:
        return len(list((out_dir / split / label).glob("*.jpg")))

    print("Dataset prepared:")
    print(f"  out_dir: {out_dir}")
    print(f"  train/open: {count('train','open')}")
    print(f"  train/closed: {count('train','closed')}")
    print(f"  val/open: {count('val','open')}")
    print(f"  val/closed: {count('val','closed')}")
    print(f"  skipped_missing_img: {skipped_missing_img}")
    print(f"  skipped_unknown_cls: {skipped_unknown_cls}")
    print(f"  skipped_focus: {skipped_focus}")
    print(f"  skipped_tiny: {skipped_tiny}")


if __name__ == "__main__":
    main()
