"""Download a local FFmpeg/FFprobe build into ignored runtime storage."""
from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "runtime" / "tools"
ARCHIVE = TOOLS / "ffmpeg-release-essentials.zip"
URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip"


def main():
    if list(TOOLS.rglob("ffprobe.exe")) and list(TOOLS.rglob("ffmpeg.exe")):
        print("FFmpeg and FFprobe already available in runtime/tools")
        return
    TOOLS.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Windows FFmpeg essentials from {URL}")
    urllib.request.urlretrieve(URL, ARCHIVE)
    with zipfile.ZipFile(ARCHIVE) as bundle:
        bundle.extractall(TOOLS)
    ARCHIVE.unlink(missing_ok=True)
    ffmpeg = next(iter(TOOLS.rglob("ffmpeg.exe")), None)
    ffprobe = next(iter(TOOLS.rglob("ffprobe.exe")), None)
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Downloaded archive did not contain FFmpeg and FFprobe")
    print(f"FFmpeg: {ffmpeg}")
    print(f"FFprobe: {ffprobe}")


if __name__ == "__main__":
    main()

