"""Human-review evidence report; renders only data obtained from the actual case."""
from io import BytesIO
import os
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

W,H=A4
DARK=colors.HexColor("#172832")
MUTED=colors.HexColor("#607783")
ACCENT=colors.HexColor("#227B75")
LINE=colors.HexColor("#DFE7E7")
WARM=colors.HexColor("#A06438")

def _font():
    if "TEUnicode" in pdfmetrics.getRegisteredFontNames():
        return "TEUnicode"
    for path in [os.getenv("TE_REPORT_FONT_PATH", ""),
                 "C:/Windows/Fonts/tahoma.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if path and Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("TEUnicode",path))
                return "TEUnicode"
            except Exception:
                continue
    return "Helvetica"

def _text(value,font):
    value=str(value if value is not None else "Unavailable")
    if re.search(r"[\u0600-\u06ff]",value):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            value=get_display(arabic_reshaper.reshape(value))
        except ImportError:
            pass
    if font=="Helvetica":
        return value.encode("latin-1","replace").decode("latin-1")
    return value

def build_report(incident,preview_path=None):
    out=BytesIO()
    c=canvas.Canvas(out,pagesize=A4)
    c.setTitle("Traffic Enhancer — Preliminary evidence")
    font=_font()
    y=H-52
    page=0
    a=incident.get("analysis") or {}
    review=incident.get("review") or {}
    selection=(incident.get("video") or {}).get("selection") or {}
    vision=a.get("visual_reasoning") or {}
    tracks=a.get("object_tracking") or {}
    speech=a.get("transcription") or {}
    plate=a.get("plate_recognition") or {}
    assessment=a.get("violation_assessment") or {}

    def header_footer():
        c.setStrokeColor(LINE);c.line(39,49,W-39,49)
        c.setFont(font,8);c.setFillColor(MUTED)
        c.drawString(40,35,"TRAFFIC ENHANCER / PRELIMINARY REVIEW ONLY")
        c.drawRightString(W-40,35,str(page))

    def new_page():
        nonlocal y,page
        if page:
            header_footer()
            c.showPage()
        page+=1
        y=H-59
        c.setFillColor(ACCENT);c.rect(40,H-40,31,3,stroke=0,fill=1)

    def ensure(space=25):
        if y<65+space:new_page()

    def heading(label):
        nonlocal y
        ensure(42);y-=17
        c.setFillColor(ACCENT);c.setFont(font,10)
        c.drawString(40,y,_text(label.upper(),font))
        y-=22

    def write(value,small=False):
        nonlocal y
        source=str(value if value is not None else "Not available")
        for paragraph in source.splitlines() or [""]:
            lines=textwrap.wrap(paragraph, width=84,
                                break_long_words=True) or [""]
            for line in lines:
                ensure(16)
                c.setFont(font,8.7 if small else 9.5)
                c.setFillColor(DARK)
                s=_text(line,font)
                if re.search(r"[\u0600-\u06ff]",line):
                    c.drawRightString(W-40,y,s)
                else:
                    c.drawString(40,y,s)
                y-=16
        y-=6

    def field(label,value):
        nonlocal y
        ensure(28)
        c.setFont(font,8);c.setFillColor(MUTED)
        c.drawString(40,y,label.upper())
        v=str(value if value is not None else "Unavailable")
        chunks=textwrap.wrap(v,59,break_long_words=True) or [""]
        for ix,txt in enumerate(chunks[:4]):
            if ix:y-=15;ensure(16)
            c.setFont(font,9);c.setFillColor(DARK)
            display=_text(txt,font)
            if re.search(r"[\u0600-\u06ff]",txt):
                c.drawRightString(W-40,y,display)
            else:
                c.drawString(202,y,display)
        y-=23

    new_page()
    c.setFillColor(DARK);c.setFont(font,24)
    c.drawString(40,y,"TRAFFIC ENHANCER");y-=23
    c.setFont(font,10);c.setFillColor(MUTED)
    c.drawString(40,y,"PRELIMINARY EVIDENCE INTELLIGENCE");y-=34
    c.setFillColor(colors.HexColor("#EDF4F3"))
    c.roundRect(40,y-43,W-80,54,7,stroke=0,fill=1)
    c.setFillColor(WARM);c.setFont(font,10)
    c.drawString(52,y-14,"NOT VERIFIED / NOT AN OFFICIAL TRAFFIC CITATION")
    c.setFillColor(MUTED);c.setFont(font,8)
    c.drawString(52,y-31,"Visual observations and reviewer notes are distinct from proven offenses.")
    y-=76

    heading("Case at a glance")
    field("Reference",incident.get("id"))
    field("Original recording",incident.get("filename"))
    field("Uploaded (UTC)",incident.get("created_at"))
    field("Selected source",str(selection.get("start_seconds",0))+" - "+
          str(selection.get("end_seconds",incident.get("duration")))+" seconds")
    field("Review status",review.get("status","unreviewed").replace("_"," "))
    field("Proposed events",str(len(assessment.get("candidates") or []))+" (unverified)")
    if preview_path and Path(preview_path).is_file():
        heading("Source evidence frame / unannotated")
        reader=ImageReader(str(preview_path))
        nw,nh=reader.getSize();factor=min((W-80)/max(1,nw),218/max(1,nh))
        fw,fh=nw*factor,nh*factor
        ensure(fh+40)
        c.drawImage(reader,40,y-fh,width=fw,height=fh,mask="auto")
        y-=fh+14
        write("Actual decoded video frame, not a visual proof of a traffic offense.",True)

    heading("What the driver reported")
    if review.get("manual_description"):
        write("USER-SUPPLIED CLAIM (not verified by video):",True)
        write(review["manual_description"])
    elif (a.get("driver_claim") or {}).get("verbatim"):
        write("AUTOMATED SPEECH TRANSCRIPT (unverified):",True)
        write(a["driver_claim"]["verbatim"])
    else:
        write("No usable driver description available.")
    if speech.get("status")=="failed":
        write("Speech processing problem: "+str(speech.get("note") or "unknown"),True)

    heading("Visual reasoning")
    details=vision.get("observations") or {}
    write(details.get("scene_summary") or
          "Qwen2.5-VL status: "+str(vision.get("status","not configured")))
    events=assessment.get("candidates") or []
    if not events:
        write("No visually supported event was returned. This does not prove that no offense occurred.",True)
    for i,event in enumerate(events[:8],1):
        write(str(i)+". "+str(event.get("category","unknown")).replace("_"," ")+
              " / clip T+"+str(event.get("time_seconds"))+"s")
        write(str(event.get("visual_evidence",""))+" | Uncertainty: "+
              str(event.get("uncertainty","unverified")),True)

    heading("Reviewer findings")
    field("Selected track",review.get("selected_track_id"))
    field("Event time in clip",review.get("reviewed_event_second"))
    field("Provisional tracks",len(tracks.get("tracks") or []))
    write(review.get("review_note") or "No human reviewer note was saved.")
    write("Tracking IDs may change; selected tracks do not confirm a driver's or vehicle owner's identity.",True)

    heading("AI stage availability")
    for name,stage in [("Speech",speech),("Vehicle tracking",tracks),
                       ("Qwen2.5-VL",vision),("Plate OCR",plate),
                       ("Event assessment",assessment)]:
        field(name,stage.get("status","unavailable"))
    field("OCR candidates",len(plate.get("candidates") or []))
    write("OCR readings, when present, are unverified. No official vehicle registry was accessed.",True)

    heading("Evidence provenance")
    field("Source SHA-256",incident.get("sha256"))
    field("Clip SHA-256",selection.get("clip_sha256",incident.get("sha256")))
    field("Source duration",selection.get("source_duration_seconds",incident.get("duration")))
    write("SHA-256 confirms the stored uploaded bytes against this digest, not the event origin. "
          "Upload timestamp is not proven recording time. "
          "No automated finding here creates any official legal liability.",True)
    header_footer()
    c.save()
    return out.getvalue()
