# Third-party notices

| Component | Use | License / obligation |
|---|---|---|
| [OpenAI CLIP](https://github.com/openai/CLIP) | ViT-B/32 package, preprocessing, weights | MIT; retain copyright/license. Follow the research-oriented model card. |
| [PyTorch](https://github.com/pytorch/pytorch) | tensor/CUDA runtime | BSD-style; retain notices. |
| [Torchvision](https://github.com/pytorch/vision) | SSDLite implementation and COCO weights loader | BSD-3-Clause; retain notices. Selected instead of Ultralytics to avoid AGPL/enterprise ambiguity. |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | Pose Landmarker runtime/task | Apache-2.0; retain notices and state changes where applicable. |
| [FFmpeg](https://ffmpeg.org/legal.html) | metadata and clip processing | LGPL/GPL depends on build flags; redistributors must inspect the exact binary configuration and provide corresponding notices/source obligations. Runtime download is not committed. |
| FastAPI / SQLAlchemy / OpenCV / NumPy | backend | Their respective permissive licenses; preserve package notices in redistribution. |
| Next.js / React / Tailwind / Playwright | frontend and tests | Their respective open-source licenses; preserve package notices in redistribution. |

Pretrained weights, FFmpeg binaries, raw footage, and derived artifacts are downloaded/generated locally and excluded from Git. This file is an engineering summary, not legal advice.
