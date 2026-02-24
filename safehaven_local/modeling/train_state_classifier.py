#!/usr/bin/env python3
"""Train a zone state classifier for SafeHaven on macOS.

Expected dataset layout (Ultralytics classify):

dataset_root/
  train/
    open/
    closed/
  val/
    open/
    closed/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train SafeHaven state classifier")
    parser.add_argument("--data-dir", required=True, help="Path to classify dataset root")
    parser.add_argument("--model", default="yolov8m-cls.pt", help="Base classifier model")
    parser.add_argument("--imgsz", type=int, default=224, help="Image size")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs")
    parser.add_argument("--batch", type=int, default=32, help="Batch size")
    parser.add_argument("--device", default="mps", help="mps|cpu|0")
    parser.add_argument("--project", default="runs/safehaven_cls", help="Output project dir")
    parser.add_argument("--name", default="state_model", help="Run name")
    return parser.parse_args()


def validate_dataset(data_dir: Path) -> None:
    required = [
        data_dir / "train" / "open",
        data_dir / "train" / "closed",
        data_dir / "val" / "open",
        data_dir / "val" / "closed",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Dataset is missing required class folders. Missing:\n" + "\n".join(missing)
        )


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    validate_dataset(data_dir)

    model = YOLO(args.model)
    model.train(
        task="classify",
        data=str(data_dir),
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        pretrained=True,
    )

    run_dir = Path(args.project) / args.name / "weights"
    print(f"Training finished. Best model: {run_dir / 'best.pt'}")


if __name__ == "__main__":
    main()
