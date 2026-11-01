# Sprint 5B Visual Verification

Verification date: 2026-11-01 (Asia/Dhaka).

## Verified locally

- Authenticated user: local Sprint 5A browser QA administrator.
- Organization/site: Legacy Research Workspace / Legacy Imported Data.
- Source recording: authorized local research clip `fall-18.mp4`, 640×480, 2.2 seconds.
- Stored timeline: five analyzed samples at 2 FPS.
- Initial matched sample: four genuine SSDlite detections.
- Displayed provenance: SSDLite320 MobileNetV3 Large / COCO_V1 and MediaPipe Pose Landmarker Lite.
- Browser: Chromium through the local in-app browser.
- The original MP4 loaded, the transparent canvas rendered over it, sample stepping updated the timestamp, and pose/box controls remained independent.
- Compact-width navigation was checked at approximately 390 px and corrected to avoid horizontal overflow.

Automated browser verification additionally reads canvas alpha pixels to prove the overlay is genuinely drawn rather than merely present in the DOM. The test also checks the source video ready state, model identity, no-interpolation disclosure, pose toggle, sample navigation, speed control, and compact viewport overflow.

One headless Chromium run against the first authorized library item measured 992 ms from detail navigation to loaded provenance plus a decodable video, a 215,547-byte bounded timeline response, 10 ms to read that response body, and 25 MiB of JavaScript heap. A seek followed by a deliberately fixed 250 ms observation window completed in 262 ms; this is a responsiveness smoke measurement, not a precise synchronization-error benchmark. Measurements are machine- and cache-specific.

Screenshots are written only to `data/external/validation/reports/`, which is excluded from Git because research participants may be identifiable.

## Honest limitations

This is visual alignment verification on available sampled clips, not a pixel-annotated alignment benchmark. Sparse 2 FPS inference leaves expected gaps. No FPS, synchronization-error, or GPU-memory number is reported here unless collected by an instrumented benchmark.
