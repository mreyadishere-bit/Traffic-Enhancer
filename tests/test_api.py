import io
import os
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

os.environ["TE_API_KEY"] = "test-operator-secret"

from services.api import main  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(main, "DB", tmp_path / "traffic.db")
    monkeypatch.setattr(main, "EVIDENCE", tmp_path / "evidence")
    monkeypatch.setattr(main, "DERIVED", tmp_path / "derived")
    with TestClient(main.app) as browser:
        yield browser


def headers():
    return {"Authorization": "Bearer test-operator-secret"}


def test_health_and_auth(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/incidents").status_code == 401
    assert client.get("/api/v1/incidents", headers=headers()).status_code == 200
    caps = client.get("/api/v1/capabilities", headers=headers())
    assert caps.status_code == 200
    assert caps.json()["traffic_violation_verification"]["available"] is False
    assert client.get("/api/v1/capabilities").status_code == 401
    assert client.get("/api/v1/incidents/nope", headers=headers()).status_code == 404


def test_invalid_upload_rejected_without_record(client):
    response = client.post("/api/v1/incidents", headers=headers(),
                           files={"video": ("invalid.mp4", io.BytesIO(b"not a video"), "video/mp4")})
    if shutil.which("ffprobe") and shutil.which("ffmpeg"):
        assert response.status_code == 422
        assert client.get("/api/v1/incidents", headers=headers()).json()["items"] == []
    else:
        assert response.status_code == 503


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg required for real end-to-end integration test")
def test_real_video_pipeline_and_pdf(client, tmp_path):
    video = tmp_path / "road.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=5",
        "-t", "2", "-c:v", "mpeg4", str(video)
    ], check=True)
    response = client.post("/api/v1/incidents", headers=headers(),
                           files={"video": ("road.mp4", video.read_bytes(), "video/mp4")})
    assert response.status_code == 202, response.text
    incident_id = response.json()["id"]
    read = client.get(f"/api/v1/incidents/{incident_id}", headers=headers())
    assert read.status_code == 200
    data = read.json()
    assert data["status"] == "ready", data
    assert data["stage"] == "complete"
    assert data["duration"] >= 1
    assert len(data["sha256"]) == 64
    assert main.evidence_path(main.read_incident(incident_id)).suffix == ".mp4"
    assert data["analysis"]["evidence"]["keyframe_extracted"] is True
    assert data["analysis"]["vehicle_detection"]["status"] in {"not_configured", "completed"}
    assert data["analysis"]["violation_assessment"]["conclusion"] is None
    assert client.get(f"/api/v1/incidents/{incident_id}/video", headers=headers()).status_code == 200
    assert client.get(f"/api/v1/incidents/{incident_id}/thumbnail", headers=headers()).status_code == 200
    assert client.get(f"/api/v1/incidents/{incident_id}/report", headers=headers()).status_code == 200
    pdf = client.get(f"/api/v1/incidents/{incident_id}/report.pdf", headers=headers())
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1500  # includes original extracted frame as an image
    assert client.get(f"/api/v1/incidents/{incident_id}/report.pdf").status_code == 401


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg required for real trim integration")
def test_long_source_can_be_trimmed_without_losing_original(client, tmp_path):
    import hashlib
    source = tmp_path / "long-recording.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=green:s=160x120:r=3",
        "-t", "205", "-c:v", "mpeg4", str(source)
    ], check=True)
    original_bytes = source.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    too_long = client.post("/api/v1/incidents", headers=headers(),
        files={"video": ("long-recording.mp4", original_bytes, "video/mp4")})
    assert too_long.status_code == 422
    assert not list(main.EVIDENCE.iterdir()), "Rejected uploads must be cleaned up"

    response = client.post("/api/v1/incidents", headers=headers(),
        data={"start_seconds": "80", "end_seconds": "100"},
        files={"video": ("long-recording.mp4", original_bytes, "video/mp4")})
    assert response.status_code == 202, response.text
    incident_id = response.json()["id"]
    record = client.get(f"/api/v1/incidents/{incident_id}", headers=headers()).json()
    assert record["status"] == "ready", record
    assert 18 <= record["duration"] <= 21
    assert record["sha256"] == original_hash
    assert record["video"]["selection"]["was_trimmed"] is True
    assert record["video"]["selection"]["start_seconds"] == 80
    assert record["video"]["selection"]["end_seconds"] == 100
    assert record["video"]["selection"]["clip_sha256"] != original_hash
    original = client.get(f"/api/v1/incidents/{incident_id}/source", headers=headers())
    assert original.status_code == 200
    assert original.content == original_bytes
    clip = client.get(f"/api/v1/incidents/{incident_id}/video", headers=headers())
    assert clip.status_code == 200
    assert clip.content != original_bytes
    assert client.get(f"/api/v1/incidents/{incident_id}/report.pdf", headers=headers()).status_code == 200
    assert client.get(f"/api/v1/incidents/{incident_id}/source").status_code == 401


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg required for trim bounds test")
def test_invalid_trim_bounds_do_not_save_evidence(client, tmp_path):
    file = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
       "-f","lavfi","-i","color=c=red:s=160x120:r=3",
       "-t","4","-c:v","mpeg4",str(file)],check=True)
    response = client.post("/api/v1/incidents", headers=headers(),
       data={"start_seconds":"1","end_seconds":"100"},
       files={"video":("clip.mp4",file.read_bytes(),"video/mp4")})
    assert response.status_code == 422
    assert not list(main.EVIDENCE.iterdir())



