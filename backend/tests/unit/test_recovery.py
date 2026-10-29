from app.core.config import get_settings
from app.database.models import CandidateEvent, ProcessingJob, Video, VideoFrame
from app.database.session import SessionLocal
from app.database.migrations import LEGACY_RESEARCH_ORG_ID, LEGACY_RESEARCH_SITE_ID
from app.workers.recovery import recover_processing_jobs


def test_interrupted_job_is_quarantined_and_review_record_is_preserved():
    video_id = "recovery-video"
    frame_dir = get_settings().frames_dir / video_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frame_dir / "partial.jpg"
    frame_path.write_bytes(b"partial")
    with SessionLocal() as db:
        db.merge(Video(id=video_id, organization_id=LEGACY_RESEARCH_ORG_ID, site_id=LEGACY_RESEARCH_SITE_ID, original_filename="authorized.mp4", stored_filename="recovery.mp4", path="source.mp4", size_bytes=1, status="processing"))
        db.merge(ProcessingJob(id="recovery-job", video_id=video_id, status="running", stage="object detection"))
        db.merge(VideoFrame(id="recovery-frame", video_id=video_id, timestamp_seconds=0, frame_number=0, path=str(frame_path), width=10, height=10))
        db.merge(CandidateEvent(id="reviewed-recovery-event", video_id=video_id, event_type="potential_fall", label="Potential Fall — Review Required", start_seconds=0, end_seconds=1, processing_method="test", model_version="test", raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]", review_status="false_positive"))
        db.commit()
    result = recover_processing_jobs()
    assert result["running_quarantined"] == 1
    with SessionLocal() as db:
        job = db.get(ProcessingJob, "recovery-job")
        assert job.status == "failed"
        assert job.stage == "interrupted_by_process_exit"
        assert db.get(VideoFrame, "recovery-frame") is None
        assert db.get(CandidateEvent, "reviewed-recovery-event").review_status == "false_positive"
    assert not frame_dir.exists()
