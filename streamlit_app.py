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

def upload_and_analyze(blob: bytes, name: str, start: float, end: float, untrimmed: bool):
    form = {} if untrimmed else {"start_seconds": str(start), "end_seconds": str(end)}
    suffix = Path(name).suffix.lower()
    kind = {".mp4": "video/mp4", ".mov": "video/quicktime",
            ".mkv": "video/x-matroska"}[suffix]
    result = api_request(
        "POST", "/incidents", data=form,
        files={"video": (Path(name).name, blob, kind)},
        timeout=360,
    )
    return result.json()

@st.fragment(run_every="4s")
def pending_work():
    future = st.session_state.get("pending_work")
    if future is None:
        return
    if not future.done():
        st.info("Analyzing your recording. The original clip and hash are kept in this temporary demo session. This can be slow on free cloud CPU.")
        return
    st.session_state.pending_work = None
    try:
        result = future.result()
        if st.session_state.pop("pending_kind", "") == "upload":
            incident_id = result.get("id") if isinstance(result, dict) else None
            if incident_id and re.fullmatch(r"[0-9a-f]{32}", str(incident_id)):
                if incident_id not in st.session_state.te_case_ids:
                    st.session_state.te_case_ids.append(incident_id)
        st.session_state.last_result = ("success", result)
    except Exception as exc:
        st.session_state.last_result = ("error", str(exc)[:500])
    st.rerun()

