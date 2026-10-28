from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.database.models import (
    CandidateEvent, EmbeddingCache, ObjectDetection, PoseEvidence, ProcessingJob,
    SafetyZone, Video, VideoFrame, now_iso,
)
from app.database.session import SessionLocal
from app.services.video_io import iter_sampled_frames, probe_video, save_jpeg
from app.vision.clip_engine import clip_engine
from app.vision.fall_detection import detect_fall_events, pose_signals
from app.vision.object_detector import object_detector
from app.vision.obstruction_detection import ObstructionSample, detect_persistent_obstructions
from app.vision.pose_engine import pose_engine
from app.vision.tracker import IoUTracker


RELEVANT_LABELS = {"person", "backpack", "handbag", "suitcase", "chair", "bicycle", "car", "truck"}


def cleanup_partial_analysis(db, video: Video, frame_dir: Path) -> None:
    db.execute(delete(ObjectDetection).where(ObjectDetection.video_id == video.id))
    db.execute(delete(PoseEvidence).where(PoseEvidence.video_id == video.id))
    db.execute(delete(VideoFrame).where(VideoFrame.video_id == video.id))
    db.execute(delete(EmbeddingCache).where(EmbeddingCache.video_id == video.id))
    db.execute(delete(CandidateEvent).where(
        CandidateEvent.video_id == video.id,
        CandidateEvent.synthetic_fixture.is_(False),
        CandidateEvent.review_status == "pending",
    ))
    db.commit()
    if frame_dir.exists():
        shutil.rmtree(frame_dir)


def update_job(db, job, progress, stage, **fields):
    job.progress = min(100.0, max(0.0, progress))
    job.stage = stage
    for key, value in fields.items():
        setattr(job, key, value)
    db.commit()


def check_cancel(db, job):
    db.refresh(job)
    if job.cancel_requested:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.completed_at = now_iso()
        db.commit()
        raise InterruptedError("processing cancelled")


