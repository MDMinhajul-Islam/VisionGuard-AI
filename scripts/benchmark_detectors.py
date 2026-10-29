from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import psutil
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.vision.detectors.base import DetectorMetadata, validate_detections
from app.evaluation.benchmark import validate_benchmark_report
from app.vision.object_detector import ObjectDetector


COCO_NAMES = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def letterbox(image: np.ndarray, size: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    y = (size - resized.shape[0]) // 2
    x = (size - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


class YOLO26Adapter:
    def __init__(self, size: str, weights_root: Path):
        self.size = size
        self.weights_path = weights_root / f"yolo26{size}.pt"
        self.model = None
        self._last_ms = None

    @property
    def last_inference_ms(self): return self._last_ms

    @property
    def metadata(self):
        return DetectorMetadata(
            model_id=f"ultralytics-yolo26{self.size}", model_version="YOLO26",
            architecture=f"YOLO26{self.size}", checkpoint=f"models/benchmark/yolo26{self.size}.pt",
            license="AGPL-3.0 or Ultralytics Enterprise; benchmark-only without commercial license",
            commercial_runtime_eligible=False,
            device="cuda:0" if torch.cuda.is_available() else "cpu", class_names=COCO_NAMES,
        )

    def load(self):
        from ultralytics import YOLO
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        self.model = YOLO(str(self.weights_path if self.weights_path.exists() else f"yolo26{self.size}.pt"))
        resolved = Path(getattr(self.model, "ckpt_path", self.weights_path))
        if resolved.exists() and resolved != self.weights_path:
            resolved.replace(self.weights_path)
            self.model = YOLO(str(self.weights_path))

    def detect(self, frame, threshold=.45, allowed_labels=None):
        started = time.perf_counter()
        result = self.model.predict(frame, imgsz=640, conf=threshold, device=0 if torch.cuda.is_available() else "cpu", verbose=False)[0]
        if torch.cuda.is_available(): torch.cuda.synchronize()
        self._last_ms = (time.perf_counter() - started) * 1000
        height, width = frame.shape[:2]
        rows = []
        for box, confidence, class_id in zip(result.boxes.xyxy.cpu(), result.boxes.conf.cpu(), result.boxes.cls.cpu()):
            label = result.names[int(class_id)]
            if allowed_labels and label not in allowed_labels: continue
            x1, y1, x2, y2 = map(float, box)
            rows.append({"label": label, "confidence": float(confidence), "bbox_pixels": (x1,y1,x2,y2), "bbox": (x1/width,y1/height,x2/width,y2/height), "model_id": self.metadata.model_id, "model_version": "YOLO26", "device": self.metadata.device, "provenance": f"ultralytics:yolo26{self.size}"})
        validate_detections(rows)
        return rows

    def unload(self): self.model = None; torch.cuda.empty_cache() if torch.cuda.is_available() else None


class RFDETRAdapter:
    def __init__(self, size: str): self.size=size; self.model=None; self._last_ms=None; self.names={}
    @property
    def last_inference_ms(self): return self._last_ms
    @property
    def metadata(self):
        return DetectorMetadata(model_id=f"rf-detr-{self.size}", model_version="1.11.2", architecture=f"RF-DETR {self.size.title()}", checkpoint=f"models/benchmark/rfdetr/rf-detr-{self.size}.pth", license="Apache-2.0 core model", commercial_runtime_eligible=True, device="cuda:0" if torch.cuda.is_available() else "cpu", class_names=COCO_NAMES)
    def load(self):
        from rfdetr import RFDETRNano, RFDETRSmall
        from rfdetr.assets.coco_classes import COCO_CLASSES
        self.names = COCO_CLASSES
        self.model = (RFDETRNano if self.size == "nano" else RFDETRSmall)()
    def detect(self, frame, threshold=.45, allowed_labels=None):
        started=time.perf_counter(); prediction=self.model.predict(frame, threshold=threshold)
        if torch.cuda.is_available(): torch.cuda.synchronize()
        self._last_ms=(time.perf_counter()-started)*1000; height,width=frame.shape[:2]; rows=[]
        for box,confidence,class_id in zip(prediction.xyxy,prediction.confidence,prediction.class_id):
            label=self.names[int(class_id)]
            if allowed_labels and label not in allowed_labels: continue
            x1,y1,x2,y2=map(float,box)
            rows.append({"label":label,"confidence":float(confidence),"bbox_pixels":(x1,y1,x2,y2),"bbox":(x1/width,y1/height,x2/width,y2/height),"model_id":self.metadata.model_id,"model_version":"1.11.2","device":self.metadata.device,"provenance":f"roboflow:rf-detr-{self.size}"})
        validate_detections(rows); return rows
    def unload(self): self.model=None; torch.cuda.empty_cache() if torch.cuda.is_available() else None


def adapter(name: str, weights_root: Path):
    if name == "ssdlite": return ObjectDetector()
    if name in {"yolo26n", "yolo26s"}: return YOLO26Adapter(name[-1], weights_root)
    if name in {"rfdetr-nano", "rfdetr-small"}: return RFDETRAdapter(name.split("-")[-1])
    raise ValueError(f"unsupported detector: {name}")


def percentile(values: list[float], quantile: float) -> float:
    return float(np.percentile(np.asarray(values), quantile))


def main() -> int:
    parser=argparse.ArgumentParser(description="Benchmark detector adapters on identical letterboxed source images.")
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--models", nargs="+", default=["ssdlite"])
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--threshold", type=float, default=.45)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT/"evaluations"/"detector_benchmark.json")
    args=parser.parse_args()
    if args.warmup < 1 or args.iterations < 3: parser.error("use at least one warmup and three measured iterations")
    sources=[]
    for path in args.images:
        image=cv2.imread(str(path))
        if image is None: parser.error(f"cannot decode {path}")
        sources.append((sha256(path),letterbox(image,args.input_size)))
    results=[]; process=psutil.Process(); weights_root=PROJECT_ROOT/"models"/"benchmark"
    for name in args.models:
        detector=adapter(name,weights_root); load_started=time.perf_counter()
        try:
            detector.load(); load_seconds=time.perf_counter()-load_started
            if torch.cuda.is_available(): torch.cuda.reset_peak_memory_stats()
            for index in range(args.warmup): detector.detect(sources[index%len(sources)][1],args.threshold)
            latencies=[]; end_to_end=[]; counts=[]; cpu_start=process.cpu_times(); measured_started=time.perf_counter()
            for index in range(args.iterations):
                started=time.perf_counter(); detections=detector.detect(sources[index%len(sources)][1],args.threshold); end_to_end.append((time.perf_counter()-started)*1000); latencies.append(float(detector.last_inference_ms)); counts.append(len(detections))
            wall=time.perf_counter()-measured_started; cpu_end=process.cpu_times(); cpu_seconds=(cpu_end.user+cpu_end.system)-(cpu_start.user+cpu_start.system)
            metadata=detector.metadata.to_dict(); checkpoint=Path(metadata["checkpoint"]); checkpoint=checkpoint if checkpoint.is_absolute() else PROJECT_ROOT/checkpoint
            results.append({"status":"completed","metadata":metadata,"checkpoint_sha256":sha256(checkpoint) if checkpoint.is_file() else None,"load_seconds":load_seconds,"warmup_iterations":args.warmup,"measured_iterations":args.iterations,"inference_ms":{"mean":statistics.mean(latencies),"p50":percentile(latencies,50),"p95":percentile(latencies,95)},"end_to_end_ms":{"mean":statistics.mean(end_to_end),"p50":percentile(end_to_end,50),"p95":percentile(end_to_end,95)},"peak_gpu_memory_mib":torch.cuda.max_memory_allocated()/2**20 if torch.cuda.is_available() else 0,"process_cpu_percent_normalized":100*cpu_seconds/max(wall*psutil.cpu_count(),1e-9),"detection_counts":counts})
        except Exception as error:
            results.append({"status":"failed","model":name,"error_type":type(error).__name__,"error":str(error)})
        finally: detector.unload()
    report={"schema_version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"git_commit":os.popen("git rev-parse HEAD").read().strip(),"protocol":{"source_image_sha256":[item[0] for item in sources],"input_canvas":f"{args.input_size}x{args.input_size} letterbox","threshold":args.threshold,"accuracy_metrics":"not calculated; no bounding-box ground truth"},"hardware":{"platform":platform.platform(),"python":platform.python_version(),"torch":torch.__version__,"cuda_available":torch.cuda.is_available(),"cuda":torch.version.cuda,"gpu":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None},"results":results}
    validate_benchmark_report(report)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2));return 0


if __name__ == "__main__": raise SystemExit(main())
