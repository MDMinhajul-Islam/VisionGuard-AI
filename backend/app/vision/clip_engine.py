from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.core.config import get_settings


class CLIPUnavailable(RuntimeError):
    pass


class CLIPEngine:
    model_name = "ViT-B/32"

    def __init__(self):
        self.settings = get_settings()
        self.device = torch.device("cuda" if self.settings.device == "auto" and torch.cuda.is_available() else self.settings.device if self.settings.device != "auto" else "cpu")
        self.model = None
        self.preprocess = None
        self._lock = threading.Lock()
        self.load_seconds = None

    def load(self):
        if self.model is not None:
            return
        try:
            import clip
        except ImportError as error:
            raise CLIPUnavailable("Original OpenAI CLIP package is not installed") from error
        started = time.perf_counter()
        with self._lock:
            if self.model is None:
                self.model, self.preprocess = clip.load(
                    self.model_name,
                    device=self.device,
                    jit=False,
                    download_root=str(self.settings.model_dir / "clip"),
                )
                self.model.eval()
                if self.device.type == "cuda":
                    torch.cuda.synchronize()
                self.load_seconds = time.perf_counter() - started

    @staticmethod
    def _normalize(features: torch.Tensor) -> torch.Tensor:
        return features.float() / features.float().norm(dim=-1, keepdim=True).clamp_min(1e-12)

    @torch.inference_mode()
    def encode_images(self, images: list[np.ndarray], batch_size: int = 8) -> tuple[np.ndarray, float]:
        self.load()
        features = []
        started = time.perf_counter()
        with self._lock:
            for offset in range(0, len(images), batch_size):
                tensors = torch.stack([
                    self.preprocess(Image.fromarray(image[:, :, ::-1]).convert("RGB"))
                    for image in images[offset: offset + batch_size]
                ]).to(self.device)
                features.append(self._normalize(self.model.encode_image(tensors)).cpu())
            if self.device.type == "cuda":
                torch.cuda.synchronize()
        return torch.cat(features).numpy() if features else np.empty((0, 512), np.float32), time.perf_counter() - started

    @torch.inference_mode()
    def encode_text(self, text: str) -> np.ndarray:
        self.load()
        import clip
        with self._lock:
            tokens = clip.tokenize([text]).to(self.device)
            return self._normalize(self.model.encode_text(tokens)).cpu().numpy()[0]

    def save_index(self, video_id: str, features: np.ndarray, frame_ids: list[str], timestamps: list[float]) -> Path:
        path = self.settings.embeddings_dir / f"{video_id}.npz"
        np.savez_compressed(path, features=features.astype(np.float32), frame_ids=np.asarray(frame_ids), timestamps=np.asarray(timestamps, np.float32))
        return path

    def unload(self):
        with self._lock:
            self.model = None
            self.preprocess = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def search(self, cache_path: Path, query: str, top_k: int, suppression_seconds: float):
        cache = np.load(cache_path, allow_pickle=False)
        features, timestamps, frame_ids = cache["features"], cache["timestamps"], cache["frame_ids"]
        query_feature = self.encode_text(query)
        scores = features @ query_feature
        selected = []
        for index in np.argsort(scores)[::-1]:
            timestamp = float(timestamps[index])
            if any(abs(timestamp - item["timestamp_seconds"]) < suppression_seconds for item in selected):
                continue
            selected.append({"frame_id": str(frame_ids[index]), "timestamp_seconds": timestamp, "similarity": float(scores[index])})
            if len(selected) >= top_k:
                break
        return selected


clip_engine = CLIPEngine()

