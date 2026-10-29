# Commercial Licensing Inventory

This engineering inventory is not legal advice. Counsel must review code, weights, training data, distribution model and customer terms before release.

| Component | Published status | Sprint 3 treatment | Open question / obligation |
|---|---|---|---|
| OpenAI CLIP code | MIT | controlled research search only | model card states deployed and surveillance use is out of scope; exclude from commercial surveillance runtime |
| Torchvision / SSDlite code | BSD-3-Clause | existing runtime preserved | retain notices; separately review COCO checkpoint/training-data provenance before commercial promotion |
| MediaPipe | Apache-2.0 | experimental pose/fall research | retain notices; verify downloaded task-model terms and provenance |
| Ultralytics YOLO26 code/weights | AGPL-3.0 or Enterprise | isolated benchmark only | commercial proprietary use is blocked absent an appropriate license/compliance decision |
| RF-DETR Nano/Small core | Apache-2.0 | isolated candidate benchmark | core Nano–Large only; do not confuse with differently licensed Plus variants; retain notices and review training data |
| FFmpeg | LGPL/GPL depends on build configuration | local transcoding | audit the exact shipped binary configuration and codecs before redistribution |
| UR Fall Detection | CC BY-NC-SA 4.0, non-commercial academic use | research evaluation only | never train or validate a commercial claim with it; contact publisher for commercial permission |
| OpenAI CLIP research data | not released; model-card restrictions | no redistribution | do not imply training-data clearance |
| VisionGuard source | repository MIT license | internal foundation | third-party obligations remain independent |

Authoritative references:

- https://github.com/openai/CLIP/blob/main/model-card.md
- https://github.com/pytorch/vision/blob/main/LICENSE
- https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE
- https://docs.ultralytics.com/models/yolo26/
- https://github.com/ultralytics/ultralytics/blob/main/LICENSE
- https://github.com/roboflow/rf-detr
- https://ffmpeg.org/legal.html
- https://fenix.ur.edu.pl/~mkepski/ds/uf.html
