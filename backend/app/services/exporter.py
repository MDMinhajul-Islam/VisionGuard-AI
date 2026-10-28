from __future__ import annotations

import subprocess
import time
from pathlib import Path

from app.core.config import get_settings
from app.services.video_io import find_binary, safe_within


def validate_clip_range(start: float, end: float, duration: float) -> None:
    if start < 0 or end <= start:
        raise ValueError("invalid clip time range")
    if end > duration + 0.05:
        raise ValueError("clip end exceeds video duration")
    if end - start > 300:
        raise ValueError("clip duration exceeds five-minute limit")


def export_clip(source: Path, destination: Path, start: float, end: float, duration: float) -> float:
    settings = get_settings()
    source = safe_within(source, settings.uploads_dir)
    destination = safe_within(destination, settings.exports_dir)
    validate_clip_range(start, end, duration)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(find_binary("ffmpeg")), "-y", "-ss", f"{start:.3f}", "-i", str(source),
        "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac",
        "-movflags", "+faststart", str(destination),
    ]
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, timeout=max(60, int((end - start) * 10)), check=False)
    if result.returncode != 0 or not destination.exists():
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg export failed: {result.stderr[-800:]}")
    return time.perf_counter() - started

