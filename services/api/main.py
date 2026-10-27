"""Traffic Enhancer MVP — authenticated evidence intake and report API.

Operator-key auth and SQLite are for the initial local vertical slice only.
Never deploy with the development key or expose this service publicly as-is.
"""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import uuid
from fractions import Fraction
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
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
MAX_SOURCE_BYTES = int(os.environ.get("TE_MAX_SOURCE_MB", "512")) * 1024 * 1024
MAX_SOURCE_SECONDS = int(os.environ.get("TE_MAX_SOURCE_SECONDS", "7200"))
# Remote deployments always require an explicitly configured operator key.
# A local-only development session does not require anyone to type a key.
KEY = os.environ.get("TE_API_KEY", "").strip()
if os.environ.get("TE_ENV", "development") == "production" and not KEY:
    raise RuntimeError("Set a unique TE_API_KEY before using TE_ENV=production")
if not KEY:
    KEY = secrets.token_urlsafe(32)  # Never use a known hardcoded remote key.




def ensure_media_tools():
    """Use installed FFmpeg first; fetch both binaries into Python cache if missing.

    The optional first-use fetch requires internet. It does not modify Windows
    global PATH, and respects manually installed ffmpeg/ffprobe.
    """
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths(weak=True)
    except Exception as exc:
        raise HTTPException(503,
            "FFmpeg setup failed. Ensure internet access for first-use download, "
            f"or install FFmpeg and FFprobe: {type(exc).__name__}: {str(exc)[:160]}") from exc
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(503, "FFmpeg and FFprobe unavailable; retry setup.")

