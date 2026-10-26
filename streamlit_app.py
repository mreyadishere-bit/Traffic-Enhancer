"""Traffic Enhancer — Streamlit Community Cloud entrypoint.

Native Streamlit UI over the repository's EXISTING FastAPI analysis engine.
Uses an in-process authenticated TestClient; this is an operator-only,
resource-limited, non-persistent demo, not a public enforcement service.
"""
from __future__ import annotations

import hashlib
import hmac
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
os.environ["TE_ENV"] = "production"
os.environ["TE_LOCAL_NO_AUTH"] = "0"
os.environ.setdefault("TE_DATA_DIR", "/tmp/traffic-enhancer-streamlit")
os.environ.setdefault("TE_MAX_UPLOAD_MB", "50")
os.environ.setdefault("TE_MAX_SOURCE_MB", "70")
# The free cloud has no local GPU. Only remote opt-in providers run.
os.environ.pop("TE_YOLO_MODEL", None)
os.environ.pop("TE_ASR_MODEL", None)
os.environ.pop("TE_PLATE_MODEL", None)
if os.environ.get("TE_QWEN_API_KEY"):
    os.environ.setdefault("TE_ENABLE_QWEN", "1")
    os.environ.setdefault("TE_QWEN_API_BASE", "https://openrouter.ai/api/v1")
    os.environ.setdefault("TE_QWEN_MODEL", "qwen/qwen-2.5-vl-7b-instruct:free")
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
    '<div class="kicker">TE / LAB &nbsp; · &nbsp; PRIVATE EVIDENCE WORKSPACE</div>',
    unsafe_allow_html=True,
)

_SECRET = os.environ.get("TE_API_KEY", "").strip()
if not _SECRET or len(_SECRET) < 16:
    st.error("Cloud deployment is locked. Add a strong TE_API_KEY (at least 16 characters) in Streamlit app Settings → Secrets.")
    st.caption("This app will not expose uploaded recordings without an operator secret.")
    st.stop()

if "te_logged_in" not in st.session_state:
    st.session_state.te_logged_in = False

if not st.session_state.te_logged_in:
    st.markdown(
        '<div class="hero-title">Safer roads start<br>with <span>better evidence.</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="hero-subtitle">Enter your private operator password to access the video evidence workspace.</p>',
                unsafe_allow_html=True)
    with st.form("sign_in"):
        supplied = st.text_input("Operator password", type="password")
        submit = st.form_submit_button("Open workspace", type="primary", use_container_width=True)
    if submit:
        if hmac.compare_digest(supplied.encode(), _SECRET.encode()):
            st.session_state.te_logged_in = True
            st.rerun()
        else:
            st.error("Incorrect operator password.")
    st.stop()

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
        headers={"Authorization": "Bearer " + _SECRET},
        **kwargs,
    )
    if response.status_code >= 400:
        try:
            info = response.json().get("detail", response.text[:180])
        except Exception:
            info = response.text[:180]
        raise RuntimeError(f"{response.status_code}: {info}")
    return response

def all_cases():
    return api_request("GET", "/incidents").json().get("items", [])

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
    st.caption("Private demo · Uploaded files are not permanently stored or backed up on Community Cloud.")
    if st.button("Sign out"):
        st.session_state.te_logged_in = False
        st.session_state.pop("pending_work", None)
        st.rerun()

pending_work()
last_result = st.session_state.pop("last_result", None)
if last_result:
    if last_result[0] == "success":
        st.success(f"Recording analyzed and saved as case {last_result[1]['id'][:12]}. Open Evidence studio to inspect real results.")
    else:
        st.error("Analysis failed: " + str(last_result[1]))

