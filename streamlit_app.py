"""Traffic Enhancer — Streamlit Community Cloud entrypoint.

Native Streamlit UI over the repository's EXISTING FastAPI analysis engine.
Uses an in-process authenticated TestClient; this is an operator-only,
resource-limited, non-persistent demo, not a public enforcement service.
"""
from __future__ import annotations

import hashlib
import secrets
import re
import threading
import time
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Traffic Enhancer | Evidence Studio",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit root-level secrets are also injected into the environment on Cloud.
# Fall back to st.secrets for local Streamlit sessions, without requiring a
# checked-in secrets.toml. Never print, log or return secret values.
_SECRET_NAMES = (
    "TE_API_KEY", "TE_QWEN_API_KEY", "TE_QWEN_API_BASE",
    "TE_QWEN_MODEL", "TE_QWEN_FRAMES", "TE_GROQ_API_KEY",
    "TE_GROQ_ASR_MODEL", "TE_ENABLE_QWEN",
)
for _name in _SECRET_NAMES:
    if _name not in os.environ:
        try:
            _value = st.secrets.get(_name, "")
            if isinstance(_value, str) and _value:
                os.environ[_name] = _value
        except (FileNotFoundError, KeyError):
            pass

# Fail closed by default. This service may be visible on the open Internet.
os.environ.setdefault("TE_API_KEY", secrets.token_urlsafe(32))
os.environ["TE_ENV"] = "production"
os.environ["TE_LOCAL_NO_AUTH"] = "0"
os.environ.setdefault("TE_DATA_DIR", "/tmp/traffic-enhancer-streamlit")
os.environ.setdefault("TE_MAX_UPLOAD_MB", "50")
os.environ.setdefault("TE_MAX_SOURCE_MB", "70")
# Lightweight ONNX CPU inference: NO PyTorch/GPU download on Community Cloud.
# First analysis downloads two small public model files into ephemeral cache.
os.environ.setdefault("TE_CLOUD_VISION", "1")
os.environ.setdefault("TE_CLOUD_VISION_FRAMES", "5")
os.environ.setdefault("TE_CLOUD_PLATE_FRAMES", "5")
os.environ.pop("TE_ASR_MODEL", None)
if os.environ.get("TE_QWEN_API_KEY"):
    os.environ.setdefault("TE_ENABLE_QWEN", "1")
    os.environ.setdefault("TE_QWEN_API_BASE", "https://openrouter.ai/api/v1")
    os.environ.setdefault("TE_QWEN_MODEL", "qwen/qwen3.8-27b:free")
    os.environ.setdefault("TE_QWEN_FRAMES", "2")
