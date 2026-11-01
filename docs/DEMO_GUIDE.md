# 2–3 minute demo

## Synchronized video-analysis workflow

1. Sign in at `http://127.0.0.1:3000/login`, choose the authorized organization/site, and open **Video Workspace**.
2. Select **Open Analysis** on a processed recording. The original MP4—not a thumbnail sequence—loads in the analysis workspace.
3. Play and seek. Point out the box canvas moving with presented video timestamps and the HUD showing the real analysis sampling rate.
4. Toggle **Boxes**, **Track IDs**, **Pose**, and **Zones** independently. Use previous/next sample controls to inspect the exact stored observations.
5. Read the provenance strip: the default runtime is **SSDLite320 MobileNetV3 Large / COCO_V1**, not YOLO. State that similarity/confidence is model output, not a calibrated safety probability.
6. Select an event marker when available. It seeks to the candidate start and preserves its pending/human-review status.
7. Open **Incident Review**, record an explicit reviewer decision and note, then export a bounded clip if authorized.

For the local verified example, `fall-18.mp4` contains five samples at 2 FPS and the initial sample contains four genuine stored detections. The clip has no generated event candidate; do not imply otherwise. Screenshots containing research participants remain local in ignored `data/external/validation/reports/`.

## Phase 2 profile comparison

1. Open `http://127.0.0.1:3000/datasets` and select one of the ten Phase 2 recordings listed in `docs/PHASE2_GENERALIZATION.md`.
2. Compare baseline, shape-gated, and motion-fusion candidate markers without changing thresholds.
3. Inspect the synchronized landmark bounding-box center chart, torso/aspect signals, missing-pose state, and raw threshold block.
4. Select `fall-29` to show the honest remaining false negative: 25/34 sufficient samples, weak measured orientation/drop evidence.
5. State that 4 TP / 0 FP / 5 TN / 1 FN is a ten-video exploratory result with wide Wilson intervals, not an operational claim.
6. For an authorized staged doorway recording, use the command in `docs/OBSTRUCTION_VALIDATION.md`; real obstruction accuracy is still incomplete.

## Real-dataset workflow

1. Start FastAPI and Next.js with the README commands, then open `http://127.0.0.1:3000/datasets`.
2. Show the source/license boundary, 10 fall + 10 non-fall counts, and actual 4 TP / 1 FP / 9 TN / 6 FN confusion matrix.
3. Click `fall-02`. Play the locally served imported MP4 and use its event-timestamp button to seek to the real model candidate.
4. Contrast `adl-30` (false positive) with a missed fall such as `fall-26`. State that predictions, source labels, and human review are separate records.
5. Export the evaluation JSON. Show `docs/REAL_VIDEO_EVALUATION.md` for timing, failure analysis, and annotation caveats.

Dataset media and diagnostic participant frames remain local under ignored `data/external/`. Do not publish or screen-share them without checking the dataset license and participant/privacy context.

## Synthetic plumbing workflow

1. Start FastAPI on `127.0.0.1:8000` and Next.js on `127.0.0.1:3000` using the README commands.
2. If the library is empty, run `generate_demo.py`, `seed_demo.py`, and `process_demo.py`. State aloud that the clip is synthetic and the review event is a fixture, not model output.
3. Open **Video Workspace**. Show FFprobe metadata, indexed status, processing controls, playback, and extracted frames.
4. Open **Semantic Search**. Choose the demo, search `Someone carrying a cardboard box.`, and click the leading 3-second result to seek the source video. Explain that 0.2658 is an uncalibrated similarity.
5. Open **Industrial Safety**. Show real COCO detection overlays and the manual normalized keep-clear rectangle. Save/analyze it; a zero model-event result is valid for this drawn fixture.
6. Open **Incident Review**. Select the item labeled `SYNTHETIC / NOT MODEL EVIDENCE`. Step through original/combined-overlay frames; point out actual detector boxes, manual zone geometry, raw pose `unknown` state, synchronization error, triggering rules, and the unchanged human review controls. Export the 2.5-second MP4.
7. Open **Validation**. Show that ground truth is separate from predictions, select the development split, and run one-to-one event evaluation. Explain why precision/recall/F1 are undefined with no positive falls.
8. Open **Models & System**. Show the backend-reported CUDA device, model versions/resources, and limitations.

Screenshots captured by the actual Chromium test are in `docs/images/`. They are screenshots, not a claimed screen recording.

For a real uploaded MP4, use short authorized 720p footage, process sequentially, and wait for job completion. Do not describe fall or obstruction output as confirmed. Without consented staged footage, demonstrate only the separately verified pose/detector integrations and deterministic temporal rules described in the evaluation.
