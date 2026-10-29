from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.datasets.io import file_hash, safe_extract_zip, write_json
from app.datasets.manifest import PreparedManifest, PreparedVideo
from app.services.video_io import find_binary


DATA_ROOT = PROJECT_ROOT / "data" / "external"
UR_ROOT = DATA_ROOT / "ur_fall"
UR_PAGE = "https://fenix.ur.edu.pl/~mkepski/ds/uf.html"
UR_LICENSE = "CC BY-NC-SA 4.0; non-commercial academic use"


def read_sync(path: Path) -> dict[int, float]:
    timestamps: dict[int, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if len(row) < 2:
                continue
            try:
                frame_number, timestamp_ms = int(row[0]), float(row[1])
            except ValueError:
                continue
            timestamps[frame_number] = timestamp_ms / 1000.0
    if not timestamps:
        raise ValueError(f"no synchronization timestamps in {path}")
    values = list(timestamps.values())
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError(f"timestamps are not strictly increasing in {path}")
    return timestamps


def read_posture_labels(path: Path) -> dict[str, dict[int, int]]:
    labels: dict[str, dict[int, int]] = {}
    if not path.exists():
        return labels
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                continue
            try:
                frame_number, label = int(row[1]), int(row[2])
            except ValueError:
                continue
            labels.setdefault(row[0].strip(), {})[frame_number] = label
    return labels


def ffprobe(path: Path) -> dict:
    command = [
        str(find_binary("ffprobe")), "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,nb_read_frames:format=duration,size",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip()[:500])
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    numerator, denominator = stream.get("avg_frame_rate", "0/1").split("/")
    return {
        "duration_seconds": float(payload["format"]["duration"]),
        "width": int(stream["width"]), "height": int(stream["height"]),
        "fps": float(numerator) / float(denominator),
        "frame_count": int(stream.get("nb_read_frames") or 0),
        "codec": stream.get("codec_name"), "size_bytes": int(payload["format"].get("size") or path.stat().st_size),
    }


def build_concat(images: list[Path], timestamps: dict[int, float], path: Path) -> tuple[int, int]:
    ordered: list[tuple[Path, float]] = []
    for image in images:
        try:
            number = int(image.stem.rsplit("-", 1)[-1])
        except ValueError:
            continue
        if number in timestamps:
            ordered.append((image, timestamps[number]))
    ordered.sort(key=lambda item: item[1])
    if len(ordered) < 2:
        raise ValueError("fewer than two synchronized RGB frames")
    median_delta = sorted(right[1] - left[1] for left, right in zip(ordered, ordered[1:]))[len(ordered) // 2 - 1]
    lines: list[str] = []
    for index, (image, timestamp) in enumerate(ordered):
        escaped = image.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        duration = ordered[index + 1][1] - timestamp if index + 1 < len(ordered) else median_delta
        lines.append(f"duration {duration:.9f}")
    lines.append(f"file '{ordered[-1][0].resolve().as_posix()}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(ordered), len(images) - len(ordered)


def source_intervals(sequence: str, timestamps: dict[int, float], labels: dict[str, dict[int, int]]) -> list[dict]:
    if not sequence.startswith("fall-"):
        return []
    sequence_labels = labels.get(sequence, {})
    transition = [frame for frame, label in sequence_labels.items() if label == 0 and frame in timestamps]
    if not transition:
        return []
    deltas = [right - left for left, right in zip(timestamps.values(), list(timestamps.values())[1:])]
    frame_duration = sorted(deltas)[len(deltas) // 2] if deltas else 1 / 30
    return [{
        "event_type": "potential_fall", "start_seconds": timestamps[min(transition)],
        "end_seconds": timestamps[max(transition)] + frame_duration, "ground_truth_label": "positive",
        "annotation_source": "UR official cam0 depth posture table; label 0 (temporary/falling posture)",
        "source_frame_start": min(transition), "source_frame_end": max(transition),
        "note": "Source labels describe depth-frame posture; timing is mapped through the official cam0 synchronization CSV.",
    }]


def prepare_ur() -> Path:
    download_manifest_path = UR_ROOT / "download_manifest.json"
    download_manifest = json.loads(download_manifest_path.read_text(encoding="utf-8"))
    raw_root, prepared_root = UR_ROOT / "raw", UR_ROOT / "prepared"
    annotations_root = DATA_ROOT / "validation" / "annotations"
    reports_root = DATA_ROOT / "validation" / "reports"
    labels = {}
    labels.update(read_posture_labels(UR_ROOT / "archives" / "urfall-cam0-falls.csv"))
    labels.update(read_posture_labels(UR_ROOT / "archives" / "urfall-cam0-adls.csv"))
    records: list[PreparedVideo] = []
    conversion_report = []
    source_annotations = []
    for item in download_manifest["records"]:
        sequence = item["sequence_id"]
        archive_info = next(file for file in item["files"] if file["filename"].endswith("rgb.zip"))
        sync_info = next(file for file in item["files"] if file["filename"].endswith("data.csv"))
        archive = UR_ROOT / "archives" / archive_info["filename"]
        sync_path = UR_ROOT / "archives" / sync_info["filename"]
        extract_root = raw_root / sequence
        images = sorted(extract_root.rglob("*.png")) if extract_root.exists() else []
        if not images:
            images = sorted(path for path in safe_extract_zip(archive, extract_root) if path.suffix.lower() == ".png")
        timestamps = read_sync(sync_path)
        concat_path = extract_root / "frames.ffconcat"
        synchronized, missing_timing = build_concat(images, timestamps, concat_path)
        output = prepared_root / f"{sequence}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(find_binary("ffmpeg")), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-fps_mode", "vfr", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(output),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if result.returncode:
            raise RuntimeError(f"FFmpeg failed for {sequence}: {result.stderr.strip()[:500]}")
        probe = ffprobe(output)
        if probe["codec"] != "h264" or probe["frame_count"] <= 0 or probe["duration_seconds"] <= 0:
            raise ValueError(f"invalid prepared output: {output}")
        intervals = source_intervals(sequence, timestamps, labels)
        source_annotations.extend({"record_id": f"ur-{sequence}", **interval} for interval in intervals)
        record = PreparedVideo(
            record_id=f"ur-{sequence}", source_dataset="UR Fall Detection",
            original_recording_id=sequence, prepared_video_path=output.relative_to(PROJECT_ROOT).as_posix(),
            original_label="fall sequence" if item["evaluation_label"] == "fall" else "activity of daily living sequence",
            evaluation_label=item["evaluation_label"], detailed_label=None,
            duration_seconds=probe["duration_seconds"], width=probe["width"], height=probe["height"],
            fps=probe["fps"], frame_count=probe["frame_count"], conversion_status="converted",
            annotation_status="source_frame_labels" if intervals else "video_level_only",
            source_url=UR_PAGE, source_license=UR_LICENSE,
            source_archive_sha256=archive_info["sha256"], prepared_sha256=file_hash(output),
            timing_source="official per-frame cam0 synchronization CSV", split="evaluation",
        )
        records.append(record)
        conversion_report.append({
            "record_id": record.record_id, "status": "converted", "input_frames": len(images),
            "synchronized_frames": synchronized, "frames_missing_timestamps": missing_timing,
            "output": record.prepared_video_path, **probe,
        })
        print(f"Prepared {sequence}: {probe['duration_seconds']:.2f}s, {probe['frame_count']} frames")
    created_at = datetime.now(timezone.utc).isoformat()
    manifest = PreparedManifest(
        dataset_name="UR Fall Detection balanced RGB subset", seed=download_manifest["seed"],
        created_at=created_at, records=records,
    )
    manifest_path = DATA_ROOT / "validation" / "manifests" / "ur-balanced-20.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))
    write_json(annotations_root / "ur-source-temporal-labels.json", {
        "schema_version": "1.0", "created_at": created_at, "annotations": source_annotations,
    })
    write_json(reports_root / "ur-conversion-report.json", {
        "created_at": created_at, "records": conversion_report,
    })
    print(f"Wrote prepared manifest: {manifest_path}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely extract and convert downloaded research videos.")
    parser.add_argument("--dataset", choices=["ur"], default="ur")
    args = parser.parse_args()
    if args.dataset == "ur":
        prepare_ur()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
