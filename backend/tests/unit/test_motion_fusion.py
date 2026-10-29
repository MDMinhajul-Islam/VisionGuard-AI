import cv2
import numpy as np
import pytest

from app.vision.fall_detection import PoseObservation
from app.vision.motion_fusion import box_motion, camera_compensated_flow, detect_motion_fusion_events


def pose(t, bbox, shoulder=(.5,.25), hip=(.5,.48), visibility=.95):
    return PoseObservation(t, shoulder, hip, bbox, visibility, frame_id=f"f-{t}")


def test_bbox_motion_measures_center_drop_and_aspect_change():
    motion=box_motion(pose(0,(.4,.1,.6,.9)),pose(1,(.2,.55,.8,.85),shoulder=(.3,.7),hip=(.6,.7)))
    assert motion.center_drop == pytest.approx(.2)
    assert motion.aspect_change > 1.0


def test_motion_fusion_detects_shape_supported_downward_transition():
    sequence=[pose(0,(.4,.1,.6,.9)),pose(.5,(.4,.12,.6,.92)),pose(1,(.2,.55,.8,.85),shoulder=(.3,.7),hip=(.6,.7))]
    events=detect_motion_fusion_events(sequence)
    assert len(events)==1
    assert events[0].evidence["bbox_center_drop"] >= .1


def test_motion_fusion_suppresses_narrow_bending_and_missing_boxes():
    bend=pose(1,(.42,.35,.68,.85),shoulder=(.42,.68),hip=(.62,.68))
    assert detect_motion_fusion_events([pose(0,(.4,.1,.6,.9)),bend]) == []
    missing=PoseObservation(1,None,None,None,0)
    assert detect_motion_fusion_events([pose(0,(.4,.1,.6,.9)),missing]) == []


def test_optical_flow_subtracts_global_camera_translation():
    previous=np.zeros((80,100),np.uint8);cv2.rectangle(previous,(20,20),(80,60),255,-1)
    matrix=np.float32([[1,0,2],[0,1,1]])
    current=cv2.warpAffine(previous,matrix,(100,80))
    result=camera_compensated_flow(previous,current,(30,25,70,55))
    assert np.isfinite(list(result.values())).all()
    assert result["subject_motion_magnitude"] < 1.5