@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg needed for real reviewer integration test")
def test_manual_claim_review_and_reanalysis(client, tmp_path):
    """No real audio: typed claim remains correctly attributed and editable."""
    clip=tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","color=c=green:s=128x96:r=4",
                    "-t","2","-c:v","mpeg4",str(clip)],check=True)
    response=client.post("/api/v1/incidents",headers=headers(),
       data={"driver_description":"Take photo, blue Kia on the shoulder"},
       files={"video":("silent.mp4",clip.read_bytes(),"video/mp4")})
    assert response.status_code==202,response.text
    case_id=response.json()["id"]
    detail=client.get(f"/api/v1/incidents/{case_id}",headers=headers()).json()
    assert detail["status"]=="ready",detail
    assert detail["review"]["manual_description"].startswith("Take photo")
    assert detail["analysis"]["driver_claim"]["source"]=="user_supplied_description"
    assert detail["analysis"]["driver_claim"]["verified_from_video"] is False
    source_hash=detail["sha256"]
    invalid=client.put(f"/api/v1/incidents/{case_id}/review",headers=headers(),
       json={"selected_track_id":999, "manual_description":"A blue car"})
    assert invalid.status_code==422
    invalid_time=client.put(f"/api/v1/incidents/{case_id}/review",headers=headers(),
       json={"reviewed_event_second":999,"manual_description":"A blue car"})
    assert invalid_time.status_code==422
    updated=client.put(f"/api/v1/incidents/{case_id}/review",headers=headers(),
       json={"status":"needs_review","manual_description":"العربية كيا الزرقاء على كتف الطريق",
             "review_note":"Unclear shoulder boundary","reviewed_event_second":1.2})
    assert updated.status_code==200,updated.text
    assert updated.json()["reanalyze_recommended"] is True
    assert client.put(f"/api/v1/incidents/{case_id}/review",
        json={"manual_description":"unauthorized"}).status_code==401
    after=client.get(f"/api/v1/incidents/{case_id}",headers=headers()).json()
    assert after["review"]["review_note"]=="Unclear shoulder boundary"
    assert after["sha256"]==source_hash
    rerun=client.post(f"/api/v1/incidents/{case_id}/reanalyze",headers=headers())
    assert rerun.status_code==202
    revised=client.get(f"/api/v1/incidents/{case_id}",headers=headers()).json()
    assert revised["status"]=="ready"
    assert revised["analysis"]["driver_claim"]["source"]=="user_supplied_description"
    assert revised["analysis"]["driver_claim"]["make"]=="kia"
    assert revised["sha256"]==source_hash
    pdf=client.get(f"/api/v1/incidents/{case_id}/report.pdf",headers=headers())
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF")
    assert len(pdf.content)>2500


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg needed for actual MOV transcode test")
def test_trimmed_mov_playback_serves_actual_mp4(client,tmp_path):
    clip=tmp_path/"input.mov"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","color=c=red:s=128x96:r=4",
                    "-t","5","-c:v","mpeg4",str(clip)],check=True)
    response=client.post("/api/v1/incidents",headers=headers(),
       data={"start_seconds":1,"end_seconds":3},
       files={"video":("input.mov",clip.read_bytes(),"video/quicktime")})
    assert response.status_code==202,response.text
    id=response.json()["id"]
    read=client.get(f"/api/v1/incidents/{id}",headers=headers()).json()
    assert read["status"]=="ready",read
    assert main.evidence_path(main.read_incident(id)).suffix==".mp4"
    media=client.get(f"/api/v1/incidents/{id}/video",headers=headers())
    assert media.status_code==200
    assert media.headers["content-type"].startswith("video/mp4")
    assert client.get(f"/api/v1/incidents/{id}/source",headers=headers()).content==clip.read_bytes()
