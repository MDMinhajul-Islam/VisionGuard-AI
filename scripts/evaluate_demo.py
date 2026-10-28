"""Produce actual, synthetic, and integration evidence without conflating them."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings  # noqa: E402
from app.database.models import CandidateEvent, EmbeddingCache, ProcessingJob, Video  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.exporter import export_clip  # noqa: E402
from app.vision.clip_engine import clip_engine  # noqa: E402
from app.vision.object_detector import object_detector  # noqa: E402
from app.vision.pose_engine import pose_engine  # noqa: E402


QUERIES = [
    ("People participating in a workshop.", (0, 2)),
    ("Someone carrying a cardboard box.", (2, 4)),
    ("An object placed on the floor near an exit.", (4, 6)),
    ("A clear emergency exit and empty walkway.", (6, 8)),
]


def main():
    settings = get_settings()
    db = SessionLocal()
    video = db.query(Video).filter(Video.is_demo.is_(True), Video.status == "indexed").first()
    if not video:
        raise RuntimeError("Process the synthetic demo first")
    cache = db.query(EmbeddingCache).filter(EmbeddingCache.video_id == video.id).one()
    query_results = []
    search_times = []
    for query, interval in QUERIES:
        started = time.perf_counter()
        matches = clip_engine.search(Path(cache.path), query, 3, 1.5)
        elapsed = time.perf_counter() - started
        search_times.append(elapsed)
        relevant = [interval[0] <= item["timestamp_seconds"] < interval[1] for item in matches]
        query_results.append({
            "query": query, "expected_synthetic_interval": interval,
            "top3": matches, "precision_at_3": sum(relevant) / len(matches),
            "interval_retrieved_at_3": any(relevant), "search_ms": elapsed * 1000,
        })

    grace = cv2.imread(str(settings.runtime_dir / "integration_assets" / "torchvision_grace_hopper.jpg"))
    detector_started = time.perf_counter()
    actual_detections = object_detector.detect(grace, threshold=.3)
    detector_elapsed = time.perf_counter() - detector_started
    pose_image = cv2.imread(str(settings.runtime_dir / "integration_assets" / "mediapipe_pose.jpg"))
    pose_started = time.perf_counter()
    observation = pose_engine.process(pose_image, 0)
    pose_elapsed = time.perf_counter() - pose_started
    pose_engine.close()

    fixture = db.query(CandidateEvent).filter(CandidateEvent.video_id == video.id, CandidateEvent.synthetic_fixture.is_(True)).first()
    export_path = settings.exports_dir / "evaluation-demo-clip.mp4"
    export_seconds = export_clip(Path(video.path), export_path, fixture.start_seconds, min(video.duration_seconds, fixture.end_seconds + .5), video.duration_seconds)
    latest_job = db.query(ProcessingJob).filter(ProcessingJob.video_id == video.id, ProcessingJob.status == "completed").order_by(ProcessingJob.completed_at.desc()).first()
    report = {
        "scope": {
            "demo_video": "synthetic generated fixture",
            "semantic_ground_truth": "text-labeled synthetic scene intervals",
            "safety_accuracy_claim": "none",
            "full_staged_fall_validation": False,
            "full_staged_exit_obstruction_validation": False,
        },
        "hardware": {
            "pytorch": torch.__version__, "cuda_available": torch.cuda.is_available(),
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "video": {
            "id": video.id, "duration_seconds": video.duration_seconds,
            "resolution": [video.width, video.height], "codec": video.codec,
        },
        "pipeline_metrics": json.loads(latest_job.metrics_json),
        "semantic_retrieval": {
            "queries": query_results,
            "mean_precision_at_3": sum(item["precision_at_3"] for item in query_results) / len(query_results),
            "interval_recall_at_3": sum(item["interval_retrieved_at_3"] for item in query_results) / len(query_results),
            "mean_search_ms": sum(search_times) / len(search_times) * 1000,
        },
        "real_model_integration": {
            "clip": "passed via index and query embeddings",
            "object_detector": {
                "passed": any(item["label"] == "person" for item in actual_detections),
                "inference_ms_including_loaded_call": detector_elapsed * 1000,
                "detections": [{"label": item["label"], "confidence": item["confidence"]} for item in actual_detections],
            },
            "pose": {
                "passed": observation.shoulder_center is not None and observation.hip_center is not None,
                "inference_ms": pose_elapsed * 1000, "visibility": observation.visibility,
            },
        },
        "export": {"seconds": export_seconds, "duration_seconds": min(video.duration_seconds, fixture.end_seconds + .5) - fixture.start_seconds},
        "gpu_peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20 if torch.cuda.is_available() else None,
    }
    output = ROOT / "evaluations" / "latest_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    db.close()


if __name__ == "__main__":
    main()
