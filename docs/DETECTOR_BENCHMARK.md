# Detector Benchmark — Sprint 3

## Protocol

- Five local UR Fall Detection frames, identified in the report only by SHA-256.
- Same 640×640 letterboxed BGR canvas, threshold 0.45, hardware and process.
- Two warmups and ten measured inferences per model, cycling the same frames.
- CUDA synchronization around measured inference.
- Load time, inference and end-to-end p50/p95, PyTorch peak allocation, normalized process CPU and detection counts recorded.
- Model-native internal preprocessing remains model-specific and is recorded by architecture: SSDlite resizes through official Torchvision transforms; YOLO26 receives `imgsz=640`; RF-DETR Nano applies its published model transform.
- No bounding-box ground truth exists for these five frames. **mAP, precision and recall were not calculated.** Detection counts are not accuracy.

Raw results: `evaluations/detector_benchmark.json`.

## Actual RTX 3050 Ti results

| Model | Load s | Inference mean / p50 / p95 ms | End-to-end mean / p50 / p95 ms | Peak GPU MiB | Status |
|---|---:|---:|---:|---:|---|
| Torchvision SSDlite320 MobileNetV3 | 0.46 | 49.66 / 46.23 / 61.99 | 52.81 / 49.37 / 65.33 | 38.30 | commercial clearance pending |
| Ultralytics YOLO26n | 0.23 | 14.26 / 14.18 / 14.96 | 14.56 / 14.50 / 15.20 | 65.26 | benchmark-only licensing |
| RF-DETR Nano 1.11.2 | 6.30 | 32.15 / 23.56 / 72.75 | 32.33 / 23.76 / 72.94 | 178.50 | Apache core candidate |

Checkpoint SHA-256 values are recorded for all three. RF-DETR emitted an official warning that the eager model was not inference-optimized; results must not be compared with vendor TensorRT figures.

## Limitations

The source frames come from a non-commercial academic dataset, contain limited scene diversity, and have no detection annotations. This run measures engineering compatibility and latency only. It does not select an accuracy winner and cannot support a commercial performance claim.

## Reproduction

```powershell
python -m venv .venv-benchmark --system-site-packages
.\.venv-benchmark\Scripts\python.exe -m pip install -r benchmark\requirements.txt
$env:RF_HOME="$PWD\models\benchmark\rfdetr"
$images = Get-ChildItem runtime\frames -Recurse -Filter *.jpg |
  Group-Object DirectoryName | ForEach-Object {$_.Group[0].FullName} | Select-Object -First 5
.\.venv-benchmark\Scripts\python.exe scripts\benchmark_detectors.py @images `
  --models ssdlite yolo26n rfdetr-nano --warmup 2 --iterations 10 `
  --output evaluations\detector_benchmark.json
.\.venv\Scripts\python.exe scripts\register_benchmark_experiment.py evaluations\detector_benchmark.json
```
