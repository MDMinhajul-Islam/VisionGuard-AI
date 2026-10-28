# 2–3 minute demo

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
