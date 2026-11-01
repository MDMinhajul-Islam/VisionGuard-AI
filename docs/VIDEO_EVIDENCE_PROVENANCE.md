# Video Evidence Provenance

## Source relationship

The analysis timeline is derived from database rows linked to the selected `Video` and its `VideoFrame` records. Each sample returns its frame ID, timestamp, genuine object detections, genuine stored pose observations, configured zones, and related event candidates. Media and frame URLs use storage identifiers and pass through server authorization; client paths are never accepted.

For the current default pipeline, object evidence is produced by Torchvision `SSDLite320 MobileNetV3 Large` with `COCO_V1` weights. Pose evidence is produced by `MediaPipe Pose Landmarker Lite`. Future processing jobs persist detector model and version in job metrics. Legacy rows are labeled with the known pipeline identity; they are not relabeled as YOLO or RF-DETR output.

## Protected API

`GET /api/videos/{video_id}/analysis-timeline` requires an authenticated administrator or reviewer, then performs explicit video-level authorization. PostgreSQL RLS remains the database backstop. The endpoint limits windows to 300 seconds and samples to 5,000, and returns no video binary in JSON.

Cross-organization requests receive `404`, matching the application's anti-enumeration behavior.

## Integrity and review

The player is read-only. Toggling or navigating overlays does not mutate evidence. Existing frame checksums, event relationships, review history, source media, and exports remain unchanged. Human review is the only path to `confirmed_by_reviewer`; an AI candidate is never presented as a confirmed incident.

Dataset participant imagery, source videos, generated screenshots, databases, embeddings, and model weights remain Git-ignored and local to the F drive.
