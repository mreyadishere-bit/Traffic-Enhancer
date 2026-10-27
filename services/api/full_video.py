"""Render a full-duration annotated review video from real YOLO inferences.

Unlike the historical five-image montage, the output covers the same timeline
as the clip actually selected by the user. Detectors inspect every *output
sample frame* at a bounded 1–3 Hz rate appropriate for a CPU-only free host.
The final browser-friendly MP4 is encoded at 10 fps by holding those
observations between samples. This is NOT original-fps continuous tracking,
nor a physical speed measurement. All boxes are clearly preliminary.
"""
from __future__ import annotations

import math
import os
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

from .visual_evidence import annotate_frame, provisional_pixel_motion
from .cloud_vision import _iou


def review_fps(seconds: float) -> int:
    if seconds <= 45:
        return 3
    if seconds <= 120:
        return 2
    return 1


def probe_duration(path: Path) -> float:
    import json
    result=subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","json",str(path)],capture_output=True,text=True,
        timeout=15,check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def make_annotated_full_clip(video: Path, output_dir: Path, case_id: str,
                             seconds: float, *, detector=None,
                             progress=None) -> dict:
    """Automatically annotate actual decoded frames and encode matching timeline.

    The output is an optional derived artifact. Failure is a recorded stage
    failure and NEVER changes or destroys the source recording.
    """
    from .cloud_vision import predict_frame

    detector=detector or predict_frame
    output_dir=Path(output_dir)
    result_file=output_dir/(case_id+".tracked.mp4")
    preview_file=output_dir/(case_id+".tracked.jpg")
    if not video.is_file():
        return {"status":"failed","note":"Original selected video unavailable."}
    seconds=float(seconds)
    if not math.isfinite(seconds) or seconds < 1 or seconds>180.1:
        return {"status":"failed","note":"Selected clip must be 1–180 seconds."}
    fps=review_fps(seconds)
    output_dir.mkdir(parents=True,exist_ok=True)
    result_file.unlink(missing_ok=True)
    processed=0
    observations=[]
    active=[]
    next_id=1
    counts=[]
    try:
        with tempfile.TemporaryDirectory(prefix="traffic-frames-") as root:
            folder=Path(root)
            original_frames=folder/"original"
            annotated_frames=folder/"tracked"
            original_frames.mkdir()
            annotated_frames.mkdir()
            command=[
                "ffmpeg","-hide_banner","-loglevel","error","-y",
                "-i",str(video),
                "-vf",f"fps={fps},scale='min(854,iw)':-2",
                "-q:v","5",str(original_frames/"frame-%05d.jpg")
            ]
            subprocess.run(command,check=True,capture_output=True,timeout=150)
            candidates=sorted(original_frames.glob("frame-*.jpg"))
            if not candidates:
                raise RuntimeError("FFmpeg extracted no actual source frames")
            if len(candidates)>550:
                raise RuntimeError("Video exceeded safe CPU inference frame cap")
            for i, source in enumerate(candidates):
                with Image.open(source) as raw:
                    frame=raw.convert("RGB")
                at=round(i/fps,3)
                raw_boxes=detector("vehicle",frame)
                labeled=[]
                next_active=[]
                claimed=set()
                for box in raw_boxes[:70]:
                    label=box.get("label")
                    bbox=box.get("box_xyxy")
                    if label not in ("car","truck","bus","motorcycle") or not bbox:
                        continue
                    best_id=None
                    best_score=.30
                    for prior in active:
                        if prior["track_id"] in claimed or prior["label"]!=label:
                            continue
                        similarity=_iou(prior["box_xyxy"],bbox)
                        if similarity>best_score:
                            best_score=similarity
                            best_id=prior["track_id"]
                    if best_id is None:
                        best_id=next_id
                        next_id+=1
                    claimed.add(best_id)
                    item={**box,"track_id":best_id,"second":at}
                    labeled.append(item)
                    next_active.append(item)
                    observations.append(item)
                active=next_active
                annotated=annotate_frame(frame,at,labeled)
                w,h=annotated.size
                if w%2 or h%2:
                    annotated=annotated.crop((0,0,w-w%2,h-h%2))
                annotated.save(annotated_frames/f"frame-{i+1:05d}.jpg",quality=84)
                if i==0:
                    annotated.save(preview_file,quality=90)
                counts.append({"second":at,"vehicles":len(labeled)})
                processed+=1
                if progress and (i%4==0 or i==len(candidates)-1):
                    progress(f"annotating_video:{processed}/{len(candidates)}")
            # Present at 10fps with held boxes / frames between actual 1–3 Hz
            # inference samples; tpad ensures short trailing fractions are not cut.
            # The audio stream, when available, comes from the selected video.
            # Source duration is authoritative for the -t cut.
            command=[
                "ffmpeg","-hide_banner","-loglevel","error","-y",
                "-framerate",str(fps),
                "-i",str(annotated_frames/"frame-%05d.jpg"),
                "-i",str(video),
                "-map","0:v:0","-map","1:a:0?",
                "-vf",f"fps=10,tpad=stop_mode=clone:stop_duration=2,"
                      f"trim=duration={seconds:.3f},setpts=PTS-STARTPTS",
                "-r","10","-c:v","libx264","-preset","veryfast",
                "-crf","27","-pix_fmt","yuv420p",
                "-c:a","aac","-b:a","96k",
                "-t",f"{seconds:.3f}","-movflags","+faststart",
                str(result_file)
            ]
            if progress:
                progress("encoding_full_video")
            subprocess.run(command,check=True,capture_output=True,timeout=180)
        if not result_file.is_file() or result_file.stat().st_size < 1024:
            raise RuntimeError("Full-length annotated MP4 was not created")
        actual=probe_duration(result_file)
        if abs(actual-seconds)>.13:
            raise RuntimeError(f"Output duration mismatch ({actual:.2f}s vs {seconds:.2f}s)")
        grouped={}
        for obj in observations:
            group=grouped.setdefault(obj["track_id"],{
                "track_id":obj["track_id"],"label":obj["label"],"observations":[]})
            group["observations"].append({
                "second":obj["second"],"box_xyxy":obj["box_xyxy"],
                "confidence":obj.get("confidence",0)})
        return {
            "status":"completed","duration_seconds":round(actual,3),
            "selected_clip_duration_seconds":round(seconds,3),
            "inference_fps":fps,"display_fps":10,
            "analyzed_frames":processed,
            "total_vehicle_detections":len(observations),
            "counts":counts,
            "motion_metrics":provisional_pixel_motion(list(grouped.values()))[:80],
            "note":"FULL selected clip timeline, analyzed at "+str(fps)+
                   " true YOLO frames/s on CPU; remaining frames repeat the most recent "
                   "sample, not re-detected. IDs are tentative; no real-world speed.",
        }
    except Exception as exc:
        result_file.unlink(missing_ok=True)
        return {"status":"failed","analyzed_frames":processed,
                "note":f"Full-length rendering failed: {type(exc).__name__}: {str(exc)[:130]}"}
