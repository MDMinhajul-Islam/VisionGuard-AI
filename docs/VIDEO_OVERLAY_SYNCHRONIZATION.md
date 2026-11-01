# Video Overlay Synchronization

## Clock and lookup

The player uses `HTMLVideoElement.requestVideoFrameCallback()` when Chromium exposes it. The callback's presented-frame `mediaTime` is the annotation clock. A `requestAnimationFrame` fallback reads `currentTime` for browsers without the API. Callbacks and media listeners are cancelled on unmount.

Samples are sorted by timestamp and found with binary search. A sample is displayed only inside a bounded association window derived from the configured analysis rate (maximum 0.5 seconds). No boxes or landmarks are interpolated.

## Coordinate mapping

Detector boxes and pose points are stored as normalized source-frame coordinates. Canvas rendering computes the visible `object-fit: contain` rectangle inside the displayed video element:

1. choose the smaller horizontal/vertical scale;
2. calculate the rendered media width and height;
3. calculate letterbox offsets;
4. map normalized points into that content rectangle;
5. scale the canvas backing store by `devicePixelRatio`.

The same calculation runs after resizing, seeking, playback-rate changes, and fullscreen entry. It prevents overlay drift when source and container aspect ratios differ.

## Evidence states

- **N genuine detections**: a stored inference sample is associated with the presented frame.
- **Analyzed sample: no detections**: the model ran for that sample but returned no retained objects.
- **No analyzed sample near this frame**: there is no stored observation in the association window. This is not evidence that an object was absent.

The HUD displays the actual sampling rate and matched sample timestamp. The provenance strip explicitly states **No interpolation**.
