"""Regressions for truthfully labeled evidence PDF and actual overlay frame."""
from io import BytesIO

from PIL import Image
from pypdf import PdfReader

from services.api.report import build_report, report_model_name


def sample_case():
    return {
        "id": "8" * 32,
        "filename": "1014.mp4",
        "created_at": "2026-10-27T20:02:58+00:00",
        "duration": 26.8,
        "sha256": "a"*64,
        "video": {"width": 854, "height": 480, "selection": {
            "start_seconds": 115.4, "end_seconds": 142.2,
            "source_duration_seconds": 211.905,
            "clip_sha256": "b"*64}},
        "analysis": {
            "review_status": "unreviewed",
            "object_tracking": {"status": "completed",
                "tracks": [{"track_id": i} for i in range(26)]},
            "vehicle_detection": {"status":"completed",
                "detections": [{"label":"car"}]*53},
            "transcription": {"status":"completed"},
            "visual_reasoning": {"status":"completed",
                "model":"nvidia/nemotron-3.5-super-vl:free",
                "requested_model":"qwen/qwen3.8-27b:free",
                "routing":"OpenRouter free multimodal router",
                "observations": {"scene_summary":"Cars and pedestrians in a street",
                                 "potential_events":[]}},
            "full_length_video": {"status":"completed",
                "inference_fps":3, "analyzed_frames":82,
                "duration_seconds":26.8},
            "plate_recognition": {"status":"completed", "candidates":[]},
            "violation_assessment": {"status":"inconclusive", "candidates":[]},
        }
    }


def test_model_name_is_served_model_not_configured_qwen():
    info=sample_case()["analysis"]["visual_reasoning"]
    assert report_model_name(info)=="nvidia/nemotron-3.5-super-vl:free"
    assert report_model_name({"status":"failed"})=="Not reported"


def test_pdf_explains_completed_without_readable_plates():
    doc=PdfReader(BytesIO(build_report(sample_case())))
    text="\n".join(page.extract_text() for page in doc.pages)
    assert "nvidia/nemotron-3.5-super-vl:free" in text
    assert "QWEN2.5-VL" not in text
    assert "Plate OCR candidates" in text
    assert "No plate string is verified" in " ".join(text.split())
    assert "26" in text
    assert "82" in text
    assert "53" in text
    assert "115.4" in text and "142.2" in text
    assert "NO OFFICIAL TRAFFIC CITATION" in text


def test_pdf_shows_real_annotated_and_original_frames_when_available(tmp_path):
    original=tmp_path/"original.jpg"
    overlay=tmp_path/"tracked.jpg"
    Image.new("RGB",(320,180),(140,140,140)).save(original)
    Image.new("RGB",(320,180),(160,160,160)).save(overlay)
    pdf=build_report(sample_case(), original, overlay)
    reader=PdfReader(BytesIO(pdf))
    text="\n".join(page.extract_text() for page in reader.pages)
    assert "ACTUAL UNANNOTATED FRAME" in text
    assert "YOLO VEHICLE OVERLAY" in text
    embedded=sum(len(page.images) for page in reader.pages)
    assert embedded>=2
