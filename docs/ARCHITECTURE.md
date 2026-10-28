# Architecture

## Boundaries

VisionGuard is a local modular monorepo: FastAPI owns validation, compute, metadata, and safe file delivery; Next.js is a client of the REST API. Large binaries never enter SQLite. Every filesystem lookup is derived from generated IDs and checked against an allowed runtime root.

```mermaid
sequenceDiagram
  actor User
  participant UI as Next.js
  participant API as FastAPI
  participant DB as SQLite
  participant Worker as Single local worker
  participant CV as CLIP / SSDlite / MediaPipe
  User->>UI: Upload authorized MP4
  UI->>API: POST /api/videos/upload
  API->>API: filename, size, decode, FFprobe validation
  API->>DB: Video metadata
  User->>UI: Start processing
  UI->>API: POST /api/videos/{id}/process
  API->>DB: queued job + frozen configuration
  API-->>Worker: enqueue job ID
  Worker->>CV: bounded sampled frames, sequential models
  Worker->>DB: frames, detections, tracks, candidates, metrics
  User->>UI: text query / review / export
  UI->>API: search, PATCH review, POST export
  API->>DB: normalized evidence and human decision
```

## Ingestion and jobs

Uploads accept `.mp4` with a bounded size (500 MiB default), sanitized generated filenames, FFprobe metadata, and an OpenCV decode check. The worker receives only a job ID; configuration is persisted as JSON. A single background thread keeps model memory and SQLite write contention bounded. Jobs expose queued/running/completed/failed/cancelled state, stage, progress, error, and measured metrics. This is reliable enough for local development but not durable if the Python process is terminated.

## Sampling and model scheduling

- CLIP uses low-frequency frames (`1.0 s` default).
- detection/tracking uses `2 FPS` by default.
- pose uses `5 FPS` by default; it is never reduced to a still-frame fall decision.
- frames are decoded sequentially at a configured width (640 default), not loaded as the full video.
- CLIP and detector execute sequentially and unload between stages to protect 4 GiB GPUs; MediaPipe runs through its own runtime.

CLIP embeddings are L2-normalized and stored in compressed NumPy arrays alongside frame IDs and timestamps. Search is a matrix dot product followed by temporal suppression.

## Safety event logic

The pose state machine requires an observed upright state, rapid hip descent, a horizontal torso/body signal, and persistence. Low visibility or missing landmarks is `unknown`, not a fall. Zone obstruction requires a manually defined normalized polygon, detector-box intersection, minimum zone occupancy, temporal persistence, gap tolerance, and event merging. Both create pending candidates only.

## Data model

`Video` owns `ProcessingJob`, `VideoFrame`, `ObjectDetection`, `SafetyZone`, `CandidateEvent`, `EmbeddingCache`, and `ExportedClip`. Candidate events persist raw signals, frozen thresholds, model version, supporting frame IDs, source method, synthetic-fixture provenance, review state, note, and timestamps. Foreign keys and frequently queried video/status/time fields are indexed.

## API contract

Primary routes are `/api/videos/upload`, `/api/videos`, `/api/videos/{id}/process`, `/api/jobs/{id}`, `/api/videos/{id}/search`, `/detections`, `/events`, `/zones`, `/api/events/{id}/review`, `/export`, `/api/system/info`, and `/api/health`. Pydantic bounds all user-controlled numeric/string values. FastAPI publishes the exact OpenAPI schema at local `/docs`.

## Export

Export validates `0 <= start < end <= duration`, enforces a maximum interval, resolves source/output beneath known roots, and passes an argument array directly to FFmpeg (never a shell string). It re-encodes H.264 for accurate boundaries and preserves the uploaded source.
