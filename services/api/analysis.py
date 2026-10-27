"""Video evidence pipeline with explicit capability / uncertainty states.

All real AI stages are optional, independently fail-safe, and must preserve
their model/source details. No fabricated findings or government decisions.
"""
import os
from functools import lru_cache
import subprocess
import tempfile
from pathlib import Path

from .visual_evidence import render_sampled_evidence
from .full_video import make_annotated_full_clip
from .intent import parse_driver_claim
from .tracker import track_vehicles
from .qwen import describe_video
from .plate import scan_plates
from .assessment import match_target, assess_potential_events


@lru_cache(maxsize=2)
def loaded_whisper_model(model_name: str, device: str, compute_type: str,
                         local_files_only: bool):
    """Reuse local model weights between reports; preserves opt-in download policy."""
    from faster_whisper import WhisperModel
    return WhisperModel(model_name, device=device, compute_type=compute_type,
                        local_files_only=local_files_only)


def transcribe_via_groq(original: Path, model_name: str) -> dict:
    """Opt-in HTTPS API transcription with actual clip audio, not a guessed statement."""
    import httpx
    api_key = os.getenv("TE_GROQ_API_KEY", "").strip()
    if not api_key:
        return {"status": "not_configured", "text": None,
                "note": "Set TE_GROQ_API_KEY in the hosting provider's secrets."}
    with tempfile.TemporaryDirectory() as temp:
        flac = Path(temp) / "speech.flac"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(original), "-vn", "-map", "0:a:0",
                        "-ac", "1", "-ar", "16000", "-c:a", "flac", str(flac)],
                       capture_output=True, check=True, timeout=65)
        if not flac.is_file() or flac.stat().st_size > 24 * 1024 * 1024:
            raise ValueError("Audio exceeds Groq free-tier upload limit")
        with flac.open("rb") as f:
            response = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": "Bearer " + api_key},
                files={"file": ("speech.flac", f, "audio/flac")},
                data={"model": model_name, "response_format": "verbose_json",
                      "temperature": "0"},
                timeout=httpx.Timeout(100, connect=12))
        response.raise_for_status()
        result = response.json()
        segments = []
        for part in (result.get("segments") or [])[:100]:
            if isinstance(part, dict):
                segments.append({"start": round(float(part.get("start", 0)),2),
                                 "end": round(float(part.get("end", 0)),2),
                                 "text": str(part.get("text", "")).strip()})
        return {"status": "completed", "text": str(result.get("text","")).strip(),
                "segments": segments, "language": result.get("language"),
                "model": model_name, "provider": "groq_operator_opt_in",
                "note": "Audio sent to Groq under the configured API agreement; "
                        "transcription is unverified."}


def transcribe_audio(original: Path, metadata: dict) -> dict:
    if not metadata.get("has_audio"):
        return {"status": "unavailable", "text": None,
                "note": "The uploaded video has no audio track."}
    remote_model = os.getenv("TE_GROQ_ASR_MODEL", "").strip()
    if remote_model:
        try:
            return transcribe_via_groq(original, remote_model)
        except Exception as exc:
            # This is a diagnostic message, never expose operator credentials.
            secret = os.getenv("TE_GROQ_API_KEY", "")
            details = str(exc).replace(secret, "[redacted]") if secret else str(exc)
            return {"status": "failed", "text": None, "model": remote_model,
                    "provider": "groq_operator_opt_in",
                    "note": f"{type(exc).__name__}: {details[:220]}"}
    model_name = os.getenv("TE_ASR_MODEL", "").strip()
    if not model_name:
        return {"status": "not_configured", "text": None,
                "note": "Set TE_GROQ_ASR_MODEL and TE_GROQ_API_KEY for cloud speech, or TE_ASR_MODEL for local Whisper."}
    try:
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "speech.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(original), "-vn", "-ac", "1",
                            "-ar", "16000", str(wav)], check=True, capture_output=True, timeout=65)
            model = loaded_whisper_model(model_name,
                                         os.getenv("TE_ASR_DEVICE", "cpu"),
                                         os.getenv("TE_ASR_COMPUTE_TYPE", "int8"),
                                         os.getenv("TE_ASR_ALLOW_DOWNLOAD", "0") != "1")
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
    progress('reading_plates')
    plates = scan_plates(original, duration)
    progress('rendering_annotated_evidence')
    visual_evidence = render_sampled_evidence(
        original, preview.parent, preview.stem, tracking, plates)
    # Produce the full selected clip at authentic sampled source times;
    # independent of Qwen/Groq credentials or inferred traffic violations.
    progress('starting_full_length_annotation')
    full_video = (make_annotated_full_clip(
        original, preview.parent, preview.stem, duration,
        progress=progress) if __import__("os").getenv("TE_CLOUD_VISION","0") == "1"
        else {"status":"not_configured"})
    # Never hold the annotated evidence export hostage to optional remote VLM.
    # Qwen/OpenRouter may be unavailable, blocked, or rate-limited; CPU evidence
    # and tentative OCR should still be produced first.
    progress('qwen_visual_reasoning')
    qwen = describe_video(original, duration, claim)
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
        "annotated_evidence": visual_evidence,
        "full_length_video": full_video,
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