try:
    incident_list = all_cases()
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
    st.header("Begin with the real recording.")
    st.caption("MP4, MOV or MKV. Keep sources short on free Cloud. A selected interval can be up to 180 seconds.")
    incoming = st.file_uploader("Choose dashcam footage", type=["mp4","mov","mkv"],
                                accept_multiple_files=False)
    if incoming:
        blob = incoming.getvalue()
        if len(blob) > 70 * 1024 * 1024:
            st.error("This cloud demo accepts up to 70 MB per source. Use a smaller copy locally.")
        else:
            signature=(incoming.name,len(blob),hashlib.sha256(blob).hexdigest())
            if st.session_state.get("video_signature") != signature:
                with st.spinner("Reading video metadata with FFprobe…"):
                    try:
                        with tempfile.TemporaryDirectory() as temp:
                            source=Path(temp)/Path(incoming.name).name
                            source.write_bytes(blob)
                            backend.ensure_media_tools()
                            st.session_state.video_metadata = backend.probe(source)
                            st.session_state.video_error = None
                    except Exception as exc:
                        st.session_state.video_metadata = None
                        st.session_state.video_error = str(exc)
                st.session_state.video_signature = signature
            if st.session_state.get("video_error"):
                st.error(st.session_state.video_error)
            elif st.session_state.get("video_metadata"):
                meta=st.session_state.video_metadata
                duration=float(meta["duration_seconds"])
                left,right=st.columns([1.5,1])
                with left:
                    st.markdown("**Original recording**")
                    if incoming.name.lower().endswith(".mp4") and len(blob)<35*1024*1024:
                        st.video(blob, format="video/mp4")
                    else:
                        st.info("Video preview may require an MP4/H.264 copy. Accurate time ranges are still available.")
                with right:
                    st.metric("Source duration", fmt_secs(duration))
                    st.caption(f"Frame rate: {meta.get('frame_rate') or 'Unknown'} · Audio track: {'Yes' if meta.get('has_audio') else 'No'}")
                    st.caption("Original file kept only in temporary Cloud storage, with no backup.")
                with st.form("analyze_form"):
                    upper=round(duration,1)
                    default_end=min(20.0, upper)
                    selected_range=st.slider(
                        "Select source interval (seconds)", min_value=0.0,
                        max_value=upper, value=(0.0,default_end), step=0.1,
                    )
                    st.caption(f"Selected {fmt_secs(selected_range[0])} – {fmt_secs(selected_range[1])}, "
                               f"{selected_range[1]-selected_range[0]:.1f} sec.")
                    submit=st.form_submit_button(
                        "Analyze selected recording", type="primary",
                        use_container_width=True,
                        disabled=st.session_state.get("pending_work") is not None,
                    )
                if submit:
                    start,end=selected_range
                    if end-start<1 or end-start>180:
                        st.error("Select between 1 and 180 seconds.")
                    elif len(blob)>50*1024*1024 and start==0 and end>=upper-0.1:
                        st.error("Choose a shorter interval or smaller source file for Cloud processing.")
                    else:
                        full=abs(start)<0.01 and end>=duration-0.11 and duration<=180
                        st.session_state.pending_work=jobs().submit(
                            upload_and_analyze,blob,incoming.name,start,end,full)
                        st.rerun()
                st.caption("Qwen and Whisper run only when you configure their secrets; GPU-based YOLO and Egyptian plate OCR are not enabled on free Community Cloud.")

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
            st.markdown("#### Real recorded footage")
            try:
                media=backend.evidence_path(backend.read_incident(selected_id))
                if media.is_file():
                    st.video(str(media))
                else:
                    st.warning("The selected media is no longer on this temporary Cloud instance.")
            except Exception as exc:
                st.warning("Video unavailable: "+str(exc)[:180])
            thumb=backend.DERIVED/(selected_id+".jpg")
            if thumb.is_file():
                st.markdown("**Original unannotated evidence frame**")
                st.image(str(thumb),caption="Actual source frame — not proof of a violation.",use_container_width=True)
            st.markdown("#### Relevant model observations")
            observation=(a.get("visual_reasoning") or {}).get("observations") or {}
            st.write(observation.get("scene_summary") or "No visual scene interpretation is available.")
            events=(a.get("violation_assessment") or {}).get("candidates") or []
            if events:
                st.dataframe(events,use_container_width=True,hide_index=True)
            else:
                st.caption("No supported candidate events. This is not evidence that the recording contains no offense.")
            tracks=(a.get("object_tracking") or {}).get("tracks") or []
            st.caption(f"{len(tracks)} provisional tracking IDs; one vehicle may receive multiple IDs.")
        with inspector:
            st.markdown("#### AI processing stages")
            stage_status(st,"Vehicle tracking",a.get("object_tracking"))
            stage_status(st,"Driver speech",a.get("transcription"))
            stage_status(st,"Qwen2.5-VL",a.get("visual_reasoning"))
            stage_status(st,"Egyptian plate OCR",a.get("plate_recognition"))
            stage_status(st,"Potential violation review",a.get("violation_assessment"))
            if selected["status"] in ("ready","failed"):
                if st.button("Re-run AI analysis on this clip",use_container_width=True):
                    st.session_state.pending_work=jobs().submit(
                        lambda: api_request("POST",f"/incidents/{selected_id}/reanalyze",
                                            timeout=360).json())
                    st.rerun()
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
    st.warning("A configured API does not guarantee requests will succeed. Free endpoints may be rate-limited, discontinued, or unable to analyze a specific incident.")
    st.info("Community Cloud may put the app to sleep and its local database/videos can disappear across restarts. Use only authorized, non-sensitive recordings. No government verification or permanent evidence vault is included.")
