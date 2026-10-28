import json

from fastapi.testclient import TestClient

from app.database.models import CandidateEvent, Video
from app.database.session import SessionLocal
from app.main import app


def test_health_and_empty_overview():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        overview = client.get("/api/overview").json()
        assert set(overview) == {"videos", "jobs", "indexed_videos", "candidate_events", "pending_review", "processing_failures"}


def test_upload_rejects_unsupported_extension():
    with TestClient(app) as client:
        response = client.post("/api/videos/upload", files={"file": ("unsafe.txt", b"not video", "text/plain")})
        assert response.status_code == 415


def test_zone_polygon_validation():
    with TestClient(app) as client:
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
    with TestClient(app) as client:
        response = client.patch("/api/events/e-test/review", json={"status": "confirmed_by_reviewer", "reviewer_note": "Human reviewed synthetic fixture."})
        assert response.status_code == 200
        assert response.json()["review_status"] == "confirmed_by_reviewer"
        assert "Human reviewed" in response.json()["reviewer_note"]