def sha256_file(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

def source_evidence_path(row):
    suffix = Path(row["filename"]).suffix.lower()
    source = EVIDENCE / (row["id"] + ".source" + suffix)
    return source if source.exists() else evidence_path(row)

def trim_evidence(source, output, start, end):
    """Accurate re-encode, not keyframe-only clipping; preserve source separately."""
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start), "-i", str(source),
            "-t", str(round(end-start, 3)),
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-movflags", "+faststart", str(output),
        ], capture_output=True, check=True, timeout=360)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise HTTPException(422, f"Unable to trim video: {type(exc).__name__}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise HTTPException(422, "Trimmed recording was empty")
    if output.stat().st_size > MAX_BYTES:
        raise HTTPException(413, "Selected clip still exceeds 150 MB; choose a shorter segment")

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
            analysis_json TEXT, error TEXT, stage TEXT DEFAULT 'queued'
        )""")

    # Migration for repositories that already ran the earlier SQLite MVP.
    with connect() as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(incidents)").fetchall()}
        if "stage" not in columns:
            db.execute("ALTER TABLE incidents ADD COLUMN stage TEXT DEFAULT 'unknown'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield


app = FastAPI(title="Traffic Enhancer API", version="0.1.0", lifespan=lifespan)


def local_browser_mode(request: Request) -> bool:
    """Allow keyless access ONLY from a direct loopback browser in development.

    Never trust forwarded traffic, DNS-rebound hostnames, or cross-site requests.
    Codespaces, VPNs, proxy URLs and production must retain operator-key auth.
    """
    if os.environ.get("TE_ENV", "development") != "development":
        return False
    if os.environ.get("TE_LOCAL_NO_AUTH", "1") != "1":
        return False
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        return False
    if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    if any(request.headers.get(name) for name in (
        "forwarded", "x-forwarded-for", "x-forwarded-host", "x-original-host"
    )):
        return False
    if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
        return False
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc != request.url.netloc:
            return False
    return True


def authorize(request: Request, authorization: str | None = Header(default=None)):
    if local_browser_mode(request):
        return
    import hmac
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    if not hmac.compare_digest(authorization[7:].encode(), KEY.encode()):
        raise HTTPException(401, "Invalid operator key")


@app.get("/api/v1/session")
def session(request: Request):
    # No secret or API key is ever returned to the browser.
    return {"login_required": not local_browser_mode(request)}



def evidence_path(row):
    """Give image/video libraries a supported filename suffix.

    Old MVP evidence retained as .video remains accessible for playback.
    New uploads are stored as actual .mp4/.mov/.mkv files so OpenCV/YOLO
    can decode the recorded footage.
    """
    safe_suffix = Path(row["filename"]).suffix.lower()
    if safe_suffix not in {".mp4", ".mov", ".mkv"}:
        safe_suffix = ".mp4"
    new_path = EVIDENCE / (row["id"] + safe_suffix)
    if new_path.exists():
        return new_path
    return EVIDENCE / (row["id"] + ".video")


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
        "error": row["error"], "stage": row.get("stage") or row["status"],
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
        if not 1 <= duration <= MAX_SOURCE_SECONDS:
            raise ValueError(f"Video must be between 1 and {MAX_SOURCE_SECONDS} seconds")
        rate = streams[0].get("avg_frame_rate") or streams[0].get("r_frame_rate") or "0/1"
        try:
            frame_rate = float(Fraction(rate))
            if not 0 < frame_rate < 300:
                frame_rate = None
        except (ValueError, ZeroDivisionError):
            frame_rate = None
        return {"duration_seconds": round(duration, 3), "frame_rate": frame_rate,
                "width": streams[0].get("width"), "height": streams[0].get("height"),
                "codec": streams[0].get("codec_name"),
                "has_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", []))}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid or unsupported video: {exc}") from exc


def analyze_record(incident_id):
    with connect() as db:
        db.execute("UPDATE incidents SET status='processing', stage='starting', error=NULL WHERE id=?", (incident_id,))
    try:
        row = read_incident(incident_id)
        def on_stage(stage):
            with connect() as db:
                db.execute("UPDATE incidents SET stage=? WHERE id=?", (stage, incident_id))
        result = inspect_video(evidence_path(row),
                               DERIVED / (incident_id + ".jpg"),
                               json.loads(row["video_json"]), on_stage=on_stage)
        with connect() as db:
            db.execute("UPDATE incidents SET status='ready', stage='complete', analysis_json=? WHERE id=?",
                       (json.dumps(result, ensure_ascii=False), incident_id))
    except Exception as exc:
        with connect() as db:
            db.execute("UPDATE incidents SET status='failed', stage='failed', error=? WHERE id=?",
                       (str(exc)[:500], incident_id))


@app.get("/api/v1/capabilities", dependencies=[Depends(authorize)])
def capabilities():
    """Configuration availability, NOT evidence of model accuracy or successful inference."""
    enabled = os.getenv("TE_ENABLE_QWEN", "0") == "1"
    remote = bool(os.getenv("TE_QWEN_API_BASE", "").strip())
    return {
        "qwen": {"configured": enabled,
                 "mode": "operator_configured_remote" if remote else "local",
                 "model": os.getenv("TE_QWEN_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct") if enabled else None,
                 "loaded_and_validated": False},
        "vehicle_tracking": {
            "configured": bool(os.getenv("TE_YOLO_MODEL", "").strip()) or
                          os.getenv("TE_CLOUD_VISION", "0") == "1",
            "backend": "onnx_cpu_sampled" if os.getenv("TE_CLOUD_VISION") == "1" else "ultralytics",
            "model_tested": False},
        "speech": {
            "configured": bool(os.getenv("TE_ASR_MODEL", "").strip()) or
                 (bool(os.getenv("TE_GROQ_ASR_MODEL", "").strip()) and
                  bool(os.getenv("TE_GROQ_API_KEY", "").strip())),
            "mode": "groq" if os.getenv("TE_GROQ_ASR_MODEL") else "local",
            "model_tested": False},
        "plate_ocr": {
            "configured": bool(os.getenv("TE_PLATE_MODEL", "").strip()) or
                          os.getenv("TE_CLOUD_VISION", "0") == "1",
            "backend": "egyptian_onnx_tesseract" if os.getenv("TE_CLOUD_VISION") == "1" else "ultralytics_easyocr",
            "model_tested": False},
        "traffic_violation_verification": {"available": False,
                                           "human_review_required": True},
        "dashcam_direct_sync": {"available": False, "requires_hardware_test": True}
    }


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "traffic-enhancer-api"}


@app.post("/api/v1/incidents", status_code=202, dependencies=[Depends(authorize)])
async def upload_incident(
    background: BackgroundTasks, video: UploadFile = File(...),
    start_seconds: float | None = Form(default=None),
    end_seconds: float | None = Form(default=None),
    defer_processing: bool = Form(default=False),
):
    ensure_media_tools()
    filename = Path(video.filename or "recording.mp4").name[:160]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv"}:
        raise HTTPException(415, "Supported extensions: .mp4, .mov, .mkv")
    if (start_seconds is None) != (end_seconds is None):
        raise HTTPException(422, "Provide both trim start and end, or neither")

    incident_id = uuid.uuid4().hex
    original = EVIDENCE / (incident_id + ".source" + suffix)
    output = EVIDENCE / (incident_id + ".mp4") if start_seconds is not None else EVIDENCE / (incident_id + suffix)
    source_digest = hashlib.sha256()
    size = 0
    try:
        with original.open("wb") as out:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise HTTPException(413, "Source exceeds server upload cap (512 MB by default)")
                source_digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "Empty video")
        full_metadata = probe(original)
        duration = full_metadata["duration_seconds"]
        trimmed = start_seconds is not None
        if trimmed:
            import math
            if not math.isfinite(start_seconds) or not math.isfinite(end_seconds):
                raise HTTPException(422, "Trim bounds must be finite numbers")
            if start_seconds < 0 or end_seconds <= start_seconds or end_seconds > duration + 0.15:
                raise HTTPException(422, "Trim bounds must be inside the source recording")
            if end_seconds - start_seconds < 1 or end_seconds - start_seconds > 180:
                raise HTTPException(422, "Selected segment must be 1–180 seconds")
            trim_evidence(original, output, start_seconds, min(duration, end_seconds))
            metadata = probe(output)
            if metadata["duration_seconds"] > 180.1:
                raise HTTPException(422, "Encoded clip exceeds 180 seconds")
            clip_digest = sha256_file(output)
            stored_bytes = output.stat().st_size
        else:
            if duration > 180:
                raise HTTPException(422,
                    "Recording exceeds 180 seconds: preview and select a segment to analyze")
            if size > MAX_BYTES:
                raise HTTPException(413, "Clip exceeds 150 MB. Choose a shorter segment")
            original.replace(output)
            metadata = full_metadata
            clip_digest = source_digest.hexdigest()
            stored_bytes = size

        metadata["selection"] = {
            "was_trimmed": trimmed,
            "source_duration_seconds": duration,
            "start_seconds": round(start_seconds, 3) if trimmed else 0,
            "end_seconds": round(min(duration, end_seconds), 3) if trimmed else duration,
            "source_sha256": source_digest.hexdigest(),
            "clip_sha256": clip_digest,
            "source_bytes": size, "clip_bytes": stored_bytes,
        }
        with connect() as db:
            db.execute("""INSERT INTO incidents
                (id, filename, created_at, sha256, bytes, duration, video_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (incident_id, filename, datetime.now(timezone.utc).isoformat(),
                 source_digest.hexdigest(), stored_bytes,
                 metadata["duration_seconds"], json.dumps(metadata), "queued"))
    except Exception:
        original.unlink(missing_ok=True)
        if output != original:
            output.unlink(missing_ok=True)
        raise
    finally:
        await video.close()
    if not defer_processing:
        background.add_task(analyze_record, incident_id)
    return {"id": incident_id, "status": "queued",
            "sha256": source_digest.hexdigest(),
            "clip_sha256": clip_digest, "trimmed": trimmed}


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
    media_type = {".mp4": "video/mp4", ".mov": "video/quicktime",
                  ".mkv": "video/x-matroska"}.get(Path(row["filename"]).suffix.lower(), "application/octet-stream")
    return FileResponse(evidence_path(row), media_type=media_type,
                        filename=row["filename"])


