"""Download the small MediaPipe pose model; other weights use official library loaders."""
from __future__ import annotations

import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
POSE_PATH = MODEL_DIR / "pose_landmarker_lite.task"
POSE_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not POSE_PATH.exists():
        print(f"Downloading MediaPipe Pose Landmarker Lite from {POSE_URL}")
        urllib.request.urlretrieve(POSE_URL, POSE_PATH)
    print(f"Pose model: {POSE_PATH} ({POSE_PATH.stat().st_size / 2**20:.1f} MiB)")
    print("CLIP and Torchvision detector weights are downloaded lazily by their official loaders.")


if __name__ == "__main__":
    main()

