import cv2
import numpy as np

OUT = "./demo.mp4"
W, H = 640, 360
FPS = 5
SECONDS = 30

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(OUT, fourcc, FPS, (W, H))
for i in range(FPS * SECONDS):
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    frame[:] = (25, 25, 25)
    cv2.putText(frame, f"SafeHaven Demo t={i/FPS:0.1f}s", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    # Simulate changing zone visuals
    garage_open = (i // FPS) % 12 < 8
    gate_ajar = (i // FPS) % 10 < 5
    latch_unlocked = (i // FPS) % 14 < 9

    cv2.rectangle(frame, (40, 90), (220, 300), (0, 255, 0) if garage_open else (0, 0, 255), 3)
    cv2.putText(frame, f"garage {'OPEN' if garage_open else 'CLOSED'}", (45, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 2)

    cv2.rectangle(frame, (250, 90), (410, 300), (0, 255, 0) if gate_ajar else (0, 0, 255), 3)
    cv2.putText(frame, f"gate {'AJAR' if gate_ajar else 'CLOSED'}", (250, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 2)

    cv2.rectangle(frame, (440, 90), (600, 300), (0, 255, 0) if latch_unlocked else (0, 0, 255), 3)
    cv2.putText(frame, f"latch {'UNLOCKED' if latch_unlocked else 'LOCKED'}", (420, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 2)

    writer.write(frame)

writer.release()
print(f"Wrote {OUT}")