if os.environ.get("TE_GROQ_API_KEY"):
    os.environ.setdefault("TE_GROQ_ASR_MODEL", "whisper-large-v3-turbo")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {background:#101a22;}
[data-testid="stSidebar"] {background:#14222c;border-right:1px solid #30424b;}
.block-container {padding-top:2.1rem;max-width:1320px;}
h1,h2,h3 {letter-spacing:-.035em;}
.hero-title {font-size:clamp(32px,3.1vw,49px);font-weight:760;
  line-height:1.12;letter-spacing:-.065em;margin:.2rem 0 .7rem;}
.hero-title span {color:#b3e6df;}
.hero-subtitle {font-size:14px;color:#a3b6c0;line-height:1.7;}
.kicker {font-size:11px;color:#91d9d1;letter-spacing:.14em;font-weight:800;}
.soft-panel {background:#182833;border:1px solid #304650;border-radius:12px;
  padding:22px 25px;margin:13px 0 20px;}
.notice {font-size:12px;color:#95abb7;line-height:1.65;}
div[data-testid="stMetric"] {border-top:1px solid #36505a;
  border-bottom:1px solid #36505a;padding:15px 6px;}
[data-testid="stMetricLabel"] {color:#a1b9c1;}
</style>""", unsafe_allow_html=True)

st.markdown(
    '<div class="kicker">TE / LAB &nbsp; · &nbsp; PUBLIC DEMO / SESSION-ONLY CASES</div>',
    unsafe_allow_html=True,
)

# No visitor password. Never show other browser sessions' case IDs.
if "te_case_ids" not in st.session_state:
    st.session_state.te_case_ids = []
if "te_upload_count" not in st.session_state:
    st.session_state.te_upload_count = 0

st.caption("No password required · Session-only case history · "
           "Use nonsensitive demo clips only; this is not a private evidence vault.")

from fastapi.testclient import TestClient  # noqa: E402
from services.api import main as backend  # noqa: E402

@st.cache_resource
def local_api() -> TestClient:
    """Run FastAPI lifespan and SQLite without exposing a second network port."""
    client = TestClient(backend.app)
    client.__enter__()
    return client

@st.cache_resource
def jobs() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="evidence-worker")

def api_request(method: str, path: str, **kwargs):
    """Keep the backend operator key on the server, never send it to the browser."""
    response = local_api().request(
        method, "/api/v1" + path,
        headers={"Authorization": "Bearer " + backend.KEY},
        **kwargs,
    )
    if response.status_code >= 400:
        try:
            info = response.json().get("detail", response.text[:180])
        except Exception:
            info = response.text[:180]
        raise RuntimeError(f"{response.status_code}: {info}")
    return response

def session_cases():
    """Show only random case IDs created in the current Streamlit session."""
    records = []
    for case_id in list(st.session_state.te_case_ids)[-20:]:
        if not re.fullmatch(r"[0-9a-f]{32}", str(case_id)):
            continue
        try:
            records.append(api_request("GET", f"/incidents/{case_id}").json())
        except RuntimeError:
            continue  # Ephemeral Cloud files can be reset at any time.
    return list(reversed(records))


@st.cache_resource
def public_demo_quota():
    return {"lock": threading.Lock(), "timestamps": []}


def reserve_demo_analysis() -> bool:
    """Small in-memory limits to reduce anonymous abuse and API spending."""
    if st.session_state.te_upload_count >= 4:
        return False
    tracker = public_demo_quota()
    with tracker["lock"]:
        now = time.monotonic()
        tracker["timestamps"][:] = [t for t in tracker["timestamps"]
                                    if now - t < 86400]
        if len(tracker["timestamps"]) >= 20:
            return False
        tracker["timestamps"].append(now)
    st.session_state.te_upload_count += 1
    return True

def stage_status(panel, label: str, data):
    record = data if isinstance(data, dict) else {}
    status = record.get("status", "unavailable")
    message = record.get("note") or ""
    if status in ("failed", "unparseable"):
        panel.error(f"{label}: {status}")
        if message:
            panel.caption(message[:280])
    elif status in ("not_configured", "unavailable", "requires_review"):
        panel.warning(f"{label}: {status.replace('_', ' ')}")
        if message:
            panel.caption(message[:230])
    elif status == "completed":
        panel.success(f"{label}: completed")
    else:
        panel.info(f"{label}: {status}")

def fmt_secs(n):
    n = int(float(n or 0))
    return f"{n//60:02}:{n%60:02}"

def date_label(raw):
    try:
        return datetime.fromisoformat(raw).strftime("%d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return "Unknown"

def upload_and_analyze(source_path: str, name: str, start: float, end: float, untrimmed: bool):
    form = {"defer_processing": "true"}
    if not untrimmed:
        form.update({"start_seconds": str(start), "end_seconds": str(end)})
    suffix = Path(name).suffix.lower()
    kind = {".mp4": "video/mp4", ".mov": "video/quicktime",
            ".mkv": "video/x-matroska"}[suffix]
    # TestClient accepts a file object and streams its contents into the API.
    # Avoid allocating another 33–70 MB bytes object when starting analysis.
    with Path(source_path).open("rb") as source:
        result = api_request(
            "POST", "/incidents", data=form,
            files={"video": (Path(name).name, source, kind)},
            timeout=360,
        )
    return result.json()

@st.cache_resource
def render_progress():
    return {"lock": threading.Lock(), "cases": {}}


def process_case(case_id):
    """API job status is written by backend.analyze_record into SQLite."""
    backend.analyze_record(case_id)
    return case_id


def prepare_full_video(case_id, seconds):
    from services.api.full_video import make_annotated_full_clip
    progress=render_progress()
    def notify(stage):
        with progress["lock"]:
            progress["cases"][case_id]=stage
    try:
        record=backend.read_incident(case_id)
        path=backend.evidence_path(record)
        return make_annotated_full_clip(path,backend.DERIVED,case_id,seconds,
                                        progress=notify)
    finally:
        with progress["lock"]:
            progress["cases"].pop(case_id,None)


@st.fragment(run_every="3s")
def pending_work():
    """Automatic progress polling, including the actual API processing stage."""
    future=st.session_state.get("pending_work")
    if future is not None:
        if not future.done():
            kind=st.session_state.get("pending_kind")
            if kind=="vision_only":
                st.info("Checking current free visual model endpoints and analyzing "
                        "the saved video frames. YOLO and video export are preserved.")
            elif kind=="rerun":
                st.info("Re-running the case analysis…")
            else:
                st.info("Uploading and trimming the selected source video…")
            return
        st.session_state.pending_work=None
        try:
            record=future.result()
            incident_id=record.get("id") if isinstance(record,dict) else None
            if not incident_id or not re.fullmatch(r"[0-9a-f]{32}",incident_id):
                raise RuntimeError("Upload did not return a valid case ID.")
            kind=st.session_state.pop("pending_kind","upload")
            if kind in ("vision_only","rerun"):
                st.session_state.active_case_id=incident_id
                visual=record.get("vision_status")
                if kind=="vision_only" and visual!="completed":
                    st.session_state.last_result=("vision_failed",record.get("note",
                        "The remote free visual provider could not analyze this clip."))
                else:
                    st.session_state.last_result=("vision_success" if kind=="vision_only"
                                                  else "success",record)
                st.rerun()
            if incident_id not in st.session_state.te_case_ids:
                st.session_state.te_case_ids.append(incident_id)
            st.session_state.active_case_id=incident_id
            # Initial upload is deferred; run local analysis once and poll the DB.
            st.session_state.processing_case_id=incident_id
            st.session_state.processing_future=jobs().submit(process_case,incident_id)
            st.rerun()
        except Exception as exc:
            st.session_state.last_result=("error",str(exc)[:350])
            st.rerun()
    active=st.session_state.get("processing_case_id")
    if active:
        try:
            record=api_request("GET",f"/incidents/{active}",timeout=15).json()
            stage=str(record.get("stage") or "queued")
            state=str(record.get("status") or "queued")
            if state not in ("ready","failed"):
                pct=None
                if stage.startswith("annotating_video:"):
                    try:
                        done,total=[int(n) for n in stage.split(":")[1].split("/")]
                        pct=min(95,round(35+55*done/max(1,total)))
                    except (TypeError,ValueError,ZeroDivisionError):
                        pct=None
                if pct is not None:
                    st.progress(pct,text=f"YOLO full-clip rendering: {stage.split(':')[1]} real frames")
                else:
                    st.info(f"Automatically processing: {stage.replace('_',' ')}")
                return
            st.session_state.processing_case_id=None
            st.session_state.processing_future=None
            st.session_state.last_result=("success",{"id":active,"status":state})
            st.rerun()
        except Exception:
            st.info("Reading current analysis progress…")
            return
    render_future=st.session_state.get("pending_render")
    if render_future is not None:
        case_id=st.session_state.get("pending_render_case_id")
        if not render_future.done():
            with render_progress()["lock"]:
                step=render_progress()["cases"].get(case_id,"preparing frames")
            st.info(f"Building a full-duration video from actual YOLO detections: {step}")
            return
        st.session_state.pending_render=None
        st.session_state.pending_render_case_id=None
        try:
            outcome=render_future.result()
            st.session_state.setdefault("recent_full_exports",{})[case_id]=outcome
            if outcome.get("status")=="completed":
                st.session_state.last_result=("render_success",outcome)
            else:
                st.session_state.last_result=("error",
                    outcome.get("note","Full-length video export failed"))
        except Exception as exc:
            safe_note=f"Render worker failed ({type(exc).__name__})."
            st.session_state.setdefault("recent_full_exports",{})[case_id]={
                "status":"failed","note":safe_note}
            st.session_state.last_result=("error",safe_note)
        st.rerun()


with st.sidebar:
    st.markdown("### ◈ TRAFFIC ENHANCER")
    st.caption("PRELIMINARY EVIDENCE INTELLIGENCE")
    area = st.radio(
        "WORKSPACE",
        ["New analysis", "Evidence studio", "Incident library", "Overview", "System health"],
        index=0, label_visibility="collapsed",
    )
    st.divider()
    st.caption("No sign-in required. Case lists are per browser session; files have no durable backup.")
    if st.button("Forget this session's case links"):
        st.session_state.te_case_ids = []
        st.rerun()

pending_work()
last_result = st.session_state.pop("last_result", None)
if last_result:
    if last_result[0] == "success":
        st.success("Analysis finished — results shown on this page below.")
    elif last_result[0] == "render_success":
        st.success("Full-length annotated video ready below.")
    elif last_result[0] == "vision_success":
        st.success("Visual reasoning updated using the saved clip; YOLO and video "
                   "were not reprocessed.")
    elif last_result[0] == "vision_failed":
        st.warning("The visual provider is still unavailable: " + str(last_result[1])[:260])
    else:
        st.error("Analysis failed: " + str(last_result[1]))

try:
    incident_list = session_cases()
except Exception as exc:
    st.error("Cannot load evidence database: " + str(exc)[:300])
    st.stop()

ready = sum(x["status"] == "ready" for x in incident_list)
processing = sum(x["status"] in ("processing", "queued") for x in incident_list)
failed = sum(x["status"] == "failed" for x in incident_list)

def render_case_detail(selected):
    """Shared actual-evidence viewer in the one-page flow and case library."""
    selected_id=selected["id"]
    a=selected.get("analysis") or {}
    st.caption(f"Case {selected_id.upper()} · {selected['status'].upper()} · {selected.get('stage','')}")
    if selected.get("error"):
        st.error(selected["error"])
    first,inspector=st.columns([1.6,1],gap="large")
    with first:
        st.markdown("### Annotated evidence viewer")
        st.caption("YOLO runs on real frames throughout the selected clip at 1–3 FPS. "
                   "The full-duration export preserves the timeline.")
        # Ephemeral Cloud restarts can remove derived MP4 after a saved
        # analysis still reports 'completed'. Use disk reality, not stale DB.
        from services.api.overlay_state import overlay_state
        session_exports=st.session_state.setdefault("recent_full_exports",{})
        full_meta=(session_exports.get(selected_id) or a.get("full_length_video") or {})
        full_video=backend.DERIVED/(selected_id+".tracked.mp4")
        full_image=backend.DERIVED/(selected_id+".tracked.jpg")
        preview_movie=backend.DERIVED/(selected_id+".samples.mp4")
        preview_image=backend.DERIVED/(selected_id+".annotated.jpg")
        viz=a.get("annotated_evidence") or {}
        try:
            original_path=backend.evidence_path(backend.read_incident(selected_id))
            original_exists=original_path.is_file()
        except Exception:
            original_exists=False
        attempts=st.session_state.setdefault("overlay_attempted_ids",set())
        pending_id=st.session_state.get("pending_render_case_id")
        pending_future=st.session_state.get("pending_render")
        job_active=(pending_id==selected_id and pending_future is not None)
        status=overlay_state(ready=selected["status"]=="ready",
                             video_exists=full_video.is_file(),
                             source_exists=original_exists,job_active=job_active,
                             attempted=selected_id in attempts,
                             last_status=(session_exports.get(selected_id) or {}).get("status"))
        if status=="auto_rebuild" and st.session_state.get("processing_case_id") is None:
            if st.session_state.get("pending_render") is None:
                attempts.add(selected_id)
                st.session_state.pending_render_case_id=selected_id
                st.session_state.pending_render=jobs().submit(
                    prepare_full_video,selected_id,float(selected["duration"]))
                status="rendering"
            else:
                status="waiting_other_job"
        if status=="waiting_other_job":
            st.info("Another video is currently rendering on this free CPU instance. "
                    "Open this case again when that job finishes.")
        if status=="source_missing":
            st.error("The original selected video is missing from this temporary "
                     "Cloud instance. The report metadata survived, but the MP4 "
                     "cannot be regenerated. Upload the source video again.")
        elif status=="rendering":
            with render_progress()["lock"]:
                current_step=render_progress()["cases"].get(selected_id,"starting CPU inference")
            st.info("Full-duration overlay is processing automatically: " +
                    str(current_step).replace("_"," ")[:100])
        elif status in ("failed","needs_retry"):
            note=session_exports.get(selected_id,{}).get("note")
            if status=="failed":
                st.error("Full-length video regeneration failed. " +
                         str(note or "The free CPU worker could not finish.")[:220])
            else:
                st.warning("The MP4 is not present on this server. Its old report "
                           "still says completed, but no render job is running. "
                           "It may have disappeared when the free app restarted.")
            if st.button("Retry full-length overlay · keep saved analysis",
                         key="retry_overlay_"+selected_id[:10],use_container_width=True,
                         disabled=(st.session_state.get("pending_render") is not None)):
                session_exports.pop(selected_id,None)
                attempts.add(selected_id)
                st.session_state.pending_render_case_id=selected_id
                st.session_state.pending_render=jobs().submit(
                    prepare_full_video,selected_id,float(selected["duration"]))
                st.rerun()
        elif status=="case_not_ready":
            st.info("The case is not ready. Live stage updates appear above.")
        if status=="available":
            st.video(full_video.read_bytes(),format="video/mp4")
            st.caption(
                f"FULL SELECTED CLIP · {float(selected['duration']):.2f}s · "
                f"genuine YOLO detection on {full_meta.get('inference_fps','1–3')} "
                "sampled frames/sec. Between updates, frames are duplicated "
                "for a normal video timeline, NOT re-detected."
            )
            st.download_button("Download full-length annotated MP4",
                               data=full_video.read_bytes(),
                               file_name=f"traffic-full-{selected_id[:10]}.mp4",
                               mime="video/mp4",key="full_download")
            if full_image.is_file():
                with st.expander("First annotated frame"):
                    st.image(str(full_image),use_container_width=True)
            cols=st.columns(3)
            cols[0].metric("Real YOLO frames",full_meta.get("analyzed_frames","—"))
            cols[1].metric("Inference FPS",full_meta.get("inference_fps","—"))
            cols[2].metric("Selected duration",f"{selected['duration']:.1f}s")
            if full_meta.get("counts"):
                import pandas as pd
                df=pd.DataFrame(full_meta["counts"])
                st.line_chart(df.set_index("second")[["vehicles"]],height=175)
        if preview_movie.is_file():
            with st.expander("Legacy five-frame diagnostic clip (not original length)"):
                st.video(preview_movie.read_bytes(),format="video/mp4")
                st.caption("This older diagnostic video is not the full-length result.")
        elif preview_image.is_file() and not full_video.is_file():
            st.image(str(preview_image),use_container_width=True,
                     caption="Existing YOLO sample while full rendering starts")
        if preview_image.is_file() and preview_movie.is_file():
            with st.expander("Annotated still frame · preview and JPG download"):
                st.image(str(preview_image),
                         caption="Original frame with actual detection rectangles",
                         use_container_width=True)
                st.download_button(
                    "Download annotated JPG",
                    data=preview_image.read_bytes(),
                    file_name=f"traffic-detections-{selected_id[:10]}.jpg",
                    mime="image/jpeg",key="annotated_jpg_download")
        sampled=(a.get("vehicle_detection") or {}).get("detections") or []
        if sampled:
            from collections import Counter
            by_time=Counter(round(float(d["second"]),2)
                            for d in sampled if isinstance(d.get("second"),(int,float)))
            if by_time:
                import pandas as pd
                table=pd.DataFrame([{"Sample second":sec,"Vehicles detected":n}
                                    for sec,n in sorted(by_time.items())])
                st.caption(f"{len(sampled)} vehicle detections across "
                           f"{len(by_time)} sampled source timestamps. "
                           "Not continuous vehicle counts.")
                st.line_chart(table.set_index("Sample second"),height=180)
        if viz.get("note"):
            st.caption(viz["note"])
        from services.api.visual_evidence import provisional_pixel_motion
        moves=full_meta.get("motion_metrics") or viz.get("motion_metrics") or provisional_pixel_motion(
            (a.get("object_tracking") or {}).get("tracks") or [])
        st.markdown("#### Motion measurements · image-plane only")
        if moves:
            st.dataframe(
                [{"Track (provisional)":m["track_id"],"Vehicle":m["vehicle"],
                  "Samples":m["observations"],
                  "Path (pixels)":m["image_path_px"],
                  "Motion (px/s)":m["image_motion_px_s"],
                  "Speed (km/h)":"N/A — uncalibrated",
                  "Ground distance":"N/A — uncalibrated"}
                 for m in moves],hide_index=True,use_container_width=True)
            from services.api.visual_evidence import motion_csv
            st.download_button("Download measured pixel-motion CSV",
                               data=motion_csv(moves),
                               file_name=f"motion-{selected_id[:10]}.csv",
                               mime="text/csv",key="motion_download")
        else:
            st.caption("At least two detections matched to the same provisional "
                       "track are required for pixel-motion measurements.")
        st.info("Real-world speed and distance require a calibrated stationary "
                "camera, known ground-plane geometry and reliable track IDs. "
                "Uncalibrated px/s is NOT km/h; do not use it as evidence of speeding.")
        with st.expander("View the unaltered original video and source frame"):
            try:
                media=backend.evidence_path(backend.read_incident(selected_id))
                if media.is_file():
                    st.video(str(media))
                else:
                    st.warning("Original is no longer on this temporary Cloud instance.")
            except Exception as exc:
                st.warning("Original unavailable: "+str(exc)[:180])
            thumb=backend.DERIVED/(selected_id+".jpg")
            if thumb.is_file():
                st.image(str(thumb),caption="Unannotated original source frame",
                         use_container_width=True)
        st.markdown("#### Relevant model observations")
        observation=(a.get("visual_reasoning") or {}).get("observations") or {}
        st.write(observation.get("scene_summary") or "No visual scene interpretation is available.")
        events=(a.get("violation_assessment") or {}).get("candidates") or []
        if events:
            st.dataframe(events,use_container_width=True,hide_index=True)
        else:
            st.caption("No supported candidate events. This is not evidence that the recording contains no offense.")
        tracking = a.get("object_tracking") or {}
        detections = (a.get("vehicle_detection") or {}).get("detections") or []
        tracks = tracking.get("tracks") or []
        st.markdown("#### Actual YOLO vehicle detections")
        if detections:
            st.dataframe(
                [{"Second":d.get("second"),"Vehicle":d.get("label"),
                  "Confidence":d.get("confidence"),"Provisional track":d.get("track_id"),
                  "Bounding box":d.get("box_xyxy")} for d in detections[:80]],
                hide_index=True,use_container_width=True
            )
        else:
            st.caption("No vehicles detected in sampled frames, or the detector could not run.")
        st.caption(f"{len(tracks)} provisional track IDs. Sparse IoU associations "
                   "are not verified vehicle identities and are NOT BoT-SORT.")
        plates = a.get("plate_recognition") or {}
        st.markdown("#### Arabic license-plate OCR candidates (Egypt format requires review)")
        st.caption(f"Detected plate regions: {plates.get('plates_detected',0)} · "
                   "No OCR reading is automatically confirmed.")
        if plates.get("candidates"):
            st.dataframe(plates["candidates"],hide_index=True,use_container_width=True)
        else:
            st.caption("No readable plate candidates at these distances or lighting conditions.")
    with inspector:
        st.markdown("#### AI processing stages")
        stage_status(st,"Vehicle tracking",a.get("object_tracking"))
        stage_status(st,"Driver speech",a.get("transcription"))
        vision_state=a.get("visual_reasoning") or {}
        stage_status(st,"Visual scene reasoning",vision_state)
        if vision_state.get("status")=="completed":
            st.caption("Actual model: " + str(vision_state.get("model") or "unknown")[:100])
            if vision_state.get("routing")=="OpenRouter free multimodal router":
                st.caption("Free auto-router selected the actual model shown above. "
                           "It may not be Qwen.")
        elif vision_state.get("status")=="failed":
            st.caption("404 can mean an unavailable model or an account/provider "
                       "routing restriction. The no-cost fallback is automatic on "
                       "new requests; old failures need visual-only retry.")
        if vision_state.get("status") in ("failed","unparseable"):
            st.info("This is the last SAVED visual result, not a live request. "
                    "HTTP 404 may mean that OpenRouter cannot route to a provider "
                    "allowed by your account's privacy settings. Retry visual AI "
                    "here without repeating the YOLO video analysis.")
        if selected["status"]=="ready":
            if st.button("Retry visual AI only · keep YOLO and full video",
                         key="retry_visual_only",use_container_width=True,
                         disabled=st.session_state.get("pending_work") is not None):
                if reserve_demo_analysis():
                    st.session_state.pending_kind="vision_only"
                    st.session_state.pending_work=jobs().submit(
                        lambda: api_request("POST",
                            f"/incidents/{selected_id}/retry-vision",
                            timeout=240).json())
                    st.rerun()
                else:
                    st.warning("The public demo processing limit was reached.")
        plates_stage=a.get("plate_recognition") or {}
        if plates_stage.get("status")=="completed":
            if plates_stage.get("candidates"):
                st.warning("Plate detector ran; OCR candidates need human verification. "
                           "No registration number is confirmed.")
            else:
                st.info("Plate detection completed, but no reliable Egyptian plate "
                        "characters were recovered. Do not assume a readable plate.")
        else:
            stage_status(st,"Plate detection and tentative Arabic OCR",plates_stage)
        stage_status(st,"Potential violation review",a.get("violation_assessment"))
        if selected["status"] in ("ready","failed"):
            if st.button("Re-run all stages (slower)",use_container_width=True):
                if reserve_demo_analysis():
                    st.session_state.pending_kind = "rerun"
                    st.session_state.pending_work=jobs().submit(
                        lambda: api_request("POST",f"/incidents/{selected_id}/reanalyze",
                                            timeout=360).json())
                    st.rerun()
                else:
                    st.warning("Public demo processing limit reached.")
        if selected["status"]=="ready":
            try:
                pdf=api_request("GET",f"/incidents/{selected_id}/report.pdf").content
                st.download_button(
                    "Download preliminary PDF",
                    data=pdf, file_name=f"traffic-report-{selected_id[:12]}.pdf",
                    mime="application/pdf",use_container_width=True)
            except Exception as exc:
                st.warning("PDF export unavailable: "+str(exc)[:180])
        st.caption("AI guesses must always be reviewed against the original video. Never treat a suggested incident as an official finding.")


if area == "Overview":
    st.markdown('<div class="kicker">EVIDENCE INTELLIGENCE / OVERVIEW</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">See the full <span>picture.</span></div>',
                unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Upload real road footage, inspect preliminary observations, and preserve the selected clip’s SHA-256 evidence trail.</p>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total cases", len(incident_list))
    c2.metric("Ready to inspect", ready)
    c3.metric("In progress", processing)
    c4.metric("Needs attention", failed)
    st.markdown("#### Recent recordings")
    if not incident_list:
        st.info("Your case library is empty. Choose **New analysis** from the sidebar to begin.")
    else:
        for item in incident_list[:6]:
            with st.container(border=True):
                left,right=st.columns([4,1])
                left.markdown(f"**{item['filename']}**")
                left.caption(f"{item['id'][:12].upper()} · {fmt_secs(item['duration'])} · {date_label(item['created_at'])}")
                right.markdown(f"**{item['status'].upper()}**")
    st.caption("This is preliminary evidence-review software, not official traffic enforcement.")

elif area == "New analysis":
    st.markdown('<div class="kicker">01 / EVIDENCE INTAKE</div>', unsafe_allow_html=True)
    st.header("Bring in your recording.")
    st.caption("Upload a real MP4, MOV or MKV file (up to 70 MB). Select a segment before analysis, or use the full video.")
    if "upload_widget_generation" not in st.session_state:
        st.session_state.upload_widget_generation=0
    incoming = st.file_uploader(
        "01 · Choose dashcam footage", type=["mp4", "mov", "mkv"],
        accept_multiple_files=False,
        key=f"source_uploader_{st.session_state.upload_widget_generation}",
    )
    if st.button("Reset stuck upload / choose a file again",key="retry_stuck_upload"):
        st.session_state.upload_widget_generation+=1
        st.session_state.video_signature=None
        st.session_state.video_metadata=None
        st.session_state.video_error=None
        st.session_state.upload_source_path=None
        st.rerun()
    st.caption("If the file spinner keeps turning for over a minute, use Reset above. "
               "An incomplete browser upload has not yet reached FFprobe or AI. "
               "A fresh browser tab or Streamlit Cloud reboot may be needed if the "
               "connection has stalled.")
    st.markdown("### 02 · Optional clip trimming")
    st.caption("The timeline, exact start/end fields and video preview appear once the uploaded file has finished transferring and FFprobe has read its duration.")
    if incoming is None:
        st.info("Choose a video above. You can then trim any 1–180-second section, or analyze the whole file if it is up to 180 seconds long.")
    else:
        from services.api.upload_intake import fingerprint_upload, spool_uploaded_file
        try:
            signature=fingerprint_upload(incoming)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Browser upload received: {signature[0]} ({signature[1]/1048576:.1f} MiB).")
            if st.session_state.get("video_signature") != signature:
                st.session_state.video_signature=signature
                st.session_state.video_metadata=None
                st.session_state.video_error=None
                st.session_state.upload_source_path=None
                with st.spinner("Saving the received clip and reading its duration with FFprobe…"):
                    temp_dir=tempfile.TemporaryDirectory(prefix="traffic-upload-")
                    try:
                        source=spool_uploaded_file(incoming, Path(temp_dir.name), signature)
                        backend.ensure_media_tools()
                        metadata=backend.probe(source)
                        st.session_state.video_metadata=metadata
                        st.session_state.upload_source_path=str(source)
                        # Preserve this source while a background analysis may
                        # still be reading it; cleanup occurs on session disposal.
                        st.session_state.setdefault("upload_tempdirs",[]).append(temp_dir)
                    except Exception as exc:
                        temp_dir.cleanup()
                        st.session_state.video_error=(
                            f"{type(exc).__name__}: video intake/metadata failed. "
                            "Try a browser-compatible MP4 or reset and re-upload."
                        )
            if st.session_state.get("video_error"):
                st.error("Cannot read this recording: " + st.session_state.video_error)
                st.caption("Try an MP4 encoded with H.264; do not start analysis until the source can be inspected.")
            elif st.session_state.get("video_metadata"):
                from services.api.clip_selection import choose_clip_interval

                meta = st.session_state.video_metadata
                duration = float(meta["duration_seconds"])
                # Round DOWN rather than up: the API validates clip ends
                # against FFprobe's precise source duration.
                upper = max(1.0, int(duration * 10) / 10.0)
                if st.session_state.get("clip_signature") != signature:
                    st.session_state.clip_signature = signature
                    st.session_state.clip_mode = "Select a clip (recommended)"
                    st.session_state.clip_range = (0.0, min(20.0, upper))
                    st.session_state.clip_start = 0.0
                    st.session_state.clip_end = min(20.0, upper)

                def sync_range_to_fields():
                    st.session_state.clip_start = float(st.session_state.clip_range[0])
                    st.session_state.clip_end = float(st.session_state.clip_range[1])

                def sync_fields_to_range():
                    begin = float(st.session_state.clip_start)
                    finish = float(st.session_state.clip_end)
                    if 0 <= begin < finish <= upper:
                        st.session_state.clip_range = (begin, finish)

                mode = st.radio(
                    "What should be analyzed?",
                    ["Select a clip (recommended)", "Analyze the entire video"],
                    key="clip_mode", horizontal=True,
                )
                if mode == "Select a clip (recommended)":
                    st.slider(
                        "Trim timeline — drag either handle",
                        min_value=0.0, max_value=upper,
                        step=0.1, key="clip_range",
                        on_change=sync_range_to_fields,
                    )
                    first, last = st.columns(2)
                    with first:
                        st.number_input(
                            "START · seconds", min_value=0.0,
                            max_value=upper, step=0.1, format="%.1f",
                            key="clip_start", on_change=sync_fields_to_range,
                        )
                    with last:
                        st.number_input(
                            "END · seconds", min_value=0.0,
                            max_value=upper, step=0.1, format="%.1f",
                            key="clip_end", on_change=sync_fields_to_range,
                        )
                    start = float(st.session_state.clip_start)
                    end = float(st.session_state.clip_end)
                else:
                    start, end = 0.0, duration

                try:
                    start, end, full = choose_clip_interval(
                        duration, mode == "Analyze the entire video",
                        start, end
                    )
                    selection_error = None
                except ValueError as exc:
                    selection_error = str(exc)
                    full = False

                if selection_error:
                    st.warning(selection_error)
                else:
                    st.info(
                        f"Selected {fmt_secs(start)} → {fmt_secs(end)}"
                        f"  ·  {end-start:.1f} seconds"
                        f"  ·  {'Entire source' if full else 'Only this section will be analyzed'}."
                    )

                left, right = st.columns([1.6, 1], gap="large")
                with left:
                    st.markdown("#### 03 · Preview your selection")
                    if incoming.name.lower().endswith(".mp4") and signature[1] < 50 * 1024 * 1024:
                        if selection_error:
                            st.info("Enter valid start and end times to preview the selected segment.")
                        elif full:
                            st.video(st.session_state.upload_source_path, format="video/mp4",
                                     alt="Original dashcam recording")
                        else:
                            # Streamlit natively stops preview at the selection's
                            # end; no expensive server-side transcoding is needed.
                            st.video(st.session_state.upload_source_path, format="video/mp4",
                                     start_time=f"{start:.1f}s",
                                     end_time=f"{end:.1f}s",
                                     alt="Preview of exactly the selected segment")
                        st.caption("Preview is limited to the selected timeline. "
                                   "The server trims accurately after you press Analyze.")
                    else:
                        st.info("A browser preview is unavailable for this format/size. "
                                "The start/end controls still work; the server trims the original.")
                with right:
                    st.metric("Full source duration", fmt_secs(duration))
                    st.metric("Selected analysis duration",
                              "—" if selection_error else f"{end-start:.1f}s")
                    st.caption(f"FPS: {meta.get('frame_rate') or 'Unknown'}")
                    st.caption("Audio track: " + ("Yes" if meta.get("has_audio") else "No"))
                    st.caption("Your original video is transferred in full before trimming. "
                               "For slower connections, upload a smaller source copy.")

                st.markdown("#### 04 · Analyze the selected footage")
                st.button(
                    "Analyze recording",
                    key="analyze_clip",
                    type="primary", use_container_width=True,
                    disabled=selection_error is not None or
                             st.session_state.get("pending_work") is not None or
                             st.session_state.get("processing_case_id") is not None,
                    on_click=None,
                )
                # The button's clicked value is an ephemeral Streamlit state;
                # consume it immediately, never treat a previous run as a click.
                if st.session_state.get("analyze_clip", False) and not selection_error:
                    if reserve_demo_analysis():
                        st.session_state.pending_kind = "upload"
                        st.session_state.pending_work = jobs().submit(
                            upload_and_analyze, st.session_state.upload_source_path, incoming.name,
                            start, end, full
                        )
                        st.rerun()
                    else:
                        st.warning("Public demo processing limit reached. Try later or use the local app.")
                st.caption("CPU YOLO detects sampled vehicles and a pretrained generic "
                       "plate locator feeds tentative Arabic OCR. Egyptian-specific "
                       "performance is not validated. First run may "
                       "download public ONNX weights. Qwen/Whisper use separate API keys.")

    st.divider()
    st.markdown("### 05 · Live results & annotated video")
    if incident_list:
        labels={x["id"]:f"{x['filename']} · {x['status']} · {x['id'][:8]}" for x in incident_list}
        default_id=st.session_state.get("active_case_id")
        ids=list(labels.keys())
        idx=ids.index(default_id) if default_id in ids else 0
        chosen_id=st.selectbox("Your recent recordings",ids,index=idx,
                               format_func=lambda key:labels[key],key="inline_case_select")
        st.session_state.active_case_id=chosen_id
        render_case_detail(next(x for x in incident_list if x["id"]==chosen_id))
    elif st.session_state.get("pending_work") is None:
        st.caption("Your annotated video and measurements will appear here automatically.")

elif area in ("Evidence studio","Incident library"):
    st.markdown('<div class="kicker">02 / FOOTAGE & ANALYSIS</div>', unsafe_allow_html=True)
    st.header("Evidence studio" if area == "Evidence studio" else "Incident library")
    if not incident_list:
        st.info("No recordings yet. Use New analysis to submit a short clip.")
    else:
        labels={x["id"]:f"{x['filename']} · {x['id'][:9]} · {x['status']}" for x in incident_list}
        selected_id=st.selectbox("Select a recording",list(labels.keys()),
                                 format_func=lambda key:labels[key])
        selected=next(x for x in incident_list if x["id"]==selected_id)
        if area=="Incident library":
            st.dataframe(
                [{"Recording":x["filename"],"Uploaded":date_label(x["created_at"]),
                  "Clip seconds":round(x["duration"],1),"Status":x["status"],
                  "Case ID":x["id"][:12]} for x in incident_list],
                hide_index=True, use_container_width=True,
            )
        render_case_detail(selected)

elif area=="System health":
    st.markdown('<div class="kicker">03 / SYSTEM CAPABILITIES</div>', unsafe_allow_html=True)
    st.header("See what is actually configured.")
    caps=api_request("GET","/capabilities").json()
    labels=[
        ("Qwen2.5-VL scene reasoning","qwen"),
        ("Groq Whisper speech","speech"),
        ("YOLO vehicle detection","vehicle_tracking"),
        ("Egyptian plate OCR","plate_ocr"),
    ]
    for title,key in labels:
        cap=caps.get(key,{})
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption("Enabled — runtime unverified" if cap.get("configured") else "Not configured on Streamlit Community Cloud")
    st.markdown("#### Local CPU models · actual readiness check")
    st.caption("Optional: load both real ONNX detectors and run them on a generated "
               "blank image, then inspect installed Tesseract languages. First check "
               "may download public weights and take time on free Cloud. No road "
               "footage is used or transmitted; success does NOT measure accuracy.")
    if st.button("Test CPU YOLO, plate detector and Arabic OCR installation",
                 use_container_width=True, key="run_cpu_readiness"):
        from services.api.vision_diagnostics import cpu_detector_readiness
        with st.spinner("Loading CPU ONNX models and checking OCR languages…"):
            st.session_state.cpu_readiness=cpu_detector_readiness()
    cpu=st.session_state.get("cpu_readiness")
    if cpu:
        for name, title in (
            ("vehicle", "Vehicle YOLO ONNX"),
            ("plate", "Generic license plate ONNX (Egypt unvalidated)"),
            ("arabic_ocr", "Tesseract Arabic + English")):
            item=cpu.get(name,{})
            status=item.get("status","failed")
            label=f"{title}: "
            if status=="ready":
                elapsed=item.get("elapsed_seconds")
                timing=f" ({elapsed:.2f}s on synthetic image)" if isinstance(elapsed,(float,int)) else ""
                st.success(label+"runtime executed successfully"+timing)
            elif status=="partial":
                st.warning(label+"only partial language support available")
            elif status=="disabled":
                st.info(label+"disabled by TE_CLOUD_VISION configuration")
            else:
                st.error(label+"runtime check failed ("+
                         str(item.get("error_type","unknown error"))+")")
        st.caption("These checks verify loading/execution ONLY. They do not establish "
                   "detection accuracy, Egyptian plate readability, or vehicle speed.")
    st.caption("Health diagnostics UI revision: CPU-check-2026-10-27")
    st.markdown("#### OpenRouter · free image AI diagnostics")
    st.caption("The public catalog, account-filtered catalog, and live inference "
               "are three DIFFERENT checks. No road footage is sent here.")
    from services.api.vision_diagnostics import (
        catalog_diagnostics, test_free_image_inference
    )
    key=os.getenv("TE_QWEN_API_KEY","")
    diag_store=st.session_state.get("free_vision_diagnostics")
    left_button,right_button=st.columns(2)
    with left_button:
        check_catalog=st.button(
            "Check free image models + account permissions",
            use_container_width=True,key="check_vision_catalog")
    with right_button:
        check_inference=st.button(
            "Test my API key with a generated image",
            use_container_width=True,key="check_vision_probe")
    st.caption("Catalog check doesn't send video. Image test makes ONE free "
               "inference request using a generated icon (not your footage); "
               "it may count toward your daily free request allowance.")
    if check_catalog:
        with st.spinner("Reading OpenRouter model catalogs…"):
            diag_store=catalog_diagnostics(key)
            st.session_state.free_vision_diagnostics=diag_store
    if diag_store:
        public=diag_store["public"]
        account=diag_store["account"]
        if public["status"]=="available":
            count=public["count_free_image"]
            st.success(f"Public catalog reachable: {count} zero-priced image-capable "
                       "model variants found.")
            qwen=public["free_image_qwen"]
            others=public["free_image_other"]
            if qwen:
                st.markdown("**Free image-capable Qwen models**")
                st.code("\n".join(qwen))
            else:
                st.info("No Qwen variant matched the free image catalog filters. "
                        "This does NOT mean every free image model is unavailable.")
            if others:
                with st.expander("Other free image models found"):
                    st.code("\n".join(others))
            st.caption("Free automatic image router: openrouter/free "
                       "(may choose a non-Qwen vision model).")
        else:
            st.error("Public catalog failed: "+str(public.get("message","Unknown error")))
        if account["status"]=="available":
            st.info(f"Account-filtered list: {account['count_free_image']} free "
                    "image-capable variants under current provider/privacy rules "
                    "(not a guarantee of live inference).")
            with st.expander("Free image models visible to this account"):
                permitted=account["free_image_qwen"]+account["free_image_other"]
                st.code("\n".join(permitted) if permitted else "No eligible models listed")
        elif account["status"]=="not_configured":
            st.warning("TE_QWEN_API_KEY is missing from Streamlit Secrets.")
        elif account.get("http_status")==403:
            st.warning("Account-filtered model endpoint returned 403; some keys "
                       "cannot use this endpoint. Use the live generated-image test.")
        elif account.get("http_status")==401:
            st.error("HTTP 401: OpenRouter rejected your key. Replace "
                     "TE_QWEN_API_KEY in Streamlit Secrets.")
        else:
            st.warning("Account-specific listing failed: " +
                       str(account.get("message","Unknown reason")))
    if check_inference:
        with st.spinner("Testing free image inference (no footage sent)…"):
            st.session_state.free_vision_probe=test_free_image_inference(key)
    probe=st.session_state.get("free_vision_probe")
    if probe:
        if probe["status"]=="success":
            st.success(probe["message"])
            st.caption("Actual responding model: "+probe.get("model","Not reported"))
            st.info("Your key can use the free image router. For an existing "
                    "case, use Retry visual AI only; YOLO and video are retained.")
        elif probe["status"]=="not_configured":
            st.warning(probe["message"])
        else:
            st.error("Free visual inference failed: "+probe["message"])
    st.caption("HTTP 404 on inference can mean no compatible provider allowed "
               "by account privacy settings. A public model page alone cannot "
               "verify access for your key. No paid model is auto-selected.")
    st.warning("Configured means enabled, not validated. The CPU ONNX detectors download "
               "public weights on first analysis and may run slowly on free Cloud. "
               "OCR is tentative. OpenRouter and Groq still require valid secrets.")
    st.info("This no-password demo shows only the current browser session's cases, but "
            "files still live in temporary shared server storage. They are not encrypted "
            "or permanently preserved. Anyone with the URL can consume the limited AI "
            "quota. Upload nonsensitive videos only. No official enforcement.")
