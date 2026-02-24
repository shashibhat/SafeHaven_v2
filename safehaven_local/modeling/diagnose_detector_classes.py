#!/usr/bin/env python3
"""Diagnose whether a detect model is emitting all expected classes on RTSP frames."""

from __future__ import annotations

import argparse
import collections
import os

import cv2
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnose detector class usage")
    p.add_argument("--model", required=True)
    p.add_argument("--stream", required=True)
    p.add_argument("--frames", type=int, default=300)
    p.add_argument("--device", default="mps")
    p.add_argument("--imgsz", type=int, default=1280)
    p.add_argument("--conf", type=float, default=0.05)
    p.add_argument("--iou", type=float, default=0.45)
    p.add_argument("--rtsp-transport", default="tcp", choices=["tcp", "udp"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.stream.startswith("rtsp://"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{args.rtsp_transport}"

    model = YOLO(args.model)
    print("model.names=", model.names)

    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open stream: {args.stream}")

    class_counts = collections.Counter()
    conf_sums = collections.Counter()
    processed = 0

    while processed < args.frames and cap.isOpened():
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        processed += 1

        results = model.predict(
            frame,
            task="detect",
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            device=args.device,
            verbose=False,
        )
        if not results:
            continue

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            continue

        for c, s in zip(boxes.cls.tolist(), boxes.conf.tolist()):
            cls_id = int(c)
            class_counts[cls_id] += 1
            conf_sums[cls_id] += float(s)

    cap.release()

    print(f"processed_frames={processed}")
    if not class_counts:
        print("No detections produced at this conf/imgsz setup.")
        return

    print("class detection summary:")
    for cls_id, cnt in class_counts.most_common():
        avg_conf = conf_sums[cls_id] / max(1, cnt)
        name = model.names.get(cls_id, str(cls_id)) if isinstance(model.names, dict) else str(cls_id)
        print(f"  class_id={cls_id} name={name} detections={cnt} avg_conf={avg_conf:.3f}")


if __name__ == "__main__":
    main()
