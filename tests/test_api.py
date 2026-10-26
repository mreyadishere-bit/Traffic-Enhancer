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



def test_local_browser_requires_direct_loopback_only(monkeypatch):
    from starlette.requests import Request

    def req(ip="127.0.0.1", host="127.0.0.1:8000", **headers):
        pairs=[(b"host",host.encode())]
        pairs += [(name.replace("_","-").encode(),str(value).encode())
                  for name,value in headers.items()]
        scope={"type":"http","http_version":"1.1","method":"GET","scheme":"http",
               "path":"/api/v1/incidents","headers":pairs,
               "client":(ip,40000),"server":("127.0.0.1",8000)}
        return Request(scope)

    monkeypatch.setenv("TE_ENV","development")
    monkeypatch.setenv("TE_LOCAL_NO_AUTH","1")
    allowed=req()
    assert main.local_browser_mode(allowed) is True
    assert main.authorize(allowed) is None
    assert main.session(allowed)=={"login_required":False}
    assert main.local_browser_mode(req(host="localhost:8000"))
    assert not main.local_browser_mode(req(ip="192.168.1.5"))
    assert not main.local_browser_mode(req(host="app.github.dev"))
    assert not main.local_browser_mode(req(x_forwarded_for="8.8.8.8"))
    assert not main.local_browser_mode(req(origin="https://malicious.example"))
    assert not main.local_browser_mode(req(sec_fetch_site="cross-site"))
    monkeypatch.setenv("TE_ENV","production")
    assert not main.local_browser_mode(req())
    monkeypatch.setenv("TE_ENV","development")
    monkeypatch.setenv("TE_LOCAL_NO_AUTH","0")
    assert not main.local_browser_mode(req())



def test_real_fastapi_local_session_without_password(tmp_path, monkeypatch):
    """A browser connecting directly to loopback gets the app, not the login page."""
    monkeypatch.setenv("TE_ENV", "development")
    monkeypatch.setenv("TE_LOCAL_NO_AUTH", "1")
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(main, "DB", tmp_path / "traffic.db")
    monkeypatch.setattr(main, "EVIDENCE", tmp_path / "evidence")
    monkeypatch.setattr(main, "DERIVED", tmp_path / "derived")
    with TestClient(main.app, base_url="http://127.0.0.1:8000",
                    client=("127.0.0.1", 50001)) as browser:
        assert browser.get("/api/v1/session").json() == {"login_required": False}
        assert browser.get("/api/v1/incidents").status_code == 200
        assert browser.get("/api/v1/capabilities").status_code == 200
        # Cross-site requests cannot use the local no-password exception.
        assert browser.get("/api/v1/incidents",
                           headers={"Origin": "https://unsafe.example"}).status_code == 401
        assert browser.get("/api/v1/incidents",
                           headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 401
    with TestClient(main.app, base_url="https://my-codespace-8000.app.github.dev",
                    client=("127.0.0.1", 50001)) as proxy:
        assert proxy.get("/api/v1/session").json() == {"login_required": True}
        assert proxy.get("/api/v1/incidents").status_code == 401
