import json
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database.models import CandidateEvent, DatasetAsset, ObjectDetection, PoseEvidence, SafetyZone, User, ValidationAnnotation, Video, VideoFrame
from app.database.session import SessionLocal
from app.main import app


@contextmanager
def authenticated_client(role="admin"):
    with TestClient(app) as client:
        email = f"{role}-{uuid4()}@test.local"
        password = "test-only-password-123!"
        db = SessionLocal()
        db.add(User(email=email, display_name=f"Test {role}", password_hash=hash_password(password), role=role))
        db.commit()
        db.close()
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        yield client


def test_health_and_empty_overview():
    with authenticated_client() as client:
        assert client.get("/api/health").status_code == 200
        overview = client.get("/api/overview").json()
        assert set(overview) == {"videos", "jobs", "indexed_videos", "candidate_events", "pending_review", "processing_failures"}


def test_upload_rejects_unsupported_extension():
    with authenticated_client() as client:
        response = client.post("/api/videos/upload", files={"file": ("unsafe.txt", b"not video", "text/plain")})
        assert response.status_code == 415


def test_zone_polygon_validation():
    with authenticated_client() as client:
        response = client.post("/api/videos/missing/zones", json={"name": "bad", "polygon": [[0, 0], [1, 1], [2, 2]]})
        assert response.status_code == 422


def test_human_review_update():
    db = SessionLocal()
    video = Video(id="v-test", original_filename="fixture.mp4", stored_filename="fixture.mp4", path="fixture.mp4", size_bytes=1, status="uploaded")
    event = CandidateEvent(
        id="e-test", video_id=video.id, event_type="synthetic_demo_fixture", label="Synthetic Fixture",
        start_seconds=0, end_seconds=1, processing_method="test", model_version="none",
        raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]", synthetic_fixture=True,
    )
    db.merge(video)
    db.merge(event)
    db.commit()
    db.close()
    with authenticated_client() as client:
        response = client.patch("/api/events/e-test/review", json={"status": "confirmed_by_reviewer", "reviewer_note": "Human reviewed synthetic fixture."})
        assert response.status_code == 200
        assert response.json()["review_status"] == "confirmed_by_reviewer"
        assert "Human reviewed" in response.json()["reviewer_note"]


def test_annotation_create_is_deterministic_and_evaluation_is_event_level():
    db = SessionLocal()
    video = Video(id="v-annotation", original_filename="authorized.mp4", stored_filename="authorized.mp4", path="authorized.mp4", size_bytes=1, duration_seconds=10, status="indexed")
    prediction = CandidateEvent(id="p-annotation", video_id=video.id, event_type="potential_fall", label="Potential Fall — Review Required", start_seconds=2.2, end_seconds=3.4, processing_method="test", model_version="test", raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]")
    db.merge(video); db.merge(prediction); db.commit(); db.close()
    payload = {"video_id": video.id, "event_type": "potential_fall", "start_seconds": 2, "end_seconds": 3.5, "ground_truth_label": "positive", "annotation_source": "authorized staged reviewer", "split": "evaluation"}
    with authenticated_client() as client:
        first = client.post("/api/validation/annotations", json=payload)
        second = client.post("/api/validation/annotations", json=payload)
        assert first.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        result = client.post(f"/api/videos/{video.id}/evaluate", json={"event_type": "potential_fall"}).json()
        assert result["true_positives"] == 1
        assert result["precision"] == 1


def test_reprocess_requires_explicit_override_when_reviewed_model_events_exist():
    db = SessionLocal()
    video = Video(id="v-reviewed", original_filename="reviewed.mp4", stored_filename="reviewed.mp4", path="reviewed.mp4", size_bytes=1, duration_seconds=5, status="indexed")
    event = CandidateEvent(id="e-reviewed", video_id=video.id, event_type="potential_fall", label="Potential Fall — Review Required", start_seconds=1, end_seconds=2, processing_method="test", model_version="test", raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]", review_status="false_positive", synthetic_fixture=False)
    db.merge(video); db.merge(event); db.commit(); db.close()
    with authenticated_client() as client:
        response = client.post(f"/api/videos/{video.id}/process", json={})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "reviewed_events_exist"


def test_frame_evidence_keeps_pose_sync_error_and_actual_detections_separate():
    db = SessionLocal()
    video = Video(id="v-evidence", original_filename="evidence.mp4", stored_filename="evidence.mp4", path="evidence.mp4", size_bytes=1, duration_seconds=5, status="indexed")
    frame = VideoFrame(id="f-evidence", video_id=video.id, timestamp_seconds=1.0, frame_number=25, path="unused.jpg", width=640, height=360)
    detection = ObjectDetection(id="d-evidence", video_id=video.id, frame_id=frame.id, timestamp_seconds=1.0, label="person", confidence=.91, bbox_json="[0.1,0.1,0.5,0.9]", track_id=3)
    pose = PoseEvidence(id="pose-evidence", video_id=video.id, frame_id=frame.id, timestamp_seconds=1.04, frame_timestamp_seconds=1.0, sync_error_seconds=.04, landmarks_json="[]", signals_json='{"state":"upright"}', sufficient_evidence=True)
    db.merge(video); db.merge(frame); db.merge(detection); db.merge(pose); db.commit(); db.close()
    with authenticated_client() as client:
        payload = client.get(f"/api/frames/{frame.id}/evidence").json()
        assert payload["detections"][0]["track_id"] == 3
        assert payload["pose_samples"][0]["sync_error_seconds"] == .04
        assert payload["pose_samples"][0]["signals"]["state"] == "upright"


