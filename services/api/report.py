"""Honest preliminary evidence PDF for operator inspection.

PDF pages state model statuses and hypothetical observations, not legal guilt.
The source SHA-256 always refers to the uploaded original video bytes.
"""
from io import BytesIO
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def build_report(incident, preview_path=None):
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    dark = colors.HexColor("#111F2D")
    muted = colors.HexColor("#526779")
    cyan = colors.HexColor("#13A8BB")
    y = height - 145

    def page_header():
        c.setFillColor(dark)
        c.rect(0, height - 112, width, 112, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 23)
        c.drawString(42, height - 60, "TRAFFIC ENHANCER")
        c.setFont("Helvetica", 10)
        c.drawString(44, height - 81, "PRELIMINARY EVIDENCE INTELLIGENCE")
        c.setFillColor(colors.HexColor("#B91C1C"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(42, height - 129, "NOT VERIFIED  |  NO OFFICIAL TRAFFIC CITATION")

    def ensure(space=36):
        nonlocal y
        if y < 65 + space:
            c.showPage()
            page_header()
            y = height - 153

    def section(title):
        nonlocal y
        ensure(48)
        y -= 12
        c.setFillColor(cyan)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(42, y, title.upper())
        y -= 23

    def row(label, value):
        nonlocal y
        ensure(22)
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(42, y, label.upper()[:25])
        c.setFillColor(dark)
        c.setFont("Helvetica", 9)
        safe = str(value if value is not None else "Unavailable").encode("ascii", "replace").decode("ascii")
        c.drawString(185, y, safe[:83])
        y -= 20

    def paragraph(value):
        nonlocal y
        safe = str(value or "Not available").encode("ascii", "replace").decode("ascii")
        for line in textwrap.wrap(safe, width=95, break_long_words=True) or ["Not available"]:
            ensure(16)
            c.setFillColor(dark)
            c.setFont("Helvetica", 9)
            c.drawString(42, y, line)
            y -= 15
        y -= 7

    page_header()
    info = incident.get("analysis") or {}
    track = info.get("object_tracking") or {}
    ocr = info.get("plate_recognition") or {}
    speech = info.get("transcription") or {}
    claim = info.get("driver_claim") or {}
    qwen = info.get("visual_reasoning") or {}
    assessment = info.get("violation_assessment") or {}

    section("Evidence integrity")
    for label, value in (
        ("Incident ID", incident["id"]),
        ("Uploaded at (UTC)", incident["created_at"]),
        ("Source filename", incident["filename"]),
        ("SHA-256", incident["sha256"]),
        ("Selected source range", (
            f"{incident['video'].get('selection', {}).get('start_seconds', 0)} - "
            f"{incident['video'].get('selection', {}).get('end_seconds', incident['duration'])} sec"
        )),
        ("Source duration", incident["video"].get("selection", {}).get("source_duration_seconds", incident["duration"])),
        ("Clip SHA-256", incident["video"].get("selection", {}).get("clip_sha256", incident["sha256"])),
        ("Duration", str(incident["duration"]) + " seconds"),
        ("Frames", str(incident["video"].get("width")) + " x " + str(incident["video"].get("height"))),
    ):
        row(label, value)


    # Embed an ACTUAL decoded frame from the submitted recording. Never invent
    # plate close-ups or labels. The rest of the original footage remains linked
    # by its immutable source SHA-256 in the report.
    if preview_path is not None and preview_path.is_file():
        ensure(240)
        section("Source recording - actual unannotated frame")
        reader = ImageReader(str(preview_path))
        natural_w, natural_h = reader.getSize()
        scale = min(505 / natural_w, 210 / natural_h)
        display_w, display_h = natural_w * scale, natural_h * scale
        c.drawImage(reader, 42, y - display_h, width=display_w, height=display_h,
                    mask="auto")
        y -= display_h + 10
        paragraph("Image is taken directly from the uploaded video. This single frame does not prove a traffic offense.")

    section("AI execution state")
    for label, value in (
        ("Speech", speech.get("status")),
        ("Video tracker", track.get("status")),
        ("Qwen2.5-VL", qwen.get("status")),
        ("Egyptian plate OCR", ocr.get("status")),
        ("Incident assessment", assessment.get("status")),
        ("Human review", info.get("review_status")),
    ):
        row(label, value)

    section("Driver-stated description - unverified")
    paragraph(claim.get("verbatim") or "No usable audio description was available.")
    section("Machine visual interpretation - unverified")
    observations = qwen.get("observations") or {}
    paragraph(observations.get("scene_summary") or qwen.get("note") or "Vision model did not run.")
    section("Potential events requiring human review")
    candidates = assessment.get("candidates") or []
    if not candidates:
        paragraph("No visually grounded potential events were reported. This is not a declaration that the driving was lawful.")
    else:
        for item in candidates[:8]:
            paragraph(f"{item['category']} at {item.get('time_seconds')}s. "
                      f"AI observation: {item.get('visual_evidence')}. "
                      f"Uncertainty: {item.get('uncertainty')}. Human review required.")
    section("License plate / vehicle information")
    paragraph(f"Plate OCR candidates: {len(ocr.get('candidates', []))}. "
              "No plate string is verified. No vehicle owner or official registry was queried.")
    section("Evidence-handling limitations")
    paragraph("AI may be mistaken about traffic signals, road boundaries, vehicle identity, and object motion. "
              "Video frames may be sampled, so crucial transitions could be absent.")
    paragraph("Original uploaded file must be reviewed for any real-world decision. "
              "Recording time and GPS are not inferred from upload metadata. "
              "A SHA-256 hash verifies only the stored uploaded bytes, not camera provenance.")
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    ensure(32)
    c.line(42, 51, width - 42, 51)
    c.setFont("Helvetica", 8)
    c.setFillColor(muted)
    c.drawString(42, 37, "Traffic Enhancer / AI-assisted preliminary evidence / Not for automated enforcement")
    c.save()
    return output.getvalue()