@app.get("/api/v1/incidents/{incident_id}/source", dependencies=[Depends(authorize)])
def get_original(incident_id: str):
    """The unaltered uploaded file is accessible to the authenticated operator."""
    row = read_incident(incident_id)
    return FileResponse(source_evidence_path(row), filename=row["filename"],
                        media_type="application/octet-stream")


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
        db.execute("UPDATE incidents SET status='queued', stage='queued', analysis_json=NULL, error=NULL WHERE id=?",
                   (incident_id,))
    background.add_task(analyze_record, incident_id)
    return {"id": incident_id, "status": "queued"}


@app.post("/api/v1/incidents/{incident_id}/retry-vision",
          dependencies=[Depends(authorize)])
def retry_vision_only(incident_id: str):
    """Re-run only remote image reasoning, retaining the original YOLO/ASR/MP4.

    This is deliberately separate from /reanalyze: it does not erase the
    incident, original evidence hashes, OCR, tracking or derived video assets.
    """
    from .qwen import describe_video
    from .assessment import assess_potential_events
    row=read_incident(incident_id)
    if row["status"]!="ready" or not row["analysis_json"]:
        raise HTTPException(409,"Run initial analysis before retrying visual reasoning")
    original=json.loads(row["analysis_json"])
    claim=original.get("driver_claim") or {}
    result=describe_video(evidence_path(row),float(row["duration"]),claim)
    original["visual_reasoning"]=result
    original["violation_assessment"]=assess_potential_events(claim,result)
    with connect() as db:
        update=db.execute(
            "UPDATE incidents SET analysis_json=? WHERE id=? AND status='ready' AND analysis_json=?",
            (json.dumps(original,ensure_ascii=False),incident_id,row["analysis_json"]))
        if update.rowcount != 1:
            raise HTTPException(409,"Case changed while vision retry was running")
    return {"id":incident_id,"status":"ready",
            "vision_status":result.get("status","failed"),
            "actual_model":result.get("model"),
            "note":result.get("note","")[:220]}


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
    return Response(content=build_report(public_incident(row), DERIVED / (incident_id + ".jpg")),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="traffic-report-{incident_id}.pdf"'})


app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")
