"""Real evidence metadata / thumbnails plus strictly opt-in AI inference.

No detector, ASR, license plate or violation result is synthesized when the
required model is absent. Hardware integration is outside this module.
"""
import os
import subprocess
import tempfile
from pathlib import Path


def inspect_video(original: Path, preview: Path, metadata: dict):
    second = min(max(metadata["duration_seconds"] / 2, 0.5), 12)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", str(second), "-i", str(original),
               "-frames:v", "1", "-q:v", "3", str(preview)]
    subprocess.run(command, check=True, capture_output=True, timeout=50)
    if not preview.is_file() or preview.stat().st_size == 0:
        raise RuntimeError("Failed to extract evidence preview")

    result = {
        "evidence": {"video_metadata": metadata, "keyframe_second": round(second, 2),
                     "keyframe_extracted": True},
        "vehicle_detection": {"status": "not_configured", "detections": [],
                              "note": "Set TE_YOLO_MODEL and install requirements-ai.txt to enable actual inference."},
        "transcription": {"status": "not_configured", "text": None},
        "plate_recognition": {"status": "not_implemented", "value": None},
        "object_tracking": {"status": "not_implemented", "tracks": []},
        "violation_assessment": {"status": "not_implemented", "conclusion": None},
        "review_status": "unreviewed",
    }

    model_name = os.environ.get("TE_YOLO_MODEL", "").strip()
    if model_name:
        try:
            from ultralytics import YOLO
            model = YOLO(model_name)
            predictions = model.predict(source=str(preview), conf=0.30, verbose=False, device="cpu")
            detections = []
            for prediction in predictions:
                for item in prediction.boxes:
                    index = int(item.cls[0].item())
                    label = str(prediction.names[index])
                    if label not in {"car", "truck", "bus", "motorcycle"}:
                        continue
                    detections.append({
                        "label": label, "confidence": round(float(item.conf[0].item()), 4),
                        "box_xyxy": [round(float(v), 1) for v in item.xyxy[0].tolist()],
                        "frame_second": round(second, 2),
                    })
            result["vehicle_detection"] = {
                "status": "completed", "detections": detections,
                "note": "Detections from one actual frame only. Not vehicle tracking or violation recognition.",
                "model": model_name,
            }
        except Exception as exc:
            result["vehicle_detection"] = {"status": "failed", "detections": [],
                                            "note": str(exc)[:250]}

    speech_model = os.environ.get("TE_ASR_MODEL", "").strip()
    if speech_model and metadata.get("has_audio"):
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "speech.wav"
            try:
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-i", str(original), "-vn", "-ac", "1", "-ar", "16000",
                                str(wav)], check=True, capture_output=True, timeout=60)
                from faster_whisper import WhisperModel
                model = WhisperModel(speech_model, device="cpu", compute_type="int8")
                segments, info = model.transcribe(str(wav), beam_size=3)
                result["transcription"] = {
                    "status": "completed",
                    "text": " ".join(segment.text.strip() for segment in segments).strip(),
                    "language": info.language, "model": speech_model,
                }
            except Exception as exc:
                result["transcription"] = {"status": "failed", "text": None,
                                           "note": str(exc)[:250]}
    elif not metadata.get("has_audio"):
        result["transcription"] = {"status": "unavailable", "text": None,
                                   "note": "Recording has no audio track"}
    return result
