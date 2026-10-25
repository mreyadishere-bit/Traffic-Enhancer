"""Operator-facing preliminary English PDF; no unverified legal claims."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_report(incident):
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    c.setFillColor(colors.HexColor("#0F172A"))
    c.rect(0, height - 118, width, 118, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(42, height - 62, "TRAFFIC ENHANCER")
    c.setFont("Helvetica", 10)
    c.drawString(43, height - 84, "PRELIMINARY EVIDENCE REPORT")
    y = height - 148
    c.setFillColor(colors.HexColor("#B91C1C"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(42, y, "NOT VERIFIED - NOT AN OFFICIAL CITATION")
    y -= 35
    a = incident.get("analysis") or {}
    evidence = a.get("evidence") or {}
    detection = a.get("vehicle_detection") or {}
    transcript = a.get("transcription") or {}
    lines = [
        ("Report ID", incident["id"]),
        ("Captured / uploaded", incident["created_at"]),
        ("Original filename", incident["filename"][:65]),
        ("File SHA-256", incident["sha256"]),
        ("Video duration", str(incident["duration"]) + " seconds"),
        ("Video dimensions", f"{incident['video'].get('width')} x {incident['video'].get('height')}"),
        ("Extracted evidence frame", str(evidence.get("keyframe_second")) + " seconds"),
        ("Vehicle detection", detection.get("status", "unavailable")),
        ("Frame vehicle detections", str(len(detection.get("detections", [])))),
        ("Speech transcription", transcript.get("status", "unavailable")),
        ("License plate OCR", (a.get("plate_recognition") or {}).get("status", "unavailable")),
        ("Potential violation", (a.get("violation_assessment") or {}).get("status", "unavailable")),
        ("Human review", a.get("review_status", "unreviewed")),
    ]
    for label, value in lines:
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(42, y, label.upper())
        c.setFillColor(colors.HexColor("#172033"))
        c.setFont("Helvetica", 10)
        c.drawString(192, y, str(value)[:77])
        y -= 28
    y -= 14
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(42, y, "LIMITATIONS")
    y -= 24
    for line in [
        "This document reports only executed analysis stages.",
        "No plate number, vehicle identity or traffic offense is inferred when unavailable.",
        "AI detections are not legal findings. Human review and authorization are required.",
        "Metadata upload time may differ from the actual recording time.",
        "Retain and independently verify the original evidence before relying on this report.",
    ]:
        c.setFont("Helvetica", 9)
        c.drawString(42, y, line)
        y -= 19
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.line(42, 57, width - 42, 57)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(42, 42, "Traffic Enhancer | Preliminary AI-assisted evidence document")
    c.save()
    return stream.getvalue()
