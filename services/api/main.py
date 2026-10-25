"""Traffic Enhancer MVP — authenticated evidence intake and report API.

Operator-key auth and SQLite are for the initial local vertical slice only.
Never deploy with the development key or expose this service publicly as-is.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .analysis import inspect_video
from .report import build_report

BASE = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("TE_DATA_DIR", str(BASE / "data"))).resolve()
EVIDENCE = DATA / "evidence"
DERIVED = DATA / "derived"
DB = DATA / "traffic.db"
MAX_BYTES = int(os.environ.get("TE_MAX_UPLOAD_MB", "150")) * 1024 * 1024
KEY = os.environ.get("TE_API_KEY", "dev-only-change-me")
if os.environ.get("TE_ENV", "development") == "production" and KEY == "dev-only-change-me":
    raise RuntimeError("Set a unique TE_API_KEY before using TE_ENV=production")


def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL,
            created_at TEXT NOT NULL, sha256 TEXT NOT NULL,
            bytes INTEGER NOT NULL, duration REAL NOT NULL,
            video_json TEXT NOT NULL, status TEXT NOT NULL,
            analysis_json TEXT, error TEXT
        )""")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield


app = FastAPI(title="Traffic Enhancer API", version="0.1.0", lifespan=lifespan)


def authorize(authorization: str | None = Header(default=None)):
    import hmac
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    if not hmac.compare_digest(authorization[7:].encode(), KEY.encode()):
        raise HTTPException(401, "Invalid operator key")


def read_incident(incident_id):
    with connect() as db:
        row = db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Incident not found")
    return dict(row)


def public_incident(row):
    return {
        "id": row["id"], "filename": row["filename"],
        "created_at": row["created_at"], "sha256": row["sha256"],
        "bytes": row["bytes"], "duration": row["duration"],
        "video": json.loads(row["video_json"]), "status": row["status"],
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
        "error": row["error"],
    }


def probe(path):
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=25, check=True,
        )
        info = json.loads(completed.stdout)
        streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
        if not streams:
            raise ValueError("File contains no video stream")
        duration = float(info.get("format", {}).get("duration") or streams[0].get("duration") or 0)
        if not 1 <= duration <= 180:
            raise ValueError("Video must be between 1 and 180 seconds")
        return {"duration_seconds": round(duration, 3),
                "width": streams[0].get("width"), "height": streams[0].get("height"),
                "codec": streams[0].get("codec_name"),
                "has_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", []))}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid or unsupported video: {exc}") from exc


def analyze_record(incident_id):
    with connect() as db:
        db.execute("UPDATE incidents SET status='processing', error=NULL WHERE id=?", (incident_id,))
    try:
        row = read_incident(incident_id)
        result = inspect_video(EVIDENCE / (incident_id + ".video"),
                               DERIVED / (incident_id + ".jpg"),
                               json.loads(row["video_json"]))
        with connect() as db:
            db.execute("UPDATE incidents SET status='ready', analysis_json=? WHERE id=?",
                       (json.dumps(result, ensure_ascii=False), incident_id))
    except Exception as exc:
        with connect() as db:
            db.execute("UPDATE incidents SET status='failed', error=? WHERE id=?",
                       (str(exc)[:500], incident_id))


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "traffic-enhancer-api"}


@app.post("/api/v1/incidents", status_code=202, dependencies=[Depends(authorize)])
async def upload_incident(background: BackgroundTasks, video: UploadFile = File(...)):
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise HTTPException(503, "FFmpeg and ffprobe must be installed")
    filename = Path(video.filename or "recording.mp4").name[:160]
    if Path(filename).suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise HTTPException(415, "Supported file extensions: .mp4, .mov, .mkv")
    incident_id = uuid.uuid4().hex
    path = EVIDENCE / (incident_id + ".video")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "Video exceeds configured size limit")
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "Empty video")
        metadata = probe(path)
        with connect() as db:
            db.execute("""INSERT INTO incidents
            (id, filename, created_at, sha256, bytes, duration, video_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (incident_id, filename, datetime.now(timezone.utc).isoformat(),
                        digest.hexdigest(), size, metadata["duration_seconds"],
                        json.dumps(metadata), "queued"))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await video.close()
    background.add_task(analyze_record, incident_id)
    return {"id": incident_id, "status": "queued", "sha256": digest.hexdigest()}


@app.get("/api/v1/incidents", dependencies=[Depends(authorize)])
def list_incidents():
    with connect() as db:
        rows = db.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"items": [public_incident(dict(row)) for row in rows]}


@app.get("/api/v1/incidents/{incident_id}", dependencies=[Depends(authorize)])
def get_incident(incident_id: str):
    return public_incident(read_incident(incident_id))


@app.get("/api/v1/incidents/{incident_id}/video", dependencies=[Depends(authorize)])
def get_video(incident_id: str):
    row = read_incident(incident_id)
    return FileResponse(EVIDENCE / (row["id"] + ".video"), media_type="video/mp4",
                        filename=row["filename"])


@app.get("/api/v1/incidents/{incident_id}/thumbnail", dependencies=[Depends(authorize)])
def get_thumbnail(incident_id: str):
    read_incident(incident_id)
    image = DERIVED / (incident_id + ".jpg")
    if not image.is_file():
        raise HTTPException(404, "Thumbnail not yet available")
    return FileResponse(image, media_type="image/jpeg")


@app.post("/api/v1/incidents/{incident_id}/reanalyze", status_code=202,
          dependencies=[Depends(authorize)])
def reanalyze(incident_id: str, background: BackgroundTasks):
    row = read_incident(incident_id)
    if row["status"] in {"queued", "processing"}:
        raise HTTPException(409, "Analysis already pending")
    with connect() as db:
        db.execute("UPDATE incidents SET status='queued', analysis_json=NULL, error=NULL WHERE id=?",
                   (incident_id,))
    background.add_task(analyze_record, incident_id)
    return {"id": incident_id, "status": "queued"}


@app.get("/api/v1/incidents/{incident_id}/report", dependencies=[Depends(authorize)])
def get_report(incident_id: str):
    row = read_incident(incident_id)
    if row["status"] != "ready":
        raise HTTPException(409, "Report not ready")
    return {"disclaimer": "AI-assisted preliminary assessment; not a verified traffic offense.",
            "incident": public_incident(row)}


@app.get("/api/v1/incidents/{incident_id}/report.pdf", dependencies=[Depends(authorize)])
def get_report_pdf(incident_id: str):
    row = read_incident(incident_id)
    if row["status"] != "ready":
        raise HTTPException(409, "Report not ready")
    return Response(content=build_report(public_incident(row)),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="traffic-report-{incident_id}.pdf"'})


app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")
