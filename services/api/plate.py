"""Optional detector-assisted OCR; no unrestricted identity lookup.

Requires user-supplied license-plate detection weights. General vehicle YOLO
models cannot be used as plate detectors. OCR is tentative until confirmed.
"""
import os
import subprocess
import tempfile
from pathlib import Path


def scan_plates(video: Path, duration: float) -> dict:
    # Egypt-trained plate localization + Arabic OCR, no uploaded custom weights.
    if os.getenv("TE_CLOUD_VISION", "0") == "1":
        from .cloud_vision import sample_egyptian_plates
        return sample_egyptian_plates(video, duration)
    weights = os.getenv("TE_PLATE_MODEL", "").strip()
    if not weights:
        return {"status": "not_configured", "value": None, "candidates": [],
                "note": "Set TE_PLATE_MODEL to evaluated Egyptian-plate detector weights and install requirements-ocr.txt."}
    try:
        import cv2
        import easyocr
        from ultralytics import YOLO
        model = YOLO(weights)
        ocr = easyocr.Reader(["ar", "en"], gpu=os.getenv("TE_OCR_GPU", "0") == "1")
        all_readings = []
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            for i in range(6):
                second = round(duration * (i + 0.5) / 6, 2)
                file = directory / f"plate-{i}.jpg"
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-ss", str(second), "-i", str(video), "-frames:v", "1",
                                "-q:v", "3", str(file)], check=True,
                               capture_output=True, timeout=35)
                frame = cv2.imread(str(file))
                if frame is None:
                    continue
                result = model.predict(source=frame, conf=.25,
                                       device=os.getenv("TE_YOLO_DEVICE", "cpu"),
                                       verbose=False)[0]
                height, width = frame.shape[:2]
                for box in list(result.boxes or [])[:12]:
                    x1,y1,x2,y2 = [int(v) for v in box.xyxy[0].tolist()]
                    x1,y1,x2,y2 = max(x1,0),max(y1,0),min(x2,width),min(y2,height)
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    readings = ocr.readtext(crop, detail=1, paragraph=False)
                    for _, text, confidence in readings[:5]:
                        clean = str(text).strip()
                        if not clean or len(clean) < 3:
                            continue
                        all_readings.append({"raw_text": clean,
                                             "confidence": round(float(confidence), 4),
                                             "second": second, "bbox": [x1,y1,x2,y2]})
        # Candidate-only OCR: NEVER auto-confirm a license plate from one crop.
        return {"status": "completed", "model": weights, "value": None,
                "candidates": sorted(all_readings, key=lambda x:-x["confidence"])[:18],
                "note": "Tentative OCR candidates from sampled images. Needs Arabic plate-format validation, multiple frames and human review."}
    except Exception as exc:
        return {"status": "failed", "value": None, "candidates": [],
                "note": f"{type(exc).__name__}: {str(exc)[:220]}"}
