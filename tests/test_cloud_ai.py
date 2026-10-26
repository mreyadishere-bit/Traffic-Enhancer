"""Remote AI contract tests. Fake HTTP responses are NOT evidence of model accuracy."""
import os
import shutil
import subprocess
import pytest

from services.api.qwen import describe_video
from services.api.analysis import transcribe_audio


class FakeResponse:
    def __init__(self, result):
        self.result = result
    def raise_for_status(self):
        pass
    def json(self):
        return self.result


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg needed to create real media fixture")
def test_qwen_cloud_sends_actual_sampled_frames_and_rejects_unreliable_events(
        tmp_path, monkeypatch):
    import httpx
    video=tmp_path/"road.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","color=c=blue:s=160x96:r=4",
                    "-t","3","-c:v","mpeg4",str(video)],check=True)
    sent={}
    def fake_post(url,headers,json,timeout):
        sent.update({"url":url,"headers":headers,"payload":json})
        return FakeResponse({"choices":[{"message":{"content":
            '{"scene_summary":"Only a blue image; no interpretable road evidence",'
            '"potential_events":[{"category":"invented","visual_evidence":"N/A"}]}'}}]})
    monkeypatch.setattr(httpx,"post",fake_post)
    monkeypatch.setenv("TE_ENABLE_QWEN","1")
    monkeypatch.setenv("TE_QWEN_API_BASE","https://openrouter.ai/api/v1")
    monkeypatch.setenv("TE_QWEN_API_KEY","fake-ci-key")
    monkeypatch.setenv("TE_QWEN_MODEL","qwen/qwen-2.5-vl-7b-instruct:free")
    result=describe_video(video,3,{"verbatim":"Driver reported a red light"})
    assert result["status"]=="completed",result
    assert result["observations"]["potential_events"]==[]
    assert sent["url"]=="https://openrouter.ai/api/v1/chat/completions"
    assert sent["payload"]["model"].endswith(":free")
    contents=sent["payload"]["messages"][0]["content"]
    images=[c for c in contents if c.get("type")=="image_url"]
    assert len(images)>=2
    assert all(c["image_url"]["url"].startswith("data:image/jpeg;base64,") for c in images)
    assert "fake-ci-key" not in str(result)


@pytest.mark.skipif(not shutil.which("ffmpeg"),reason="FFmpeg needed for audio fixture")
def test_groq_remote_audio_sends_real_audio_and_parses_timestamps(tmp_path,monkeypatch):
    import httpx
    video=tmp_path/"audio.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","color=c=black:s=128x72:r=4",
                    "-f","lavfi","-i","sine=frequency=440:sample_rate=16000",
                    "-t","2","-c:v","mpeg4","-c:a","aac",str(video)],check=True)
    sent={}
    def fake_post(url,headers,files,data,timeout):
        sent["url"]=url
        sent["audio"]=files["file"][1].read()
        sent["model"]=data["model"]
        return FakeResponse({"text":"take photo","language":"en",
                             "segments":[{"start":0.2,"end":1.1,"text":"take photo"}]})
    monkeypatch.setattr(httpx,"post",fake_post)
    monkeypatch.setenv("TE_GROQ_ASR_MODEL","whisper-large-v3-turbo")
    monkeypatch.setenv("TE_GROQ_API_KEY","fake-ci-groq")
    result=transcribe_audio(video,{"has_audio":True})
    assert result["status"]=="completed",result
    assert result["provider"]=="groq_operator_opt_in"
    assert result["text"]=="take photo"
    assert result["segments"][0]["start"]==0.2
    assert sent["url"].endswith("/audio/transcriptions")
    assert sent["audio"].startswith(b"fLaC")
