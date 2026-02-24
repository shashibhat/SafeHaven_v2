#!/usr/bin/env python3
"""Suggest normalized ROI that covers target classes in existing YOLO labels."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Suggest focus ROI from YOLO labels")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--images-dir", default="", help="Optional image dir to include only labels with matching image stem")
    p.add_argument("--class-ids", default="0,1", help="Target class ids")
    p.add_argument("--pad", type=float, default=0.05, help="Padding ratio on all sides")
    p.add_argument("--lower-q", type=float, default=0.10, help="Lower quantile for robust bounds")
    p.add_argument("--upper-q", type=float, default=0.90, help="Upper quantile for robust bounds")
    return p.parse_args()


def line_to_xyxy(parts: list[float]) -> tuple[float, float, float, float] | None:
    coords = parts[1:]
    if len(coords) < 4:
        return None
    if len(coords) == 4:
        cx, cy, w, h = coords
        return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0
    xs = coords[0::2]
    ys = coords[1::2]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def clip01(v: float) -> float:
    return max(0.0, min(1.0, v))


def quantile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    xs = sorted(vals)
    pos = max(0, min(len(xs) - 1, int(round((len(xs) - 1) * q))))
    return xs[pos]


def main() -> None:
    args = parse_args()
    labels_dir = Path(args.labels_dir).expanduser().resolve()
    image_stems: set[str] | None = None
    if args.images_dir.strip():
        img_dir = Path(args.images_dir).expanduser().resolve()
        image_stems = {p.stem for p in img_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}}
    target = {int(x.strip()) for x in args.class_ids.split(",") if x.strip()}

    x1s, y1s, x2s, y2s = [], [], [], []
    count = 0
    for lp in sorted(labels_dir.glob("*.txt")):
        if image_stems is not None and lp.stem not in image_stems:
            continue
        for line in lp.read_text().splitlines():
            t = line.strip().split()
            if len(t) < 5:
                continue
            try:
                cls = int(float(t[0]))
                vals = [float(x) for x in t]
            except ValueError:
                continue
            if cls not in target:
                continue
            box = line_to_xyxy(vals)
            if box is None:
                continue
            x1, y1, x2, y2 = box
            x1s.append(x1)
            y1s.append(y1)
            x2s.append(x2)
            y2s.append(y2)
            count += 1

    if count == 0:
        raise RuntimeError("No matching labels found for target class ids")

    x1 = clip01(quantile(x1s, args.lower_q) - args.pad)
    y1 = clip01(quantile(y1s, args.lower_q) - args.pad)
    x2 = clip01(quantile(x2s, args.upper_q) + args.pad)
    y2 = clip01(quantile(y2s, args.upper_q) + args.pad)

    print(f"samples={count}")
    print(f"roi_x={x1:.4f}")
    print(f"roi_y={y1:.4f}")
    print(f"roi_w={x2 - x1:.4f}")
    print(f"roi_h={y2 - y1:.4f}")
    print(f"roi_csv={x1:.4f},{y1:.4f},{x2 - x1:.4f},{y2 - y1:.4f}")


if __name__ == "__main__":
    main()
