# Phase 1 evaluation

Run date: 2026-10-28. Machine: Windows, Python 3.10.9, PyTorch 2.11.0+cu128, RTX 3050 Ti Laptop GPU (4 GiB), CUDA available. Raw machine-readable results are in [`evaluations/latest_results.json`](../evaluations/latest_results.json).

## Test evidence

| Scope | Result | Evidence type |
|---|---:|---|
| Backend unit + API tests | 20 passed, 3 deselected | deterministic and mocked API fixtures |
| Real CLIP integration | passed | official ViT-B/32 image + text inference, 512-D finite normalized output |
| Real detector integration | passed | official Torchvision Grace Hopper image, person confidence 0.9977 |
| Real pose integration | passed | official MediaPipe pose image, shoulder/hip visibility 0.9974 |
| Next.js production build | passed | TypeScript and route prerender build |
| Chromium UI smoke test | 1 passed | Playwright, live frontend/backend/database |

## Synthetic demo processing

The generated 8.0-second, 640×360 H.264 clip has four visibly labeled vector-drawn scenes. It is suitable for plumbing and retrieval, not safety accuracy.

| Measurement | Actual result |
|---|---:|
| Total processing | 6.501 s |
| Frame extraction | 16 frames / 0.126 s |
| CLIP indexing | 8 frames / 0.328 s |
| Object analysis | 12 stored detections / 1.579 s |
| Detector inference mean | 76.27 ms per sampled frame |
| Pose analysis | 40 frames / 10.43 ms mean inference |
| Sufficient synthetic pose frames | 0 (expected for drawings) |
| Model-generated fall/obstruction events | 0 / 0 |
| Peak pipeline PyTorch allocation | 368.20 MiB |

## Semantic retrieval

Ground truth is the generator's four two-second scene intervals. With four queries, top-3 and 1.5-second suppression, every intended interval appeared in top 3: interval recall@3 = **1.00**; mean Precision@3 = **0.333**. First query incurred a 2699.7 ms lazy model load; subsequent queries took 9.7–12.0 ms. Mean including cold start was 682.9 ms. Similarities ranged around 0.21–0.30 and are not calibrated probabilities.

## Export

FFmpeg re-encoded a requested 2.5-second event segment in 0.074 s. Source hash preservation was covered by implementation and the source file was not opened for writing.

## What was not evaluated

No authorized staged fall or physical exit-obstruction video was available. Therefore event precision, recall, false-alert rate, timing error, and operational reliability are **unmeasured**. Deterministic state-machine/geometry tests and separate real pose/detector inference do not establish end-to-end safety performance. Object-detection mAP was not recomputed; no labeled detection dataset was introduced. Previous CLIP CIFAR-10 numbers are intentionally excluded.
