#!/usr/bin/env python3
"""Interactive ROI calibration from live RTSP stream.

Press:
- s: select ROI on current frame
- c: clear ROI
- q: quit
"""

from __future__ import annotations

import argparse
import os

import cv2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Calibrate normalized ROI from RTSP")
    p.add_argument("--stream", required=True, help="RTSP URL")
    p.add_argument("--window", default="SafeHaven ROI Calibrator")
    p.add_argument("--rtsp-transport", default="tcp", choices=["tcp", "udp"], help="RTSP transport for OpenCV/FFmpeg")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.stream.startswith("rtsp://"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{args.rtsp_transport}"
    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open stream: {args.stream}")

    roi = None
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        h, w = frame.shape[:2]
        display = frame.copy()

        if roi is not None:
            x, y, rw, rh = roi
            x1 = int(x * w)
            y1 = int(y * h)
            x2 = int((x + rw) * w)
            y2 = int((y + rh) * h)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                display,
                f"roi={x:.4f},{y:.4f},{rw:.4f},{rh:.4f}",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

        cv2.putText(display, "Press s=select ROI, c=clear, q=quit", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
        cv2.imshow(args.window, display)

        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k == ord("c"):
            roi = None
            continue
        if k == ord("s"):
            r = cv2.selectROI(args.window, frame, fromCenter=False, showCrosshair=True)
            x, y, bw, bh = r
            if bw > 0 and bh > 0:
                roi = (x / w, y / h, bw / w, bh / h)
                print(f"ROI_CSV={roi[0]:.4f},{roi[1]:.4f},{roi[2]:.4f},{roi[3]:.4f}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
