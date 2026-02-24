#!/usr/bin/env python3
"""Run real-time state classification on an RTSP stream ROI."""

from __future__ import annotations

import argparse
import os
import time

import cv2
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RTSP ROI state inference")
    parser.add_argument("--model", required=True, help="Path to classifier .pt")
    parser.add_argument("--stream", required=True, help="RTSP URL")
    parser.add_argument("--roi", default="0.0,0.0,1.0,1.0", help="x,y,w,h normalized")
    parser.add_argument("--device", default="mps", help="mps|cpu")
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--unknown-threshold", type=float, default=0.55)
    parser.add_argument("--window", default="SafeHaven ROI State")
    parser.add_argument("--rtsp-transport", default="tcp", choices=["tcp", "udp"], help="RTSP transport for OpenCV/FFmpeg")
    return parser.parse_args()


def crop_roi(frame, roi):
    h, w = frame.shape[:2]
    x, y, rw, rh = roi
    x1 = max(0, min(w - 1, int(x * w)))
    y1 = max(0, min(h - 1, int(y * h)))
    x2 = max(x1 + 1, min(w, int((x + rw) * w)))
    y2 = max(y1 + 1, min(h, int((y + rh) * h)))
    return frame[y1:y2, x1:x2], (x1, y1, x2, y2)


def main() -> None:
    args = parse_args()
    roi = tuple(float(v.strip()) for v in args.roi.split(","))
    if len(roi) != 4:
        raise ValueError("ROI must be x,y,w,h")

    model = YOLO(args.model)
    if args.stream.startswith("rtsp://"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{args.rtsp_transport}"
    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open stream: {args.stream}")

    last = time.time()
    fps = 0.0

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        roi_frame, (x1, y1, x2, y2) = crop_roi(frame, roi)
        results = model.predict(roi_frame, task="classify", imgsz=args.imgsz, device=args.device, verbose=False)

        state_label = "unknown"
        score = 0.0
        if results:
            probs = results[0].probs
            top1 = int(probs.top1)
            score = float(probs.top1conf.item())
            state_label = str(model.names[top1])
            if score < args.unknown_threshold:
                state_label = "unknown"

        now = time.time()
        dt = now - last
        last = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
        cv2.putText(
            frame,
            f"state={state_label} conf={score:.2f} fps={fps:.1f}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        cv2.imshow(args.window, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