def process_video_job(job_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    job = db.get(ProcessingJob, job_id)
    if not job:
        db.close()
        return
    video = db.get(Video, job.video_id)
    config = json.loads(job.config_json)
    total_started = time.perf_counter()
    metrics = {}
    frame_dir = settings.frames_dir / video.id
    try:
        job.status = "running"
        job.started_at = now_iso()
        video.status = "processing"
        update_job(db, job, 2, "probing")
        metadata = probe_video(Path(video.path))
        for key in ("duration_seconds", "width", "height", "fps", "codec"):
            setattr(video, key, metadata[key])
        db.commit()

        db.execute(delete(ObjectDetection).where(ObjectDetection.video_id == video.id))
        db.execute(delete(PoseEvidence).where(PoseEvidence.video_id == video.id))
        db.execute(delete(VideoFrame).where(VideoFrame.video_id == video.id))
        db.execute(delete(EmbeddingCache).where(EmbeddingCache.video_id == video.id))
        db.execute(delete(CandidateEvent).where(CandidateEvent.video_id == video.id, CandidateEvent.synthetic_fixture.is_(False)))
        db.commit()
        if frame_dir.exists():
            shutil.rmtree(frame_dir)
        frame_dir.mkdir(parents=True)
        video.thumbnail_path = None
        db.commit()

        sample_fps = max(config["analysis_fps"], 1.0 / config["clip_sample_seconds"])
        update_job(db, job, 5, "extracting frames")
        extract_started = time.perf_counter()
        stored_frames = []
        for sampled in iter_sampled_frames(Path(video.path), sample_fps, config["process_width"]):
            check_cancel(db, job)
            frame = VideoFrame(
                video_id=video.id, timestamp_seconds=sampled.timestamp_seconds,
                frame_number=sampled.frame_number, path="", width=sampled.image.shape[1],
                height=sampled.image.shape[0], clip_indexed=False,
            )
            db.add(frame)
            db.flush()
            path = frame_dir / f"{frame.id}.jpg"
            save_jpeg(sampled.image, path)
            frame.path = str(path)
            stored_frames.append(frame)
            if video.thumbnail_path is None:
                video.thumbnail_path = str(path)
            if metadata["duration_seconds"]:
                progress = 5 + 20 * sampled.timestamp_seconds / metadata["duration_seconds"]
                if len(stored_frames) % 10 == 0:
                    update_job(db, job, progress, "extracting frames")
        db.commit()
        if not stored_frames:
            raise ValueError("no frames could be extracted")
        metrics["frames_extracted"] = len(stored_frames)
        metrics["frame_extraction_seconds"] = time.perf_counter() - extract_started

        if config.get("enable_clip", True):
            update_job(db, job, 28, "CLIP semantic indexing")
            selected = []
            last_clip_time = -1e9
            for frame in stored_frames:
                if frame.timestamp_seconds - last_clip_time + 1e-6 >= config["clip_sample_seconds"]:
                    selected.append(frame)
                    last_clip_time = frame.timestamp_seconds
            all_features = []
            clip_seconds = 0.0
            for offset in range(0, len(selected), 8):
                check_cancel(db, job)
                batch = selected[offset: offset + 8]
                images = [cv2.imread(item.path) for item in batch]
                features, elapsed = clip_engine.encode_images(images, batch_size=8)
                all_features.append(features)
                clip_seconds += elapsed
                for item in batch:
                    item.clip_indexed = True
                update_job(db, job, 28 + 17 * min(1, (offset + len(batch)) / len(selected)), "CLIP semantic indexing")
            feature_matrix = np.concatenate(all_features) if all_features else np.empty((0, 512), np.float32)
            cache_path = clip_engine.save_index(video.id, feature_matrix, [item.id for item in selected], [item.timestamp_seconds for item in selected])
            db.add(EmbeddingCache(video_id=video.id, path=str(cache_path), model_name=clip_engine.model_name, frame_count=len(selected), dimensions=512))
            db.commit()
            metrics.update({"clip_frames": len(selected), "clip_indexing_seconds": clip_seconds})
            clip_engine.unload()

        if config.get("enable_detection", True):
            update_job(db, job, 47, "object detection and tracking")
            tracker = IoUTracker(max_missed_frames=max(2, round(config["analysis_fps"] * 2)))
            detection_started = time.perf_counter()
            inference_times = []
            detection_count = 0
            for index, frame in enumerate(stored_frames):
                check_cancel(db, job)
                image = cv2.imread(frame.path)
                detections = object_detector.detect(image, config["detection_threshold"], RELEVANT_LABELS)
                detections = tracker.update(detections, frame.frame_number)
                if object_detector.last_inference_ms is not None:
                    inference_times.append(object_detector.last_inference_ms)
                for item in detections:
                    db.add(ObjectDetection(
                        video_id=video.id, frame_id=frame.id, timestamp_seconds=frame.timestamp_seconds,
                        label=item["label"], confidence=item["confidence"],
                        bbox_json=json.dumps(item["bbox"]), track_id=item["track_id"],
                    ))
                    detection_count += 1
                if index % 5 == 0:
                    update_job(db, job, 47 + 23 * (index + 1) / len(stored_frames), "object detection and tracking")
            db.commit()
            metrics.update({
                "object_detections": detection_count,
                "detection_seconds": time.perf_counter() - detection_started,
                "average_detector_inference_ms": sum(inference_times) / len(inference_times) if inference_times else None,
            })
            object_detector.unload()

        if config.get("enable_pose", True):
            update_job(db, job, 72, "pose estimation and temporal fall analysis")
            observations = []
            pose_times = []
            for index, sampled in enumerate(iter_sampled_frames(Path(video.path), config["pose_fps"], config["process_width"])):
                check_cancel(db, job)
                nearest = min(stored_frames, key=lambda item: abs(item.timestamp_seconds - sampled.timestamp_seconds))
                observation = pose_engine.process(sampled.image, round(sampled.timestamp_seconds * 1000), nearest.id)
                observations.append(observation)
                if pose_engine.last_inference_ms is not None:
                    pose_times.append(pose_engine.last_inference_ms)
                if index % 10 == 0 and metadata["duration_seconds"]:
                    update_job(db, job, 72 + 13 * sampled.timestamp_seconds / metadata["duration_seconds"], "pose estimation and temporal fall analysis")
                signals = pose_signals(observation, config["pose_confidence_threshold"])
                db.add(PoseEvidence(
                    video_id=video.id, frame_id=nearest.id,
                    timestamp_seconds=observation.timestamp,
                    frame_timestamp_seconds=nearest.timestamp_seconds,
                    sync_error_seconds=abs(observation.timestamp - nearest.timestamp_seconds),
                    landmarks_json=json.dumps(observation.landmarks),
                    signals_json=json.dumps(signals),
                    sufficient_evidence=signals["state"] != "unknown",
                ))
            db.commit()
            fall_thresholds = {
                "transition_window": config["fall_transition_window"],
                "min_vertical_drop": config["fall_min_vertical_drop"],
                "horizontal_persistence": config["fall_horizontal_persistence"],
                "confidence_threshold": config["pose_confidence_threshold"],
                "max_pose_gap": config["pose_max_gap"],
                "smoothing_window": config["pose_smoothing_window"],
                "event_merge_interval": config["event_merge_interval"],
                "profile_name": config["profile_name"],
            }
            fall_events = detect_fall_events(
                observations,
                transition_window=config["fall_transition_window"],
                min_vertical_drop=config["fall_min_vertical_drop"],
                horizontal_persistence=config["fall_horizontal_persistence"],
                confidence_threshold=config["pose_confidence_threshold"],
                max_pose_gap=config["pose_max_gap"],
                smoothing_window=config["pose_smoothing_window"],
                event_merge_interval=config["event_merge_interval"],
            )
            for event in fall_events:
                db.add(CandidateEvent(
                    video_id=video.id, event_type="potential_fall",
                    label="Potential Fall — Review Required", start_seconds=event.start_seconds,
                    end_seconds=event.end_seconds, processing_method="mediapipe_pose_temporal_heuristic",
                    model_version=pose_engine.model_name,
                    raw_scores_json=json.dumps({"heuristic_signal": event.confidence_signal, **event.evidence}),
                    thresholds_json=json.dumps(fall_thresholds),
                    supporting_frames_json=json.dumps(event.supporting_frames), review_status="pending",
                ))
            db.commit()
            metrics.update({
                "pose_frames": len(observations), "potential_fall_events": len(fall_events),
                "average_pose_inference_ms": sum(pose_times) / len(pose_times) if pose_times else None,
                "pose_frames_with_sufficient_evidence": sum(pose_signals(item, config["pose_confidence_threshold"])["state"] != "unknown" for item in observations),
            })
            pose_engine.close()

        update_job(db, job, 87, "zone obstruction analysis")
        zones = db.scalars(select(SafetyZone).where(SafetyZone.video_id == video.id)).all()
        detections = db.scalars(select(ObjectDetection).where(ObjectDetection.video_id == video.id)).all()
        obstruction_count = 0
        for zone in zones:
            polygon = json.loads(zone.polygon_json)
            samples = [ObstructionSample(item.timestamp_seconds, item.label, tuple(json.loads(item.bbox_json)), item.confidence, item.frame_id, item.track_id) for item in detections]
            obstruction_thresholds = {
                "min_zone_occupancy": config["zone_overlap_threshold"],
                "min_duration": config["obstruction_persistence"],
                "max_gap": config["obstruction_max_gap"],
                "event_merge_interval": config["event_merge_interval"],
                "profile_name": config["profile_name"],
            }
            events = detect_persistent_obstructions(
                samples, polygon,
                min_zone_occupancy=config["zone_overlap_threshold"],
                min_duration=config["obstruction_persistence"],
                max_gap=config["obstruction_max_gap"],
                event_merge_interval=config["event_merge_interval"],
            )
            for event in events:
                db.add(CandidateEvent(
                    video_id=video.id, event_type="potential_exit_obstruction" if zone.zone_type == "emergency_exit" else "potential_walkway_obstruction",
                    label="Potential Exit Obstruction — Review Required" if zone.zone_type == "emergency_exit" else "Potential Walkway Obstruction — Review Required",
                    start_seconds=event.start_seconds, end_seconds=event.end_seconds,
                    processing_method="manual_zone_bbox_persistence", model_version=object_detector.model_name,
                    raw_scores_json=json.dumps({
                        "zone_id": zone.id, "zone_name": zone.name, "zone_polygon": polygon,
                        "max_zone_occupancy": event.max_zone_occupancy, "labels": event.labels,
                        "contributing_detections": event.evidence,
                    }),
                    thresholds_json=json.dumps(obstruction_thresholds),
                    supporting_frames_json=json.dumps(event.supporting_frames), review_status="pending",
                ))
                obstruction_count += 1
        db.commit()
        metrics["potential_obstruction_events"] = obstruction_count
        metrics["total_processing_seconds"] = time.perf_counter() - total_started
        if __import__("torch").cuda.is_available():
            metrics["peak_gpu_memory_mib"] = __import__("torch").cuda.max_memory_allocated() / 2**20
        job.metrics_json = json.dumps(metrics)
        job.status = "completed"
        job.completed_at = now_iso()
        has_index = db.scalar(select(EmbeddingCache.id).where(EmbeddingCache.video_id == video.id)) is not None
        video.status = "indexed" if has_index else "processed"
        update_job(db, job, 100, "completed")
    except InterruptedError:
        cleanup_partial_analysis(db, video, frame_dir)
        video.status = "uploaded"
        db.commit()
    except Exception as error:
        job.status = "failed"
        job.error = f"{type(error).__name__}: {error}"[:2000]
        job.completed_at = now_iso()
        video.status = "failed"
        update_job(db, job, job.progress, "failed")
    finally:
        clip_engine.unload()
        object_detector.unload()
        pose_engine.close()
        db.close()
