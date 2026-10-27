"""Evidence artifacts come from sampled source times, never fabricated."""
import subprocess
from pathlib import Path
import pytest
from PIL import Image
from services.api.visual_evidence import annotate_frame, provisional_pixel_motion, render_sampled_evidence, motion_csv

def test_pixel_motion_from_timestamped_bounding_boxes_without_fake_speed():
    tracks=[{"track_id":7,"label":"car","observations":[
        {"second":2.0,"box_xyxy":[0,0,20,20]},
        {"second":4.0,"box_xyxy":[30,40,50,60]}]},
        {"track_id":8,"label":"car","observations":[
        {"second":2.0,"box_xyxy":[0,0,20,20]}]}]
    result=provisional_pixel_motion(tracks)
    assert len(result)==1
    assert result[0]["image_path_px"]==50
    assert result[0]["image_motion_px_s"]==25
    assert result[0]["distance_m"] is None and result[0]["speed_kmh"] is None
    assert b"25" in motion_csv(result)

def test_actual_sample_contains_real_boxes():
    original=Image.new("RGB",(320,180),(30,30,30))
    altered=annotate_frame(original,1.6,[{
        "label":"car","track_id":17,"confidence":.9,
        "box_xyxy":[80,70,160,130]}],
        [{"bbox":[99,110,140,125],"confidence":.51}])
    assert altered.getpixel((80,70)) != original.getpixel((80,70))
    assert altered.getpixel((99,110)) != original.getpixel((99,110))
    assert altered.size==original.size

def test_unmatched_tracks_do_not_invent_motion():
    assert provisional_pixel_motion([])==[]
    assert provisional_pixel_motion([{"observations":[{"second":1,
        "box_xyxy":[0,0,10,10]}]}])==[]

def test_annotated_video_uses_real_decoded_source_frames(tmp_path):
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    source=tmp_path/"source.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi",
                    "-i","color=c=black:s=320x180:r=6",
                    "-t","3","-pix_fmt","yuv420p",str(source)],check=True,timeout=30)
    tracking={"detections":[{"second":1.0,"box_xyxy":[30,30,110,130],
                "label":"car","track_id":1,"confidence":.87}],
              "tracks":[{"track_id":1,"label":"car","observations":[
                {"second":1.0,"box_xyxy":[30,30,110,130]}]}]}
    result=render_sampled_evidence(source,tmp_path,"case",tracking,
                  {"regions":[{"second":1.0,"bbox":[40,100,65,115]}]})
    assert result["status"]=="completed",result
    assert result["frames"]==1
    assert (tmp_path/"case.annotated.jpg").stat().st_size>1000
    assert (tmp_path/"case.samples.mp4").stat().st_size>1000
    assert source.is_file()

def test_no_fake_annotations_for_missing_detections(tmp_path):
    result=render_sampled_evidence(Path("missing.mp4"),tmp_path,"case",
                {"detections":[],"tracks":[]},{})
    assert result["status"]=="unavailable"
    assert not (tmp_path/"case.samples.mp4").exists()
