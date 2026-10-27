"""Optional remote vision must not delay CPU annotated evidence and plates."""
from services.api import analysis


def test_full_video_is_generated_before_remote_qwen(monkeypatch,tmp_path):
    source=tmp_path/"selected.mp4"
    source.write_bytes(b"synthetic fixture")
    preview=tmp_path/"evidence"/"123.jpg"
    preview.parent.mkdir()
    stages=[]
    def fake_ffmpeg(command,**kwargs):
        preview.write_bytes(b"fake-jpg")
    def fake_track(video,metadata):
        return {"status":"completed","detections":[],"tracks":[],"model":"mock"}
    def fake_plates(video,duration):
        stages.append("plate_detection")
        return {"status":"completed","plates_detected":0,"candidates":[]}
    def fake_sample(*args,**kwargs):
        stages.append("sample_evidence")
        return {"status":"completed"}
    def fake_video(*args,**kwargs):
        stages.append("full_mp4")
        (preview.parent/"123.tracked.mp4").write_bytes(b"ready")
        return {"status":"completed","duration_seconds":12}
    def fake_qwen(*args,**kwargs):
        stages.append("remote_qwen")
        assert (preview.parent/"123.tracked.mp4").is_file()
        return {"status":"failed","note":"OpenRouter 404","observations":None}

    monkeypatch.setattr(analysis.subprocess,"run",fake_ffmpeg)
    monkeypatch.setattr(analysis,"transcribe_audio",lambda *a: {"status":"not_configured"})
    monkeypatch.setattr(analysis,"track_vehicles",fake_track)
    monkeypatch.setattr(analysis,"scan_plates",fake_plates)
    monkeypatch.setattr(analysis,"render_sampled_evidence",fake_sample)
    monkeypatch.setattr(analysis,"make_annotated_full_clip",fake_video)
    monkeypatch.setattr(analysis,"describe_video",fake_qwen)
    monkeypatch.setenv("TE_CLOUD_VISION","1")
    result=analysis.inspect_video(
        source,preview,{"duration_seconds":12,"has_audio":False},on_stage=stages.append)
    assert stages.index("plate_detection") < stages.index("remote_qwen")
    assert stages.index("full_mp4") < stages.index("remote_qwen")
    assert stages.index("qwen_visual_reasoning") > stages.index("full_mp4")
    assert result["full_length_video"]["status"]=="completed"
    assert result["visual_reasoning"]["status"]=="failed"
    assert result["vehicle_detection"]["status"]=="completed"
