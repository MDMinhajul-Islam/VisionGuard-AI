# Phase 1.5 evaluation

Run date: 2026-10-28. Machine: Windows, Python 3.10.9, PyTorch 2.11.0+cu128, RTX 3050 Ti Laptop GPU (4 GiB), CUDA available. Raw results are in [`evaluations/latest_results.json`](../evaluations/latest_results.json) and [`evaluations/phase1_5_synthetic_fall.json`](../evaluations/phase1_5_synthetic_fall.json).

## Verification

| Scope | Result | Evidence type |
|---|---:|---|
| Backend unit + API | 31 passed, 3 deselected | annotation, matching, rules, review consistency, evidence APIs |
| Real model integration | 3 passed | CLIP image/text, SSDlite detection, MediaPipe pose |
| Next.js production build | passed | TypeScript and nine prerendered routes |
| ESLint | passed | zero errors; five intentional local dynamic-image warnings |
| Chromium workflows | 2 passed | live DB/API, video decoding, overlays, frame stepping, validation |

## Latest controlled processing

The only available video is the project-authored 8.0-second, 640×360 H.264 vector-drawn fixture. It is valid for plumbing and semantic retrieval, not safety accuracy.

| Measurement | Actual result |
|---|---:|
| Total processing | 7.163 s |
| Frame extraction | 16 / 0.101 s |
| CLIP indexing | 8 / 0.355 s |
| Stored detector outputs | 12 / 1.542 s |
| Mean detector inference | 74.80 ms/frame |
| Pose frames | 40 |
| Mean pose inference | 10.63 ms/frame |
| Sufficient pose evidence | 0 (expected for drawings) |
| Model fall / obstruction events | 0 / 0 |
| Peak pipeline PyTorch allocation | 368.20 MiB |
| 2.5-second MP4 export | 0.087 s |

The separate real-image integration detected `person` on Torchvision's Grace Hopper fixture at confidence `0.9977`; MediaPipe returned shoulder/hip visibility `0.9974`. These checks prove execution, not video-event accuracy.

## Semantic retrieval

Four known synthetic scene intervals were queried at top-3 with temporal suppression. Interval Recall@3 was **1.00** and mean Precision@3 **0.333**. The cold first query took 2768.3 ms; warm queries took 10.8–15.3 ms. Mean including load was 702.4 ms. Similarity values are uncalibrated.

## Event evaluation semantics

Predictions and positive ground truth use greedy one-to-one matching. A pair matches at temporal IoU ≥ 0.3 or absolute onset error ≤ 1.0 second. Reported delay is `predicted_start - ground_truth_start`; localization error is its absolute value. Uncertain annotations are excluded. Splits are explicit.

The synthetic manifest declares `no_event` for falls and the model emitted no fall prediction. This is a successful deterministic no-alert case, but there are zero positive events. Therefore precision, recall, and F1 are correctly **undefined (`null`)**, not 0% or 100%. There are no empirical false-positive/false-negative safety examples because no real event dataset exists.

## Unmeasured

No consented/licensed staged fall or physical obstruction video was present. Fall/obstruction event precision, recall, F1, false alerts, missed events, delay, localization error, and generalization remain unmeasured. Deterministic sequences and separate real-model images cannot close this gap. CIFAR-10 results remain excluded.