with st.sidebar:
    st.markdown("### ◈ TRAFFIC ENHANCER")
    st.caption("PRELIMINARY EVIDENCE INTELLIGENCE")
    area = st.radio(
        "WORKSPACE",
        ["Overview", "New analysis", "Evidence studio", "Incident library", "System health"],
        label_visibility="collapsed",
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
        st.success(f"Recording analyzed and saved as case {last_result[1]['id'][:12]}. Open Evidence studio to inspect real results.")
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
    incoming = st.file_uploader(
        "01 · Choose dashcam footage", type=["mp4", "mov", "mkv"],
        accept_multiple_files=False, key="source_uploader",
    )
    st.markdown("### 02 · Optional clip trimming")
    st.caption("The timeline, exact start/end fields and video preview appear once the uploaded file has finished transferring and FFprobe has read its duration.")
    if incoming is None:
        st.info("Choose a video above. You can then trim any 1–180-second section, or analyze the whole file if it is up to 180 seconds long.")
    else:
        blob = incoming.getvalue()
        if len(blob) > 70 * 1024 * 1024:
            st.error("The cloud demo accepts at most 70 MB per source. Please upload a smaller version.")
        else:
            signature = (incoming.name, len(blob), hashlib.sha256(blob).hexdigest())
            if st.session_state.get("video_signature") != signature:
                st.session_state.video_signature = signature
                st.session_state.video_metadata = None
                st.session_state.video_error = None
                with st.spinner("Upload received. Inspecting video duration with FFprobe…"):
                    try:
                        with tempfile.TemporaryDirectory() as temp:
                            source = Path(temp) / Path(incoming.name).name
                            source.write_bytes(blob)
                            backend.ensure_media_tools()
                            st.session_state.video_metadata = backend.probe(source)
                    except Exception as exc:
                        st.session_state.video_error = str(exc)
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
                    if incoming.name.lower().endswith(".mp4") and len(blob) < 50 * 1024 * 1024:
                        if selection_error:
                            st.info("Enter valid start and end times to preview the selected segment.")
                        elif full:
                            st.video(blob, format="video/mp4",
                                     alt="Original dashcam recording")
                        else:
                            # Streamlit natively stops preview at the selection's
                            # end; no expensive server-side transcoding is needed.
                            st.video(blob, format="video/mp4",
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
                             st.session_state.get("pending_work") is not None,
                    on_click=None,
                )
                # The button's clicked value is an ephemeral Streamlit state;
                # consume it immediately, never treat a previous run as a click.
                if st.session_state.get("analyze_clip", False) and not selection_error:
                    if reserve_demo_analysis():
                        st.session_state.pending_kind = "upload"
                        st.session_state.pending_work = jobs().submit(
                            upload_and_analyze, blob, incoming.name,
                            start, end, full
                        )
                        st.rerun()
                    else:
                        st.warning("Public demo processing limit reached. Try later or use the local app.")
                st.caption("CPU YOLO detects sampled vehicles and a pretrained generic "
                       "plate locator feeds tentative Arabic OCR. Egyptian-specific "
                       "performance is not validated. First run may "
                       "download public ONNX weights. Qwen/Whisper use separate API keys.")

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
        a=selected.get("analysis") or {}
        st.caption(f"Case {selected_id.upper()} · {selected['status'].upper()} · {selected.get('stage','')}")
        if selected.get("error"):
            st.error(selected["error"])
        first,inspector=st.columns([1.6,1],gap="large")
        with first:
            st.markdown("### Annotated evidence viewer")
            st.caption("Bounding boxes are from real sampled source frames, not "
                       "fictional continuous tracking.")
            # Recover the annotated media from existing saved YOLO results;
            # this NEVER calls OpenRouter/Groq or re-runs neural inference.
            saved_detections=(a.get("vehicle_detection") or {}).get("detections") or []
            cached_movie=backend.DERIVED/(selected_id+".samples.mp4")
            if not cached_movie.is_file() and saved_detections:
                if st.button("Generate boxes from saved detections · no API usage",
                             key="offline_annotations",use_container_width=True):
                    from services.api.visual_evidence import render_sampled_evidence
                    with st.spinner("Drawing boxes on actual source timestamps…"):
                        result=render_sampled_evidence(
                            backend.evidence_path(backend.read_incident(selected_id)),
                            backend.DERIVED,selected_id,
                            {"detections": saved_detections,
                             "tracks": (a.get("object_tracking") or {}).get("tracks",[])},
                            a.get("plate_recognition") or {})
                        if result["status"]!="completed":
                            st.warning(result.get("note","Could not create montage"))
                        else:
                            st.rerun()
            viz=a.get("annotated_evidence") or {}
            preview_image=backend.DERIVED/(selected_id+".annotated.jpg")
            preview_movie=backend.DERIVED/(selected_id+".samples.mp4")
            if preview_movie.is_file():
                st.video(preview_movie.read_bytes(),format="video/mp4")
                st.caption("Sampled-frame review montage: each image is a REAL "
                           "timestamped YOLO observation held for 1 second. "
                           "Not continuous full-video tracking; no interpolated boxes.")
                st.download_button("Download annotated sampled video",
                                   data=preview_movie.read_bytes(),
                                   file_name=f"traffic-samples-{selected_id[:10]}.mp4",
                                   mime="video/mp4",key="annotated_download")
            elif preview_image.is_file():
                st.image(str(preview_image),use_container_width=True,
                         caption="Detected boxes on real sampled source frame")
            elif selected["status"]=="ready":
                st.info("Annotated preview not generated for this analysis. "
                        "Press Re-run AI analysis to produce annotated media.")
            if viz.get("note"):
                st.caption(viz["note"])
            from services.api.visual_evidence import provisional_pixel_motion
            moves=viz.get("motion_metrics") or provisional_pixel_motion(
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
            stage_status(st,"Qwen vision reasoning",a.get("visual_reasoning"))
            stage_status(st,"Egyptian plate OCR",a.get("plate_recognition"))
            stage_status(st,"Potential violation review",a.get("violation_assessment"))
            if selected["status"] in ("ready","failed"):
                if st.button("Re-run AI analysis on this clip",use_container_width=True):
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
            st.caption("Configured" if cap.get("configured") else "Not configured on Streamlit Community Cloud")
    st.warning("Configured means enabled, not validated. The CPU ONNX detectors download "
               "public weights on first analysis and may run slowly on free Cloud. "
               "OCR is tentative. OpenRouter and Groq still require valid secrets.")
    st.info("This no-password demo shows only the current browser session's cases, but "
            "files still live in temporary shared server storage. They are not encrypted "
            "or permanently preserved. Anyone with the URL can consume the limited AI "
            "quota. Upload nonsensitive videos only. No official enforcement.")