def test_zone_reanalysis_preserves_reviewed_event_without_duplicate():
    db = SessionLocal()
    video = Video(id="v-zone-reviewed", original_filename="zone.mp4", stored_filename="zone-reviewed.mp4", path="zone.mp4", size_bytes=1, duration_seconds=5, status="indexed")
    zone = SafetyZone(id="z-reviewed", video_id=video.id, name="Exit", zone_type="emergency_exit", polygon_json="[[0.5,0.5],[0.9,0.5],[0.9,0.9],[0.5,0.9]]")
    reviewed = CandidateEvent(id="e-zone-reviewed", video_id=video.id, event_type="potential_exit_obstruction", label="Potential Exit Obstruction — Review Required", start_seconds=0, end_seconds=2, processing_method="test", model_version="test", raw_scores_json='{"zone_id":"z-reviewed"}', thresholds_json="{}", supporting_frames_json="[]", review_status="false_positive")
    db.merge(video); db.merge(zone); db.merge(reviewed)
    for index in range(3):
        frame = VideoFrame(id=f"zf-{index}", video_id=video.id, timestamp_seconds=float(index), frame_number=index, path="unused.jpg", width=640, height=360)
        detection = ObjectDetection(id=f"zd-{index}", video_id=video.id, frame_id=frame.id, timestamp_seconds=float(index), label="chair", confidence=.9, bbox_json="[0.55,0.55,0.8,0.8]", track_id=1)
        db.merge(frame); db.merge(detection)
    db.commit(); db.close()
    with authenticated_client() as client:
        response = client.post(f"/api/videos/{video.id}/zones/analyze", json={})
        assert response.status_code == 200
        assert response.json()["events_created"] == 0
    db = SessionLocal()
    assert db.get(CandidateEvent, reviewed.id).review_status == "false_positive"
    db.close()


def test_dataset_asset_registration_is_idempotent_and_video_metrics_are_real_predictions():
    db = SessionLocal()
    video = Video(id="v-dataset", original_filename="fall-01.mp4", stored_filename="dataset-fall-01.mp4", path="unused.mp4", size_bytes=1, duration_seconds=3, status="indexed")
    event = CandidateEvent(id="e-dataset", video_id=video.id, event_type="potential_fall", label="Potential Fall — Review Required", start_seconds=1, end_seconds=2, processing_method="pose_temporal_rules", model_version="test", raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]", synthetic_fixture=False)
    db.merge(video); db.merge(event); db.commit(); db.close()
    payload = {
        "video_id": video.id, "dataset_name": "Research Set", "original_recording_id": "fall-01",
        "evaluation_label": "fall", "source_url": "https://example.edu/dataset",
        "source_license": "research license", "annotation_status": "video_level_only",
        "manifest_record": {"prepared_sha256": "abc"},
    }
    with authenticated_client() as client:
        first = client.post("/api/datasets/assets", json=payload)
        second = client.post("/api/datasets/assets", json=payload)
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        result = client.get("/api/datasets/evaluation", params={"dataset_name": "Research Set", "completed_only": "false"}).json()
        assert result["metrics"]["true_positives"] == 1
        assert result["records"][0]["candidate_timestamps"] == [1.0]
        assert client.get("/api/datasets/evaluation", params={"cohort": "unknown"}).status_code == 422


def test_sensitive_routes_are_denied_without_authentication():
    with TestClient(app) as client:
        assert client.get("/api/videos").status_code == 401
        assert client.get("/api/videos/private/media").status_code == 401
        assert client.get("/api/frames/private/image").status_code == 401
        assert client.get("/api/exports/private/download").status_code == 401
        assert client.get("/api/datasets/evaluation").status_code == 401


def test_reviewer_is_read_review_export_role_not_administrator():
    with authenticated_client("reviewer") as client:
        assert client.get("/api/videos").status_code == 200
        assert client.post("/api/videos/missing/process", json={}).status_code == 403
        assert client.post("/api/videos/missing/zones", json={"name": "Exit", "polygon": [[0, 0], [1, 0], [1, 1]]}).status_code == 403
        assert client.post("/api/admin/users", json={"email": "new@test.local", "display_name": "New", "password": "long-test-password!", "role": "reviewer"}).status_code == 403


def test_login_sets_http_only_session_and_me_returns_minimal_user():
    with authenticated_client("reviewer") as client:
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["role"] == "reviewer"
        assert "password_hash" not in response.json()
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

