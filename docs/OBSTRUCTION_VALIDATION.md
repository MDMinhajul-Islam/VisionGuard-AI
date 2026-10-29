# Obstruction Validation

## Status

Keep-clear-zone geometry and persistence are implemented and covered by deterministic tests. No authorized physical doorway-obstruction recording was available during Phase 2, so real obstruction accuracy remains incomplete and no precision/recall claim is made.

## Staged validation protocol

Record a safe, authorized short clip with a static camera:

1. Keep the marked doorway/walkway empty for several seconds.
2. Place a detector-supported object partly and then persistently inside the zone.
3. Include a brief pass-through that should not form an event.
4. Remove the object and leave the zone clear.
5. Do not stage an unsafe emergency-exit blockage in an occupied facility.

Import, process, configure a normalized zone, and analyze with:

```powershell
.\.venv\Scripts\python.exe scripts\import_obstruction_recording.py C:\authorized\doorway.mp4 --zone 0.55 0.15 0.35 0.75 --min-duration 2
```

The script uses the upload/process/zone APIs, preserves the source, validates the zone against `[0,1]`, and waits for real processing. It never reads arbitrary server paths.

## Evidence and decision logic

Evidence retains the configured polygon, real detector boxes, label, detector confidence, polygon/box intersection, and timestamp. The rule requires configurable overlap and persistence, tolerates short detection gaps, and merges adjacent evidence. Brief overlap is not automatically an obstruction.

The label remains **Potential Exit Obstruction — Review Required**. Box overlap is only an approximation and cannot prove an exit is inaccessible.

Automated tests cover empty/outside zones, partial and sufficient overlap, persistent and temporary overlap, intermittent detections, merge gaps, multiple objects, and invalid polygons.

## Outstanding work

Run the staged protocol with persistent obstruction, empty-zone, outside-zone, and pass-through clips. Annotate intervals independently, then report event precision/recall, delay, and failures. Synthetic geometry tests are not real-model obstruction accuracy.
