import os
from pathlib import Path

import cv2
import numpy as np
import pytest


pytestmark = pytest.mark.skipif(os.getenv("VISIONGUARD_RUN_MODEL_TESTS") != "1", reason="set VISIONGUARD_RUN_MODEL_TESTS=1 for real model tests")
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_actual_clip_image_and_text_encoding():
    from app.vision.clip_engine import clip_engine
    image = np.full((224, 224, 3), (180, 100, 30), np.uint8)
    features, _ = clip_engine.encode_images([image])
    text = clip_engine.encode_text("a blue image")
    assert features.shape == (1, 512)
    assert text.shape == (512,)
    assert np.isfinite(features).all() and np.isfinite(text).all()


@pytest.mark.integration
def test_actual_torchvision_detector():
    from app.vision.object_detector import object_detector
    image = cv2.imread(str(ROOT / "runtime" / "integration_assets" / "torchvision_grace_hopper.jpg"))
    assert image is not None
    detections = object_detector.detect(image, threshold=.3)
    assert any(item["label"] == "person" for item in detections)


@pytest.mark.integration
def test_actual_mediapipe_pose_video_mode():
    from app.vision.pose_engine import pose_engine
    image = cv2.imread(str(ROOT / "runtime" / "integration_assets" / "mediapipe_pose.jpg"))
    assert image is not None
    observation = pose_engine.process(image, 0)
    assert observation.shoulder_center is not None
    assert observation.hip_center is not None
    assert observation.visibility > .5
    pose_engine.close()
