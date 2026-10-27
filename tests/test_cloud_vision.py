"""CPU ONNX pipeline tests: model shapes, per-class NMS, metadata, no false OCR."""
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from services.api import cloud_vision as cv


def test_letterbox_returns_correct_float32_tensor():
    original = Image.new("RGB",(320,160),"white")
    tensor,meta=cv._letterbox(original)
    assert tensor.shape == (1,3,640,640)
    assert tensor.dtype == np.float32
    assert meta == (2.,0,160,320,160)
    assert tensor.max() == 1.0


def test_yolov8_car_output_uses_real_class_id_and_nonmaximum_suppression():
    outputs=np.zeros((1,84,3),dtype=np.float32)
    outputs[0,:4,:] = np.array([[200,201,440],[240,240,200],
                                [100,100,60],[80,80,60]],dtype=np.float32)
    outputs[0,4+2,:] = [0.92,0.88,0.0] # COCO class 2: car
    outputs[0,4+5,2] = .8 # COCO class 5: bus
    result=cv._decode_yolo(outputs,(1,0,0,640,640),cv.LABELS)
    assert len(result)==2, result
    assert result[0]["label"]=="car"
    assert result[0]["box_xyxy"]==[150.,200.,250.,280.]
    assert result[1]["label"]=="bus"


def test_egyptian_plate_detector_shape_and_coordinates():
    outputs=np.zeros((1,5,4),dtype=np.float32)
    outputs[0,:4,0] = [320,320,120,45]
    outputs[0,4,0] = .85
    found=cv._decode_yolo(outputs,(2,0,160,320,160),{0:"egyptian_plate"})
    assert len(found)==1
    assert found[0]["label"]=="egyptian_plate"
    assert found[0]["confidence"]==.85
    assert 0 <= found[0]["box_xyxy"][1] <=160


def test_sampling_does_not_invent_tracks(monkeypatch):
    image=Image.new("RGB",(320,180),"gray")
    monkeypatch.setattr(cv,"sampled_frames",
                        lambda video,duration,count: iter([(1.0,image),(2.0,image)]))
    monkeypatch.setattr(cv,"predict_frame",
                        lambda kind,img: [{"label":"car","class_id":2,"confidence":.8,
                                         "box_xyxy":[20.,30.,120.,90.]}])
    result=cv.sample_vehicle_detection(Path("ignored.mp4"),{"duration_seconds":3})
    assert result["status"]=="completed"
    assert result["sampled_frames"]==2
    assert len(result["tracks"])==1
    assert result["method"].startswith("sparse-frame")
    assert len(result["detections"])==2


def test_no_ocr_fabricated_for_unreadable_plate(monkeypatch):
    image=Image.new("RGB",(320,180),"gray")
    monkeypatch.setattr(cv,"sampled_frames",
                        lambda video,duration,count: iter([(1.0,image)]))
    monkeypatch.setattr(cv,"predict_frame",
                        lambda kind,img: [{"label":"egyptian_plate","class_id":0,
                                          "confidence":.79,
                                          "box_xyxy":[20.,30.,125.,55.]}])
    monkeypatch.setattr(cv,"_ocr_plate",lambda crop: ("",0.0))
    result=cv.sample_egyptian_plates(Path("ignored.mp4"),3)
    assert result["status"]=="completed"
    assert result["plates_detected"]==1
    assert result["candidates"] == []
    assert result["value"] is None


def test_plate_text_remains_unverified_human_review(monkeypatch):
    image=Image.new("RGB",(320,180),"gray")
    monkeypatch.setattr(cv,"sampled_frames",
                        lambda video,duration,count: iter([(1.0,image)]))
    monkeypatch.setattr(cv,"predict_frame",
                        lambda kind,img: [{"label":"egyptian_plate","class_id":0,
                                          "confidence":.8,
                                          "box_xyxy":[20.,30.,120.,55.]}])
    monkeypatch.setattr(cv,"_ocr_plate",lambda crop: ("ب س ١٢٣٤",.54))
    result=cv.sample_egyptian_plates(Path("ignored.mp4"),3)
    assert result["status"]=="completed"
    assert result["value"] is None
    assert result["candidates"][0]["requires_human_review"]
    assert result["candidates"][0]["raw_text"]=="ب س ١٢٣٤"


def test_cloud_branch_keeps_original_ultralytics_backend(monkeypatch):
    from services.api import tracker,plate
    monkeypatch.setenv("TE_CLOUD_VISION","1")
    monkeypatch.setattr(cv,"sample_vehicle_detection",
                        lambda video,meta: {"status":"completed","detections":[],"tracks":[]})
    monkeypatch.setattr(cv,"sample_egyptian_plates",
                        lambda video,dur: {"status":"completed","candidates":[],"value":None})
    assert tracker.track_vehicles(Path("fake"),{"duration_seconds":3})["status"]=="completed"
    assert plate.scan_plates(Path("fake"),3)["status"]=="completed"
    monkeypatch.setenv("TE_CLOUD_VISION","0")
    monkeypatch.delenv("TE_YOLO_MODEL",raising=False)
    monkeypatch.delenv("TE_PLATE_MODEL",raising=False)
    assert tracker.track_vehicles(Path("fake"),{"duration_seconds":3})["status"]=="not_configured"
    assert plate.scan_plates(Path("fake"),3)["status"]=="not_configured"


def test_bad_onnx_output_fails_loudly():
    with pytest.raises(ValueError):
        cv._decode_yolo(np.zeros((1,3,3)),(1,0,0,640,640),cv.LABELS)
