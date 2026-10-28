"""Generate an explicitly synthetic, non-surveillance demo video."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.video_io import find_binary  # noqa: E402


def draw_person(frame, x, y, carrying=False):
    color = (235, 235, 235)
    cv2.circle(frame, (x, y - 58), 13, color, -1)
    cv2.line(frame, (x, y - 45), (x, y), color, 8)
    cv2.line(frame, (x, y - 30), (x - 22, y - 10), color, 6)
    cv2.line(frame, (x, y - 30), (x + 22, y - 10), color, 6)
    cv2.line(frame, (x, y), (x - 18, y + 38), color, 7)
    cv2.line(frame, (x, y), (x + 18, y + 38), color, 7)
    if carrying:
        cv2.rectangle(frame, (x + 18, y - 28), (x + 72, y + 15), (42, 128, 210), -1)
        cv2.putText(frame, "BOX", (x + 25, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)


def make_frame(t: float):
    frame = np.full((360, 640, 3), (20, 25, 33), dtype=np.uint8)
    cv2.rectangle(frame, (35, 55), (605, 325), (43, 50, 61), -1)
    cv2.line(frame, (35, 285), (605, 285), (110, 120, 132), 2)
    cv2.rectangle(frame, (475, 105), (585, 285), (30, 65, 82), -1)
    cv2.putText(frame, "EMERGENCY EXIT", (460, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (0, 191, 255), 2)
    title = "CONTROLLED SYNTHETIC WORKSHOP VIDEO"
    if t < 2:
        scene = "People participating in a workshop"
        draw_person(frame, 160, 230)
        draw_person(frame, 275, 230)
        cv2.rectangle(frame, (105, 240), (325, 263), (90, 90, 100), -1)
    elif t < 4:
        scene = "A person carrying a cardboard box"
        draw_person(frame, 120 + round((t - 2) * 125), 230, carrying=True)
    elif t < 6:
        scene = "An object placed on the floor near an exit"
        draw_person(frame, 360, 230)
        cv2.rectangle(frame, (495, 235), (565, 285), (42, 128, 210), -1)
        cv2.putText(frame, "BOX", (512, 266), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    else:
        scene = "Clear emergency exit and empty walkway"
        draw_person(frame, 250, 230)
    cv2.putText(frame, title, (26, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (80, 220, 190), 2)
    cv2.putText(frame, scene, (45, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (240, 240, 240), 2)
    cv2.putText(frame, f"SYNTHETIC t={t:04.1f}s", (470, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (170, 180, 190), 1)
    return frame


def main():
    destination_dir = ROOT / "runtime" / "demo"
    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary = destination_dir / "visionguard_demo.avi"
    output = destination_dir / "visionguard_demo.mp4"
    fps, duration = 10, 8
    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 360))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not initialize demo VideoWriter")
    for index in range(fps * duration):
        writer.write(make_frame(index / fps))
    writer.release()
    command = [str(find_binary("ffmpeg")), "-y", "-i", str(temporary), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    temporary.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:])
    print(f"Synthetic demo: {output}")


if __name__ == "__main__":
    main()

