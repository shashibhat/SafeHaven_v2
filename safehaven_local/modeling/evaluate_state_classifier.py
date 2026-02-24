#!/usr/bin/env python3
"""Evaluate a state classification model on classify dataset split.

Dataset format:
  data_dir/val/<class_name>/*.jpg
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from ultralytics import YOLO

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SafeHaven state classifier")
    parser.add_argument("--model", required=True, help="Path to classifier .pt")
    parser.add_argument("--data-dir", required=True, help="Classify dataset root")
    parser.add_argument("--split", default="val", choices=["train", "val"], help="Dataset split")
    parser.add_argument("--device", default="mps", help="mps|cpu")
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--unknown-threshold", type=float, default=0.55, help="Confidence threshold; below -> unknown")
    return parser.parse_args()


def collect_samples(split_dir: Path) -> list[tuple[Path, str]]:
    samples: list[tuple[Path, str]] = []
    for class_dir in sorted([p for p in split_dir.iterdir() if p.is_dir()]):
        for img in class_dir.rglob("*"):
            if img.suffix.lower() in IMG_EXTS:
                samples.append((img, class_dir.name))
    return samples


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    split_dir = data_dir / args.split
    if not split_dir.exists():
        raise FileNotFoundError(f"Split directory not found: {split_dir}")

    samples = collect_samples(split_dir)
    if not samples:
        raise RuntimeError(f"No images found under {split_dir}")

    model = YOLO(args.model)
    model_names = {int(k): v for k, v in model.names.items()} if isinstance(model.names, dict) else dict(enumerate(model.names))
    class_names = sorted({label for _, label in samples})
    if "unknown" not in class_names:
        class_names.append("unknown")

    cm: dict[str, dict[str, int]] = {gt: defaultdict(int) for gt in class_names}

    correct = 0
    for img_path, gt in samples:
        results = model.predict(str(img_path), task="classify", imgsz=args.imgsz, device=args.device, verbose=False)
        pred_label = "unknown"
        if results:
            probs = results[0].probs
            top1 = int(probs.top1)
            conf = float(probs.top1conf.item())
            candidate = str(model_names.get(top1, str(top1))).lower()
            if conf >= args.unknown_threshold:
                pred_label = candidate
        cm[gt][pred_label] += 1
        if pred_label == gt:
            correct += 1

    total = len(samples)
    acc = safe_div(correct, total)

    print(f"Model: {args.model}")
    print(f"Split: {args.split}")
    print(f"Samples: {total}")
    print(f"Accuracy: {acc:.4f}")
    print()

    print("Confusion Matrix (rows=gt, cols=pred)")
    header = ["gt\\pred"] + class_names
    print("\t".join(header))
    for gt in class_names:
        row = [gt] + [str(cm[gt].get(pred, 0)) for pred in class_names]
        print("\t".join(row))
    print()

    print("Per-class metrics")
    for cls in class_names:
        tp = cm[cls].get(cls, 0)
        fp = sum(cm[gt].get(cls, 0) for gt in class_names if gt != cls)
        fn = sum(cm[cls].get(pred, 0) for pred in class_names if pred != cls)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        support = sum(cm[cls].values())
        print(f"- {cls}: precision={precision:.4f} recall={recall:.4f} f1={f1:.4f} support={support}")


if __name__ == "__main__":
    main()
