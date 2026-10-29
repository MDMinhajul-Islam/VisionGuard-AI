# Detector Model Selection

## Recommendation

Keep SSDlite as the unchanged runtime detector until a commercially cleared replacement passes an annotated industrial benchmark. Advance **RF-DETR Nano** as the primary open-license experimental candidate. Keep **YOLO26n benchmark-only** unless an appropriate Ultralytics Enterprise agreement or an AGPL-compatible distribution decision is documented.

YOLO26n was fastest in the small latency run, but speed alone is insufficient. RF-DETR Nano was slower and used more memory, yet its core model is published under Apache-2.0 and remains feasible on the 4 GiB GPU. Neither has industrial accuracy evidence in this project.

## Class coverage

COCO checkpoints support `person`, `chair`, `suitcase`, `backpack` and some vehicles. They do **not** provide dependable dedicated classes for pallet, forklift, cardboard box, safety helmet or safety vest. Generic truck/car labels must not be relabeled as forklifts, and suitcase/package detections must not be presented as cardboard boxes.

## Commercial fine-tuning dataset

Use only customer-authorized or explicitly commercially licensed imagery. Store COCO JSON boxes with image/license/site/camera metadata. Label visible instances using written rules for truncation, occlusion, minimum size, difficult cases and ambiguous PPE. Include explicit negative/background scenes.

Split by site and camera installation—not random frames—to prevent leakage. Keep organizations and recording sessions disjoint where possible. Version media manifests and annotations separately; hash every source and derived asset. Preserve licenses and consent/contract references per asset.

Required metrics include per-class AP50 and AP50:95, precision/recall curves, small-object performance, site/camera slices, false alarms per video-hour, calibration, latency and memory on target hardware. Release evaluation must use a locked test set never used for threshold selection.
