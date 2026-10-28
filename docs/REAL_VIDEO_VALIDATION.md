# Real-video validation protocol and current status

## Status

**Blocked on data, not infrastructure.** The project contained only `visionguard_demo.mp4`, a generated vector-drawing fixture. No authorized staged fall video and no physical keep-clear obstruction video were available. No external surveillance footage was scraped or committed. Real safety-event metrics are therefore unmeasured.

## Annotation format

Ground truth is stored in `validation_annotations`, never in `candidate_events`. JSON manifests contain:

```json
{
  "dataset_name": "Consent-based staged validation set",
  "provenance": "How, where, and by whom the clips were produced",
  "license_or_consent": "Documented authorization or license",
  "exhaustive_annotations": true,
  "annotations": [{
    "video_id": "LOCAL_VIDEO_ID",
    "event_type": "potential_fall",
    "start_seconds": 4.2,
    "end_seconds": 6.8,
    "ground_truth_label": "positive",
    "annotation_source": "two-reviewer consensus",
    "reviewer_note": "Safely staged transition onto a crash mat",
    "query_text": null,
    "split": "evaluation"
  }]
}
```

Labels are `positive`, `negative`, `uncertain`, or `no_event`; splits are `development`, `calibration`, or `evaluation`. IDs are deterministic SHA-256-derived identifiers. The dashboard and import script enforce interval/query/video validation.

## Adding future clips

1. Obtain consent or confirm a compatible license. Never ask a participant to perform an unsafe fall; use professional/safe staging or existing appropriately licensed material.
2. Keep the original outside Git. Upload it through the local Video Workspace.
3. Record provenance, consent/license, camera conditions, and whether annotations are exhaustive.
4. Annotate in **Validation** or copy `validation/manifests/synthetic-demo.json` and import it with `--video-id`.
5. Put development/calibration and held-out clips in different splits before changing thresholds.
6. Process with a named profile, inspect overlays/pose gaps, then run `scripts/evaluate_validation.py`.
7. Inspect every false-positive and false-negative interval in Incident Review; do not report aggregate metrics without examples and dataset size.

No application code changes are needed to add local videos or manifests.

## Required cases

- Fall positives: safe staged upright-to-horizontal transition; safely staged transition followed by remaining down.
- Fall negatives: walking, sitting, crouching, bending, intentional lying; include occlusion/incomplete landmarks.
- Obstruction positives: supported COCO-detectable object remaining in the configured zone; passage obstruction for multiple seconds.
- Obstruction negatives: empty region, object outside, brief pass-through, immediate removal.
- Search: box carrying, chair by door, floor object, person walking, with timestamp intervals.

## Matching and metrics

Event matches are one-to-one at temporal IoU ≥ 0.3 or onset tolerance ≤ 1.0 s. Report TP, FP, FN, precision, recall, F1, signed delay, and absolute localization error. Hundreds of adjacent frames cannot become hundreds of true positives. Semantic search reports Precision@K, Recall@K, and timestamp error. Undefined denominators produce `null`.

## Current measured evidence

- Synthetic semantic intervals: Recall@3 1.00, Precision@3 0.333.
- Synthetic no-fall development interval: zero predictions, zero positive events; precision/recall/F1 undefined.
- Real single-image model execution: CLIP, SSDlite, and MediaPipe integration tests passed.
- Real staged fall/obstruction TP/FP/FN examples: none available.

These results do not establish physical event detection performance.
