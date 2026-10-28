# Phase 1.5 implementation audit

## Verified defects fixed

| Area | Defect | Resolution |
|---|---|---|
| Pose evidence | Landmarks and derived signals were discarded | Persist all landmarks, missing indices, signals, timestamps, and sync error |
| Synchronization | Pose samples were mapped to a nearest frame without exposing the offset | Store both timestamps and absolute offset; render from a single frame evidence API |
| Fall continuity | Missing pose could allow wall-clock persistence to bridge a long gap | Long/unknown gaps reset the candidate and cannot advance persistence |
| Fall interval | Event ended when first emitted | Active event extends through continuing horizontal evidence |
| Explainability | Only one heuristic scalar was stored | Store trigger booleans, angles, aspect ratios, drop, persistence, visibility, missing indices, thresholds |
| Obstruction evidence | Contributor boxes/confidence/tracks/overlap were absent | Persist every contributing detection and zone geometry |
| Review consistency | Zone re-analysis deleted reviewed events | Delete only pending derived events and skip overlap with reviewed evidence |
| Reprocessing | Reviewed model events could be silently deleted | Reject by default unless explicit override is supplied |
| Cancellation | Partial analysis rows/files survived cancellation | Clean partial frames, detections, poses, index, and pending candidates |
| Processing state | CLIP-disabled processing still became `indexed` | Use `processed` unless an embedding cache exists |
| Thumbnail lifecycle | Reprocessing deleted the referenced frame but retained its thumbnail path | Reset and regenerate thumbnail provenance before frame replacement |
| Metrics | Empty-set precision/recall/F1 displayed as zero | Report undefined values as `null` with explicit names |
| UI evidence | Review exposed JSON but not synchronized visual evidence | Add original/overlay comparison, frame stepping, raw evidence, exact video seek |

## Reviewed and retained

Upload bounds, safe paths, FFprobe validation, sequential model loading, normalized CLIP search, COCO detector execution, temporary per-video tracking, human-only confirmation, and safe FFmpeg argument handling were retained rather than rewritten.

## Known gaps

OpenCV uses presentation timestamps when available and a monotonic FPS fallback otherwise; unusual variable-frame-rate files still require targeted validation. The IoU tracker can switch IDs after occlusion and is not identity tracking. The local worker is not process-crash durable. Most importantly, no real staged safety video was available.
