"""Video evidence pipeline with explicit capability / uncertainty states.

All real AI stages are optional, independently fail-safe, and must preserve
their model/source details. No fabricated findings or government decisions.
"""
import os
import subprocess
import tempfile
from pathlib import Path

from .intent import parse_driver_claim
from .tracker import track_vehicles
from .qwen import describe_video
from .plate import scan_plates
from .assessment import match_target, assess_potential_events


def transcribe_audio(original: Path, metadata: dict) -> dict:
    if not metadata.get("has_audio"):
        return {"status": "unavailable", "text": None,
                "note": "The uploaded video has no audio track."}
    model_name = os.getenv("TE_ASR_MODEL", "").strip()
    if not model_name:
        return {"status": "not_configured", "text": None,
                "note": "Install faster-whisper and set TE_ASR_MODEL."}
    try:
        from faster_whisper import WhisperModel
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "speech.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(original), "-vn", "-ac", "1",
                            "-ar", "16000", str(wav)], check=True, capture_output=True, timeout=65)
            model = WhisperModel(model_name,
                                 device=os.getenv("TE_ASR_DEVICE", "cpu"),
                                 compute_type=os.getenv("TE_ASR_COMPUTE_TYPE", "int8"),
                                 local_files_only=os.getenv("TE_ASR_ALLOW_DOWNLOAD", "0") != "1")
            segments, info = model.transcribe(str(wav), beam_size=3,
                                               vad_filter=True)
            parts = []
            timestamps = []
            for segment in segments:
                parts.append(segment.text.strip())
                timestamps.append({"start": round(segment.start, 2),
                                   "end": round(segment.end, 2),
                                   "text": segment.text.strip()})
            return {"status": "completed", "text": " ".join(parts).strip(),
                    "segments": timestamps[:100], "language": info.language,
                    "model": model_name,
                    "note": "Automated transcript; may be inaccurate in traffic noise."}
    except Exception as exc:
        return {"status": "failed", "text": None, "model": model_name,
                "note": f"{type(exc).__name__}: {str(exc)[:250]}"}


def inspect_video(original: Path, preview: Path, metadata: dict, on_stage=None) -> dict:
    def progress(stage):
        if on_stage:
            on_stage(stage)
    progress('decoding_video')
    duration = float(metadata["duration_seconds"])
    second = min(max(duration / 2, 0.5), 12)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(second), "-i", str(original),
                    "-frames:v", "1", "-q:v", "3", str(preview)],
                   check=True, capture_output=True, timeout=50)
    if not preview.is_file() or preview.stat().st_size == 0:
        raise RuntimeError("Failed to extract an actual evidence frame")

    progress('transcribing_audio')
    speech = transcribe_audio(original, metadata)
    progress('interpreting_driver_claim')
    claim = parse_driver_claim(speech.get("text"))
    progress('tracking_vehicles')
    tracking = track_vehicles(original, metadata)
    progress('qwen_visual_reasoning')
    qwen = describe_video(original, duration, claim)
    progress('reading_plates')
    plates = scan_plates(original, duration)
    progress('reconciling_evidence')
    target = match_target(claim, tracking)
    assessment = assess_potential_events(claim, qwen)
    sample_detections = tracking.get("detections", [])
    return {
        "pipeline_version": "2.0",
        "evidence": {"video_metadata": metadata, "keyframe_second": round(second, 2),
                     "keyframe_extracted": True,
                     "note": "Original bytes preserved. Uploaded time is not capture time."},
        "transcription": speech,
        "driver_claim": claim,
        "vehicle_detection": {
            "status": tracking["status"],
            "detections": sample_detections,
            "model": tracking.get("model"),
            "note": tracking.get("note"),
            "scope": "sampled_video_frames" if tracking["status"] == "completed" else None
        },
        "object_tracking": {
            "status": tracking["status"],
            "method": tracking.get("method"),
            "tracks": tracking.get("tracks", []),
            "sampled_frames": tracking.get("sampled_frames"),
            "stride": tracking.get("stride"),
            "note": tracking.get("note"),
        },
        "visual_reasoning": qwen,
        "target_matching": target,
        "plate_recognition": plates,
        "violation_assessment": assessment,
        "vehicle_information": {
            "status": "limited_to_visible_evidence",
            "official_registry_access": False,
            "note": "No access to vehicle owner identity, official plate registry or vehicle history."
        },
        "review_status": "unreviewed"
    }
