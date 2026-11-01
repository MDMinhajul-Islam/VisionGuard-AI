# Video Analysis Player

## Implemented behavior

`VideoAnalysisPlayer` is the shared recorded-video inspection component used by the dedicated video workspace and event evidence viewer. The MP4 remains the underlying media element; a transparent canvas draws stored inference results over it.

The player supports native playback and seeking, 0.5–2× speed, keyboard play/pause, previous/next analyzed-sample stepping, wrapper fullscreen, event navigation, and independent toggles for boxes, track IDs, pose, zones, and events.

## Reviewer workflow

1. Open **Video Workspace** and select **Open Analysis**.
2. Play or seek the source recording.
3. Read the sample-state label. It distinguishes a matched analyzed sample with zero detections from a time with no nearby analyzed sample.
4. Toggle evidence layers without changing the stored evidence.
5. Select an event marker or event card to seek to its start.
6. Open the event review page before recording a human decision.

The component never confirms an incident and never generates inference in the browser.

## Current limits

- The first timeline request is bounded to 300 seconds and 5,000 samples. Longer recordings require windowed loading in a future iteration.
- Frame stepping moves between analyzed samples, not every source-video frame.
- Visual zone creation remains in the existing configuration workflow; the player currently renders saved polygons.
- Native browser media decoding determines codec support.
