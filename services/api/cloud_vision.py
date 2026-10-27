"""CPU-only ONNX detection on sparsely sampled dashcam frames.

Real pretrained models; no made-up tracks, no official enforcement claims.
Models load lazily from fixed public Hugging Face URLs, never from user input.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

# Public upstream model assets and license notes:
# Vehicle: unileon-robotics/YOLO8-ONNX (Ultralytics YOLOv8n, AGPL-3.0)
# Egyptian plate: omasayeddd/egyptian-license-plate-detector (model card MIT;
# review upstream YOLO/Ultralytics licensing before commercial deployment).
VEHICLE_SOURCE = (
    "https://huggingface.co/unileon-robotics/YOLO8-ONNX/resolve/main/yolov8n.onnx"
)
VEHICLE_SHA256 = "fa2c856b0effedce4f49fffd121f438247a64c8f633bf0e6d5e5960e869ccc5a"
PLATE_SOURCE = (
    "https://huggingface.co/omasayeddd/egyptian-license-plate-detector/resolve/main/best.onnx"
)
LABELS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
FRAME_SIZE = 640


def _models_dir() -> Path:
    folder = Path(os.environ.get("TE_CLOUD_MODEL_CACHE",
                                 str(Path(tempfile.gettempdir()) / "traffic-enhancer-models")))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _download_model(source: str, target: Path, expected_sha: str = "") -> Path:
    """Atomic bounded artifact download. Never expose uploaded content to models host."""
    import httpx
    if target.is_file() and target.stat().st_size > 500_000:
        if not expected_sha or _sha(target) == expected_sha:
            return target
    temp = target.with_suffix(".partial")
    digest = hashlib.sha256()
    total = 0
    try:
        # Fixed allowlisted model URL, no user-supplied targets or credentials.
        with httpx.stream("GET", source, follow_redirects=True,
                          timeout=httpx.Timeout(120, connect=15)) as reply:
            reply.raise_for_status()
            with temp.open("wb") as handle:
                for chunk in reply.iter_bytes(chunk_size=256 * 1024):
                    total += len(chunk)
                    if total > 55 * 1024 * 1024:
                        raise ValueError("ONNX model exceeds safe download limit")
                    digest.update(chunk)
                    handle.write(chunk)
        if total < 500_000:
            raise ValueError("ONNX model download is incomplete")
        if expected_sha and digest.hexdigest() != expected_sha:
            raise ValueError("Unexpected ONNX model checksum from public source")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return target


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(256 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=2)
def _onnx_session(kind: str):
    import onnxruntime as ort
    if kind == "vehicle":
        model_file = _download_model(VEHICLE_SOURCE, _models_dir() / "vehicle-yolov8n.onnx",
                                     VEHICLE_SHA256)
    elif kind == "plate":
        model_file = _download_model(PLATE_SOURCE, _models_dir() / "egyptian-plate-v8n.onnx")
    else:
        raise ValueError("Unsupported inference model")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    return ort.InferenceSession(str(model_file), sess_options=options,
                                providers=["CPUExecutionProvider"])


def _letterbox(frame: Image.Image, size=FRAME_SIZE):
    frame = frame.convert("RGB")
    width, height = frame.size
    target_w,target_h = (size,size) if isinstance(size,int) else size
    scale = min(target_w / width, target_h / height)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    offset_x, offset_y = (target_w-new_width)//2, (target_h-new_height)//2
    canvas = Image.new("RGB", (target_w, target_h), (114,114,114))
    canvas.paste(frame.resize((new_width,new_height), Image.Resampling.BILINEAR),
                 (offset_x,offset_y))
    tensor = np.asarray(canvas, dtype=np.float32).transpose(2,0,1)[None] / 255.
    return tensor, (scale,offset_x,offset_y,width,height)


def _iou(one, other) -> float:
    x1,y1,x2,y2 = one
    a1,b1,a2,b2 = other
    cross = max(0,min(x2,a2)-max(x1,a1))*max(0,min(y2,b2)-max(y1,b1))
    area1 = max(0,x2-x1)*max(0,y2-y1)
    area2 = max(0,a2-a1)*max(0,b2-b1)
    return float(cross / (area1+area2-cross+1e-9))


def _decode_yolo(raw, transform, class_ids: dict, threshold: float=.27,
                 max_results: int=18):
    """Decode raw YOLOv8 tensor [1, 4+classes, anchors] with per-class NMS."""
    prediction = np.asarray(raw, dtype=np.float32)
    if prediction.ndim != 3 or prediction.shape[0] != 1:
        raise ValueError("Unexpected ONNX prediction tensor shape")
    prediction = prediction[0]
    if prediction.shape[0] < 6 and prediction.shape[1] >= 6:
        prediction = prediction.T
    elif prediction.shape[0] in (5,84):
        prediction = prediction.T
    if prediction.ndim != 2 or prediction.shape[1] < 5:
        raise ValueError("Unexpected YOLO channel layout")
    scores = prediction[:, 4:]
    if max(class_ids) >= scores.shape[1]:
        raise ValueError("The pretrained model does not expose expected class IDs")
    proposals = []
    for class_id, label in class_ids.items():
        choices = np.flatnonzero(scores[:,class_id] >= threshold)
        if len(choices) > 80:
            priority = np.argsort(scores[choices,class_id])[-80:]
            choices = choices[priority]
        for idx in choices:
            cx,cy,w,h = [float(v) for v in prediction[idx,:4]]
            scale,ox,oy,orig_w,orig_h = transform
            coords = [max(0,min(orig_w,(cx-w/2-ox)/scale)),
                      max(0,min(orig_h,(cy-h/2-oy)/scale)),
                      max(0,min(orig_w,(cx+w/2-ox)/scale)),
                      max(0,min(orig_h,(cy+h/2-oy)/scale))]
            if coords[2]-coords[0] < 3 or coords[3]-coords[1] < 3:
                continue
            proposals.append({"box_xyxy":[round(v,1) for v in coords],
                              "confidence":round(float(scores[idx,class_id]),4),
                              "label":label,"class_id":class_id})
    proposals.sort(key=lambda p: -p["confidence"])
    selected = []
    for candidate in proposals:
        if all(candidate["class_id"] != old["class_id"] or
               _iou(candidate["box_xyxy"],old["box_xyxy"]) < .45
               for old in selected):
            selected.append(candidate)
            if len(selected) >= max_results:
                break
    return selected


def predict_frame(kind: str, image: Image.Image):
    if kind not in ("vehicle","plate"):
        raise ValueError("Unsupported detection target")
    model = _onnx_session(kind)
    inp = model.get_inputs()[0]
    dims = inp.shape
    # Legitimate ONNX exports can use 480×640 (COCO detector) or 640×640.
    if len(dims) != 4:
        raise ValueError("ONNX input must be NCHW")
    h = int(dims[2]) if isinstance(dims[2],int) else FRAME_SIZE
    w = int(dims[3]) if isinstance(dims[3],int) else FRAME_SIZE
    if not (256 <= h <= 1280 and 256 <= w <= 1280):
        raise ValueError("ONNX model input dimensions outside supported range")
    tensor,transform = _letterbox(image, (w,h))
    raw = model.run(None,{inp.name:tensor})[0]
    return _decode_yolo(raw,transform,LABELS if kind=="vehicle" else {0:"egyptian_plate"},
                        threshold=.28 if kind=="vehicle" else .32,
                        max_results=16 if kind=="vehicle" else 8)


def sampled_frames(video: Path, duration: float, count: int = 5):
    """Yield independent actual frames only; sparse sampling cannot prove violations."""
    count = max(1,min(count,8))
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for n in range(count):
            second = round(duration*(n+.5)/count,2)
            target = folder / f"frame-{n:02d}.jpg"
            run = subprocess.run(
                ["ffmpeg","-hide_banner","-loglevel","error","-y",
                 "-ss",str(second),"-i",str(video),"-frames:v","1",
                 "-q:v","3",str(target)],
                capture_output=True,timeout=45
            )
            if run.returncode != 0 or not target.exists():
                continue
            with Image.open(target) as frame:
                yield second, frame.convert("RGB")


def sample_vehicle_detection(video: Path, metadata: dict) -> dict:
    """Real YOLO detection + provisional IoU associations, NOT BoT-SORT."""
    try:
        duration = float(metadata["duration_seconds"])
        count = min(8,max(2,int(os.getenv("TE_CLOUD_VISION_FRAMES","5"))))
        detections, tracks = [], {}
        previous = []
        next_id = 1
        processed = 0
        for frame_index,(second,image) in enumerate(sampled_frames(video,duration,count)):
            processed += 1
            boxes = predict_frame("vehicle",image)
            matched = set()
            current = []
            for item in boxes:
                best_id,best_iou = None,.28
                for candidate in previous:
                    if candidate["track_id"] in matched or candidate["label"] != item["label"]:
                        continue
                    score = _iou(candidate["box_xyxy"],item["box_xyxy"])
                    if score > best_iou:
                        best_id,best_iou = candidate["track_id"],score
                if best_id is None:
                    best_id=next_id
                    next_id+=1
                matched.add(best_id)
                entry={**item,"second":second,"frame_index":frame_index,
                       "track_id":best_id}
                detections.append(entry)
                current.append(entry)
                tr=tracks.setdefault(best_id,{
                    "track_id":best_id,"label":item["label"],
                    "observations":[],"make":None,"color":None})
                tr["observations"].append({
                    "second":second,"box_xyxy":item["box_xyxy"],
                    "confidence":item["confidence"]})
            previous=current
        return {"status":"completed","model":"YOLOv8n COCO / ONNX CPU",
                "method":"sparse-frame IoU association (not BoT-SORT)",
                "tracks":list(tracks.values())[:80],
                "detections":detections[:250],"sampled_frames":processed,
                "stride":None,
                "note":"Real CPU ONNX detections on a few sampled frames; track IDs are "
                       "provisional and may change. Sparse samples cannot prove traffic offenses."}
    except Exception as exc:
        return {"status":"failed","tracks":[],"detections":[],
                "model":"YOLOv8n COCO / ONNX CPU",
                "note":f"{type(exc).__name__}: {str(exc)[:190]}"}


def _ocr_plate(crop: Image.Image):
    """Tesseract Arabic+English TSV; tentative OCR only, never a confirmed plate."""
    from PIL import ImageEnhance, ImageOps
    upscale = crop.resize((max(100,crop.width*3),max(38,crop.height*3)),
                          Image.Resampling.BICUBIC)
    enhanced = ImageEnhance.Contrast(ImageOps.autocontrast(upscale.convert("L"))).enhance(1.5)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/"plate.png"
        enhanced.save(path)
        result = subprocess.run(
            ["tesseract",str(path),"stdout","-l","ara+eng","--psm","7","tsv"],
            text=True,capture_output=True,timeout=15
        )
    if result.returncode != 0:
        raise RuntimeError("Arabic Tesseract OCR is unavailable. Install tesseract-ocr-ara.")
    words, confidences = [],[]
    for row in result.stdout.splitlines()[1:]:
        fields=row.split("\t",11)
        if len(fields)<12:
            continue
        word=fields[11].strip()
        try: conf=float(fields[10])
        except ValueError: continue
        if conf > 0 and word:
            words.append(word)
            confidences.append(conf/100)
    raw=" ".join(words)[:40]
    return raw, round(sum(confidences)/len(confidences),3) if confidences else 0.0


def sample_egyptian_plates(video: Path, duration: float) -> dict:
    """Egypt-trained YOLOv8n ONNX plate locator + tentative Arabic OCR."""
    try:
        count = min(8,max(2,int(os.getenv("TE_CLOUD_PLATE_FRAMES","5"))))
        candidates=[]
        detected=0
        processed=0
        for second,image in sampled_frames(video,float(duration),count):
            processed+=1
            for item in predict_frame("plate",image)[:5]:
                detected+=1
                x1,y1,x2,y2=[int(v) for v in item["box_xyxy"]]
                if x2<=x1 or y2<=y1:
                    continue
                crop=image.crop((x1,y1,x2,y2))
                # OCR is often unreadable on wide shots or small night-time plates.
                if crop.width < 16 or crop.height < 9:
                    continue
                text,conf=_ocr_plate(crop)
                if not text or conf < .15:
                    continue
                candidates.append({
                    "raw_text":text,
                    "confidence":conf,
                    "detector_confidence":item["confidence"],
                    "second":second,
                    "bbox":item["box_xyxy"],
                    "requires_human_review":True
                })
        candidates.sort(key=lambda x:-x["confidence"])
        return {"status":"completed","model":"Egyptian YOLOv8n plate ONNX + Tesseract ara/eng",
                "value":None,"candidates":candidates[:18],
                "plates_detected":detected,
                "sampled_frames":processed,
                "note":"Real Egypt-trained plate detection; OCR readings are uncertain, not "
                       "verified. No text is inferred when pixels are too small or blurry. "
                       "Only a human reviewer may confirm any reading."}
    except Exception as exc:
        return {"status":"failed","model":"Egyptian YOLOv8n ONNX + Tesseract",
                "value":None,"candidates":[],
                "note":f"{type(exc).__name__}: {str(exc)[:190]}"}
