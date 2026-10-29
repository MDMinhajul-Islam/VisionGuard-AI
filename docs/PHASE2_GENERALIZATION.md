# Phase 2 Generalization Evaluation

## Protocol

VisionGuard Phase 2 uses ten previously unseen UR Fall Detection RGB sequences. Selection was deterministic (`seed=20262034`) and had no recording-ID overlap with the original twenty-video development collection.

- Falls: `fall-04`, `fall-06`, `fall-09`, `fall-16`, `fall-29`
- Non-falls: `adl-08`, `adl-09`, `adl-20`, `adl-23`, `adl-31`
- Local manifest: `data/external/validation/manifests/ur-phase2-heldout-10.json`
- Source: University of Rzeszow UR Fall Detection Dataset
- License: CC BY-NC-SA 4.0; non-commercial research use
- Timing: official camera-0 synchronization CSV, 25 FPS conversions

The baseline and shape-gated profiles were frozen before any Phase 2 result was inspected. Motion-fusion thresholds were developed only on the original twenty videos, then evaluated once on the independent ten. Participant identifiers are not exposed by the downloaded sequence names or metadata, so participant-disjoint independence cannot be verified. This is recording-disjoint evaluation, not population-level validation.

## Results

These are video-level results. Each video contributes one fall/non-fall decision. They are not frame-level or event-timestamp accuracy.

| Frozen profile | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 2 | 0 | 5 | 3 | 1.000 | 0.400 | 0.571 |
| Shape-gated | 3 | 0 | 5 | 2 | 1.000 | 0.600 | 0.750 |
| Motion fusion | 4 | 0 | 5 | 1 | 1.000 | 0.800 | 0.889 |

Wilson 95% intervals expose the uncertainty from the small sample:

| Profile | Precision interval | Recall interval | False-alert-rate interval |
|---|---|---|---|
| Baseline | 0.342–1.000 | 0.118–0.769 | 0.000–0.434 |
| Shape-gated | 0.438–1.000 | 0.231–0.882 | 0.000–0.434 |
| Motion fusion | 0.510–1.000 | 0.376–0.964 | 0.000–0.434 |

Original-development and independent results remain separate in their reports and must not be pooled into a headline score.

The pre-motion-fusion frozen replay is preserved in `evaluations/phase2_frozen_profile_evaluation.json`; the subsequent one-time motion-fusion evaluation is in `evaluations/phase2_profile_evaluation.json`.

## Failure evidence

`fall-29` remains a false negative under motion fusion. Only 25/34 pose samples had sufficient evidence, maximum torso angle was 29.37 degrees, maximum aspect ratio was 0.84, and recent-upright vertical drop was 0.04. The transition was not represented as a confident horizontal/drop sequence. Lowering thresholds just for this clip would violate the frozen protocol and risk false positives.

## Measured processing performance

All ten videos passed real decoding, CLIP indexing, SSDLite object detection, and MediaPipe pose processing:

- Source video duration: 54.32 seconds
- End-to-end processing: 55.57 seconds total; 5.56 seconds/video mean
- Pose: 545 samples; 12.25 ms/sample mean of per-video means; 460 sufficient-evidence samples
- Detector: 225 detections; 67.03 ms/frame mean of per-video means
- CLIP: 61 indexed frames; 1.60 seconds total indexing time
- Peak PyTorch GPU allocation: 370.25 MiB
- Cached profile evaluation: about 0.008 seconds/profile

GPU memory is PyTorch allocated memory and omits some driver/runtime allocations. These measurements apply only to this laptop, configuration, and short clips.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_fall_profiles.py --manifest data\external\validation\manifests\ur-phase2-heldout-10.json --output data\external\validation\reports\phase2-full-diagnostics.json --tracked-output evaluations\phase2_profile_evaluation.json
```

This evaluation is exploratory. Five positive and five negative videos cannot establish operational safety reliability.
