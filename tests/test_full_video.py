"""Regression: 5-second collage must NOT replace a 27-second selected clip."""
import shutil
import subprocess
import pytest
from pathlib import Path
from PIL import Image
from services.api.full_video import make_annotated_full_clip, review_fps, probe_duration


def create_real_clip(path,seconds):
    subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i",
        "testsrc=size=320x180:rate=12",
        "-t",str(seconds),"-pix_fmt","yuv420p",str(path)],
        check=True,timeout=35)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg and ffprobe required")
@pytest.mark.parametrize("selected_seconds",[3.0,7.0,26.7])
def test_full_video_matches_requested_duration_and_uses_real_detected_frames(
        tmp_path,selected_seconds):
    source=tmp_path/"selected.mp4"
    create_real_clip(source,selected_seconds)
    seen=[]
    def detector(kind,frame):
        assert kind=="vehicle"
        seen.append(frame.size)
        return [{"label":"car","confidence":.83,"class_id":2,
                 "box_xyxy":[30,40,110,130]}]
    reported=[]
    result=make_annotated_full_clip(source,tmp_path,"case",selected_seconds,
                                     detector=detector,progress=reported.append)
    assert result["status"]=="completed",result
    movie=tmp_path/"case.tracked.mp4"
    assert movie.is_file() and movie.stat().st_size>1024
    assert abs(probe_duration(movie)-selected_seconds)<.13
    assert len(seen)>5 if selected_seconds>3 else len(seen)>0
    assert result["analyzed_frames"]==len(seen)
    assert result["total_vehicle_detections"]==len(seen)
    assert result["inference_fps"]==review_fps(selected_seconds)
    assert any("annotating_video:" in x for x in reported)
    assert source.is_file()  # original evidence never modified


def test_frame_sampling_is_bounded_and_scales_for_long_clips():
    assert review_fps(20)==3
    assert review_fps(70)==2
    assert review_fps(150)==1


def test_refuses_to_invent_video_without_source(tmp_path):
    outcome=make_annotated_full_clip(tmp_path/"not_exists.mp4",tmp_path,"case",7)
    assert outcome["status"]=="failed"
    assert not (tmp_path/"case.tracked.mp4").exists()
