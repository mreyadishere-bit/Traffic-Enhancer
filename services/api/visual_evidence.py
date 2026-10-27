"""Evidence visualization from actual YOLO sample timestamps.

Never synthesize continuous tracking: only detection times are annotated.
All results are derived assets; original evidence remains byte-for-byte intact.
"""
from __future__ import annotations

import csv
import io
import math
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _foot(box):
    return ((float(box[0]) + float(box[2])) / 2, float(box[3]))


def provisional_pixel_motion(tracks: list) -> list[dict]:
    """Measured image displacement, NOT metres or km/h.

    A sparse IoU-associated ID is not reliable proof of stable identity.
    Only report pixels/s when at least two ordered observations exist.
    """
    measurements=[]
    for track in tracks:
        obs=sorted((o for o in track.get("observations", [])
                    if isinstance(o.get("second"),(int,float)) and
                    len(o.get("box_xyxy", []))==4),key=lambda o:o["second"])
        if len(obs)<2:
            continue
        distance=0.0
        elapsed=0.0
        for a,b in zip(obs,obs[1:]):
            dt=float(b["second"])-float(a["second"])
            if dt<=0:
                continue
            ax,ay=_foot(a["box_xyxy"])
            bx,by=_foot(b["box_xyxy"])
            distance+=math.hypot(bx-ax,by-ay)
            elapsed+=dt
        if elapsed<=0:
            continue
        measurements.append({
            "track_id":track.get("track_id"),"vehicle":track.get("label"),
            "observations":len(obs),"start_s":round(float(obs[0]["second"]),2),
            "end_s":round(float(obs[-1]["second"]),2),
            "image_path_px":round(distance,1),
            "image_motion_px_s":round(distance/elapsed,2),
            "distance_m":None,"speed_kmh":None,
            "confidence":"provisional_sparse_iou",
        })
    return measurements


def _font(size=16):
    try:
        return ImageFont.truetype("DejaVuSans.ttf",size)
    except OSError:
        return ImageFont.load_default()


def annotate_frame(source: Image.Image, second: float, detections: list,
                   plate_regions: list | None = None) -> Image.Image:
    """Actual decoded source frame at 'second'; draw only same-sample boxes."""
    image=source.convert("RGB").copy()
    d=ImageDraw.Draw(image)
    w,h=image.size
    label_font=_font(max(12,min(18,w//55)))
    header_font=_font(max(15,min(23,w//43)))
    # Header declares uncertainty so this is not mistaken for verified footage.
    d.rectangle((0,0,w,min(h,39)),fill=(12,29,38))
    d.text((11,8),f"YOLO SAMPLED FRAME  {second:.2f}s  |  PROVISIONAL IDs",
           fill=(221,247,247),font=header_font)
    def mark(item,color,prefix):
        values=item.get("box_xyxy") or item.get("bbox")
        if not isinstance(values,(tuple,list)) or len(values)!=4:
            return
        try:
            x1,y1,x2,y2=[max(0,float(v)) for v in values]
        except (TypeError,ValueError):
            return
        x1=min(w-1,x1);x2=min(w-1,x2);y1=min(h-1,y1);y2=min(h-1,y2)
        if x2<=x1 or y2<=y1:
            return
        d.rectangle((x1,y1,x2,y2),outline=color,width=max(2,w//350))
        caption=prefix
        text_bbox=d.textbbox((0,0),caption,font=label_font)
        rw=text_bbox[2]+12
        ry=max(41,y1-25)
        rx=min(max(0,int(x1)),max(0,w-rw))
        d.rectangle((rx,ry,rx+rw,ry+22),fill=(12,29,38))
        d.text((rx+6,ry+2),caption,fill=color,font=label_font)
    for item in detections[:80]:
        track=item.get("track_id")
        label=f"{item.get('label','vehicle')} #{track if track is not None else '?'} {float(item.get('confidence',0)):.0%}"
        mark(item,(84,224,241),label)
    for item in (plate_regions or [])[:20]:
        mark(item,(252,193,90),"plate?  unverified")
    return image


def render_sampled_evidence(video: Path, output_dir: Path, stem: str, tracking: dict,
                            plates: dict, max_frames: int=8) -> dict:
    """Build annotated JPEG previews and truthful sampled-frame video montage.

    The exported MP4 is a slideshow of sampled frames, NOT a frame-by-frame
    overlay of the continuous original video. The UI must explain this.
    """
    entries=tracking.get("detections") or []
    motion=provisional_pixel_motion(tracking.get("tracks") or [])
    if not entries:
        return {"status":"unavailable","frames":0,"motion_metrics":motion,
                "note":"No detected objects to annotate; original video unchanged."}
    by_second=defaultdict(list)
    for item in entries:
        if isinstance(item.get("second"),(int,float)):
            by_second[round(float(item["second"]),2)].append(item)
    plate_by_second=defaultdict(list)
    for item in plates.get("regions",[]) or []:
        if isinstance(item.get("second"),(int,float)):
            plate_by_second[round(float(item["second"]),2)].append(item)
    times=sorted(by_second)[:max_frames]
    if not times:
        return {"status":"unavailable","frames":0,"motion_metrics":motion,
                "note":"Detector did not return valid sample times."}
    output_dir.mkdir(parents=True,exist_ok=True)
    preview=output_dir/(stem+".annotated.jpg")
    movie=output_dir/(stem+".samples.mp4")
    created=0
    note="Actual YOLO bounding boxes on sampled timestamps only. IDs and pixel motion are provisional; metric speed/distance unavailable without calibrated geometry."
    try:
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder)
            for i,second in enumerate(times):
                image_path=tmp/f"src-{i:03d}.jpg"
                extracted=subprocess.run(
                    ["ffmpeg","-hide_banner","-loglevel","error","-y",
                     "-ss",str(second),"-i",str(video),
                     "-frames:v","1","-q:v","3",str(image_path)],
                    capture_output=True,timeout=35)
                if extracted.returncode!=0 or not image_path.is_file():
                    continue
                with Image.open(image_path) as source:
                    annotated=annotate_frame(source,second,by_second[second],
                                             plate_by_second.get(second,[]))
                # Encode even dimensions for widely supported H.264.
                w,h=annotated.size
                if w%2 or h%2:
                    annotated=annotated.resize((w-w%2,h-h%2))
                annotated.save(tmp/f"frame-{created:03d}.jpg",quality=85)
                if created==0:
                    annotated.save(preview,quality=90)
                created+=1
            if not created:
                raise RuntimeError("No sampled source frames decoded for annotations")
            command=["ffmpeg","-hide_banner","-loglevel","error","-y",
                     "-framerate","1","-i",str(tmp/"frame-%03d.jpg"),
                     "-c:v","libx264","-preset","veryfast","-crf","26",
                     "-pix_fmt","yuv420p","-movflags","+faststart",str(movie)]
            result=subprocess.run(command,capture_output=True,timeout=100)
            if result.returncode!=0 or not movie.exists() or movie.stat().st_size==0:
                raise RuntimeError("FFmpeg could not render sampled annotation montage")
        return {"status":"completed","frames":created,
                "motion_metrics":motion,"note":note}
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
        return {"status":"failed","frames":created,
                "motion_metrics":motion,
                "note":f"Annotation preview unavailable: {type(exc).__name__}. "
                       "Original source footage and detections are preserved."}


def motion_csv(rows: list[dict]) -> bytes:
    keys=["track_id","vehicle","observations","start_s","end_s",
          "image_path_px","image_motion_px_s","confidence"]
    result=io.StringIO()
    writer=csv.DictWriter(result,fieldnames=keys,extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return result.getvalue().encode("utf-8-sig")
