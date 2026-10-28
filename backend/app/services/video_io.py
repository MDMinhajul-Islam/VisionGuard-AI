from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2

from app.core.config import get_settings


SUPPORTED_EXTENSIONS = {".mp4", ".m4v", ".mov"}


def safe_within(path: Path, root: Path) -> Path:
    resolved, resolved_root = path.resolve(), root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("path escapes configured storage root")
    return resolved


def find_binary(name: str) -> Path:
    settings = get_settings()
    candidates = list(settings.tools_dir.rglob(f"{name}.exe"))
    if candidates:
        return candidates[0]
    from shutil import which
    system = which(name)
    if system:
        return Path(system)
    raise FileNotFoundError(f"{name} not found. Run scripts/setup_ffmpeg.py")


def parse_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    numerator, denominator = value.split("/")
    return float(numerator) / float(denominator)


def probe_video(path: Path) -> dict:
    settings = get_settings()
    path = safe_within(path, settings.uploads_dir)
    command = [
        str(find_binary("ffprobe")), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames:format=duration,size",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise ValueError(f"FFprobe could not decode video: {result.stderr.strip()[:500]}")
    payload = json.loads(result.stdout)
    if not payload.get("streams"):
        raise ValueError("video contains no decodable video stream")
    stream = payload["streams"][0]
    return {
        "duration_seconds": float(payload.get("format", {}).get("duration") or 0),
        "size_bytes": int(payload.get("format", {}).get("size") or path.stat().st_size),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": parse_rate(stream.get("avg_frame_rate")),
        "codec": stream.get("codec_name") or "unknown",
        "frame_count": int(stream.get("nb_frames") or 0),
    }


@dataclass
class SampledFrame:
    frame_number: int
    timestamp_seconds: float
    image: object


def iter_sampled_frames(path: Path, sample_fps: float, process_width: int):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("OpenCV could not open video")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    interval = 1.0 / sample_fps
    next_timestamp = 0.0
    frame_number = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_number / source_fps
            frame_number += 1
            if timestamp + 1e-6 < next_timestamp:
                continue
            next_timestamp += interval
            height, width = frame.shape[:2]
            if width > process_width:
                scale = process_width / width
                frame = cv2.resize(frame, (process_width, max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
            yield SampledFrame(frame_number - 1, timestamp, frame)
    finally:
        capture.release()


def save_jpeg(frame, path: Path, quality: int = 88) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, quality]):
        raise OSError(f"failed to write frame: {path}")


def render_overlay(frame, detections: list[dict], polygon=None):
    output = frame.copy()
    height, width = output.shape[:2]
    if polygon:
        points = [(round(x * width), round(y * height)) for x, y in polygon]
        cv2.polylines(output, [__import__("numpy").array(points)], True, (0, 191, 255), 3)
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox_pixels"]
        color = (34, 197, 94) if detection["label"] == "person" else (255, 153, 51)
        cv2.rectangle(output, (round(x1), round(y1)), (round(x2), round(y2)), color, 2)
        cv2.putText(output, f"{detection['label']} {detection['confidence']:.2f} T{detection.get('track_id', '-')}", (round(x1), max(18, round(y1) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return output

