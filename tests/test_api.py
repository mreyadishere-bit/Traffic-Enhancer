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
    assert data["duration"] >= 1
    assert len(data["sha256"]) == 64
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
