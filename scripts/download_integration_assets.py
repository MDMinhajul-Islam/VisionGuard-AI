"""Download official project-owned test assets into ignored runtime storage."""
from __future__ import annotations

import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "runtime" / "integration_assets"
FILES = {
    "mediapipe_pose.jpg": "https://storage.googleapis.com/mediapipe-assets/pose.jpg",
    "torchvision_grace_hopper.jpg": "https://raw.githubusercontent.com/pytorch/vision/main/test/assets/encode_jpeg/grace_hopper_517x606.jpg",
}


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        path = ASSETS / name
        if not path.exists():
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, path)
        print(f"{name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
