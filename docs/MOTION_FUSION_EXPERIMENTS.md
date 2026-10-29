# Motion Fusion Experiments

## Purpose

The existing heuristic could miss a staged fall when pose orientation appeared briefly but normalized torso drop was weak. Motion fusion adds temporal bounding-box evidence without training a model or substituting mock data.

## Current decision rule

For a recent upright-to-transition window, the research profile requires:

- recent upright pose within 1.5 seconds;
- landmark-derived bounding-box center drop of at least 0.10 frame height;
- bounding-box aspect-ratio change of at least 0.25;
- ending aspect ratio of at least 0.80; and
- pose confidence of at least 0.50.

The implementation is `backend/app/vision/motion_fusion.py`. It uses real MediaPipe landmarks already stored by VisionGuard. Missing landmarks produce insufficient evidence rather than a synthesized box.

`camera_compensated_flow()` is an experimental optical-flow diagnostic. Farneback flow estimates global motion from the median background vector and subtracts it before measuring subject motion. It is unit-tested against synthetic camera translation, but it is not part of the event decision. This prevents an unvalidated flow signal from silently changing alerts.

## Development and independent results

| Set | Videos | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original development set | 20 | 7 | 0 | 10 | 3 | 1.000 | 0.700 | 0.824 |
| Independent Phase 2 set | 10 | 4 | 0 | 5 | 1 | 1.000 | 0.800 | 0.889 |

Thresholds were fixed using the original twenty before the independent set was evaluated. The independent result has wide uncertainty and is not evidence of general deployment fitness.

## Explainability payload

The diagnostics API and Dataset Evaluation UI expose normalized landmark bounding-box center/size, aspect ratio, torso angle, vertical drop, recent-upright state, timestamps, thresholds, triggering conditions, evidence sufficiency, and all three profile timelines.

## Remaining failure modes

- Pose loss or an oblique viewpoint may prevent horizontal-shape evidence (`fall-29`).
- A slow intentional transition to the floor may meet geometry gates even though it is not a fall.
- Landmark boxes describe visible joints, not a tracked full-body segmentation.
- The rule does not model recovery, furniture support, or scene semantics.
- Optical flow is diagnostic only and still needs real camera-motion validation.

All results are **Potential Fall — Review Required** candidates. Human review remains mandatory.
