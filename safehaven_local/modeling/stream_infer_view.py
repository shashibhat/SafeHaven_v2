#!/usr/bin/env python3
"""Live popup viewer for RTSP inference.

- detect mode: full-frame YOLO boxes (like test.py)
- classify mode: ROI box + state label/confidence
"""

from __future__ import annotations

import argparse
import os
import time

import cv2
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SafeHaven live stream inference viewer")
    parser.add_argument("--model", required=True, help="Path to model .pt")
    parser.add_argument("--stream", required=True, help="RTSP URL")
    parser.add_argument("--task", default="classify", choices=["classify", "detect"], help="Model task")
    parser.add_argument("--roi", default="0.72,0.35,0.12,0.20", help="ROI x,y,w,h normalized (for classify mode)")
    parser.add_argument("--unknown-threshold", type=float, default=0.55)
    parser.add_argument("--imgsz", type=int, default=224, help="classify imgsz")
    parser.add_argument("--detect-imgsz", type=int, default=960, help="detect/segment inference size")
    parser.add_argument("--conf", type=float, default=0.25, help="detect confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="detect IoU threshold")
    parser.add_argument("--classes", default="", help="Optional class filter, e.g. '0,1'")
    parser.add_argument("--device", default="mps", help="mps|cpu")
    parser.add_argument("--window", default="SafeHaven Live Inference")
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

        if args.task == "detect":
            cls_filter = None
            if args.classes.strip():
                cls_filter = [int(x.strip()) for x in args.classes.split(",") if x.strip()]
            results = model.predict(
                frame,
                task="detect",
                imgsz=args.detect_imgsz,
                conf=args.conf,
                iou=args.iou,
                classes=cls_filter,
                device=args.device,
                verbose=False,
            )
            if results:
                display = results[0].plot()
                top_text = ""
                if results[0].boxes is not None and len(results[0].boxes) > 0:
                    b = results[0].boxes
                    cls0 = int(b.cls[0].item())
                    conf0 = float(b.conf[0].item())
                    top_text = f"top={model.names.get(cls0, cls0)}:{conf0:.2f} n={len(b)}"
                if top_text:
                    cv2.putText(display, top_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            else:
                display = frame
        else:
            roi_frame, (x1, y1, x2, y2) = crop_roi(frame, roi)
            results = model.predict(roi_frame, task="classify", imgsz=args.imgsz, device=args.device, verbose=False)
            state_label = "unknown"
            conf = 0.0
            top2_text = ""
            if results:
                probs = results[0].probs
                top1 = int(probs.top1)
                conf = float(probs.top1conf.item())
                state_label = str(model.names[top1])
                if hasattr(probs, "top5") and hasattr(probs, "top5conf"):
                    names = []
                    for cls_id, cls_conf in zip(probs.top5[:2], probs.top5conf[:2]):
                        names.append(f"{model.names[int(cls_id)]}:{float(cls_conf):.2f}")
                    top2_text = " ".join(names)
                if conf < args.unknown_threshold:
                    state_label = "unknown"
            display = frame.copy()
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(
                display,
                f"state={state_label} conf={conf:.2f}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            if top2_text:
                cv2.putText(
                    display,
                    f"top={top2_text}",
                    (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

        now = time.time()
        dt = now - last
        last = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt)
        cv2.putText(display, f"fps={fps:.1f}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        cv2.imshow(args.window, display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
