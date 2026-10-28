# Models and algorithms

## OpenAI CLIP ViT-B/32

The original OpenAI package and official preprocessing/tokenization are installed from pinned upstream commit `d05afc2a98f2c58574a05c3679d992cf765c940f`. Image and text outputs are normalized 512-dimensional embeddings. Similarity is a ranking signal, **not** a probability. CLIP is lazy-loaded, cached locally, and unloaded before detection when GPU memory is constrained.

The [CLIP model card](https://github.com/openai/CLIP/blob/main/model-card.md) identifies deployed surveillance and facial recognition as out of scope. VisionGuard limits this feature to offline, authorized, controlled research.

## Torchvision SSDLite320 MobileNetV3 Large

`SSDLite320_MobileNet_V3_Large_Weights.DEFAULT` supplies official COCO weights and transforms. The detector is a compact 3.4M-parameter architecture suitable for the laptop target, with configurable thresholding and the library model's internal NMS. Stored evidence includes label, confidence, normalized/pixel boxes, timestamp, and temporary track ID. The model supports COCO labels; it does not establish exit obstruction and does not reliably support PPE, exit signs, smoke, fire, or industrial hazards.

This BSD-3-Clause Torchvision choice avoids the AGPL/enterprise constraints of Ultralytics YOLO for this research repository.

## IoU tracker

A deliberately small SORT-like association layer matches same-class boxes by Intersection over Union, retains missed tracks for a bounded age, and records short histories/motion deltas. IDs reset for every video. It performs no face recognition, embeddings, re-identification, or cross-video linkage.

## MediaPipe Pose Landmarker Lite

The official float16 Pose Landmarker Lite task runs in `VIDEO` mode with monotonically increasing millisecond timestamps. The wrapper records shoulder/hip centers, pose bounding box, visibility, and frame ID. Missing or low-confidence evidence becomes `unknown`.

## Fall heuristic

The temporal state machine combines torso angle, body aspect ratio, hip descent, upright-to-horizontal transition window, horizontal persistence, recovery, and visibility. It suppresses single-frame decisions. Sitting, crouching, intentional lying, occlusion, unusual camera angles, and truncation can still cause false results. Output is always **Potential Fall — Review Required**.

## Exit-zone heuristic

Users define a normalized polygon named Emergency Exit / Keep Clear Zone. OpenCV polygon-box intersection estimates occupied zone fraction. Qualifying samples are grouped with a detection-gap tolerance and must persist before an event is emitted. Bounding-box overlap cannot prove that an exit is inaccessible. Output is always **Potential Exit Obstruction — Review Required**.
