# Real-video fall evaluation

Run date: 2026-10-29. This is an exploratory baseline on a fixed 20-video UR Fall Detection subset, not evidence of operational safety reliability or population-level generalization.

## Protocol

- Ten source-labeled falls and ten source-labeled ADLs; fixed seed `20261028`.
- Actual VisionGuard pipeline: FFmpeg/OpenCV decoding, CLIP ViT-B/32 indexing, Torchvision SSDLite detection, MediaPipe Pose Landmarker Lite VIDEO inference, and the unchanged baseline temporal fall heuristic.
- A video prediction is positive when at least one non-synthetic `potential_fall` candidate is persisted.
- No threshold was tuned on these 20 evaluation videos.
- Temporal matching is greedy one-to-one: IoU >= 0.3 or onset error <= 1.0 second.

## Measured results

| Metric | Result |
|---|---:|
| Videos processed | 20 / 20 |
| TP / FP / TN / FN | 4 / 1 / 9 / 6 |
| Video-level precision | 0.800 |
| Video-level recall | 0.400 |
| Video-level F1 | 0.533 |
| Source-aligned temporal TP / FP / FN | 4 / 0 / 6 |
| Source-aligned temporal precision / recall / F1 | 1.000 / 0.400 / 0.571 |
| Mean matched onset delay / absolute error | 0.538 s / 0.538 s |

Temporal scores cover only the ten fall videos with mapped source intervals. They must not be read as a complete event-level false-alert rate across ADLs, and the source intervals are depth-posture-derived rather than independent RGB event annotations.

True positives were `fall-02`, `fall-07`, `fall-22`, and `fall-24`. False negatives were `fall-18`, `fall-19`, `fall-20`, `fall-23`, `fall-25`, and `fall-26`. The only video-level false positive was `adl-30`.

## Failure analysis

`adl-30` shows bending/leaning near a doorway with partially missing lower limbs. The stored event recorded vertical drop `0.1407`, torso change `16.18° -> 55.62°`, horizontal persistence `3.0 s`, and missing knee/ankle landmarks. This demonstrates that pose geometry can confuse bending/occlusion with a fall.

Several false negatives were still upright or transitional in the inspected sampled frame (`fall-19`, `fall-20`, `fall-23`, `fall-25`). `fall-26` was horizontal with three low-visibility landmarks, but horizontal posture alone correctly did not bypass the required transition/drop history. Local-only diagnostic original/overlay frames and evidence JSON are under `data/external/validation/reports/diagnostics/`; they are ignored to protect participant imagery.

## Performance

| Measurement | Actual result |
|---|---:|
| Source duration | 114.68 s |
| Total pipeline time | 103.19 s |
| Frames extracted / pose frames | 239 / 1,149 |
| Pose frames with sufficient evidence | 910 |
| Weighted mean pose inference | 12.29 ms/frame |
| CLIP indexing / detector time | 2.657 s / 20.340 s |
| Peak PyTorch GPU allocation | 370.25 MiB |

Hardware was an NVIDIA GeForce RTX 3050 Ti Laptop GPU (4 GiB), CUDA 12.8. Memory is the pipeline-reported PyTorch peak, not total system/GPU process memory.

## Remaining gaps

IKAR could not be acquired because its official host timed out. The UR subset is small and includes repeated capture conditions. Detailed activity labels are not assigned beyond what the source supports. A public, well-labeled physical doorway/walkway obstruction video set with clear compatible licensing was not readily identified; obstruction validation still requires authorized staged footage. No dataset media, participant images, database, weights, or caches are tracked by Git.
