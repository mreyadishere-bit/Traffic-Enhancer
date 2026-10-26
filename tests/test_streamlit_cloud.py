"""Passwordless Streamlit smoke and browser session isolation tests."""
import json
from datetime import datetime, timezone
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"

def prepare(tmp_path, monkeypatch):
    from services.api import main as backend
    monkeypatch.setenv("TE_ENV", "production")
    monkeypatch.setenv("TE_API_KEY", "ci-internal-key-123456789abcdef")
    monkeypatch.setattr(backend, "KEY", "ci-internal-key-123456789abcdef")
    monkeypatch.setattr(backend, "DATA", tmp_path)
    monkeypatch.setattr(backend, "DB", tmp_path / "traffic.db")
    monkeypatch.setattr(backend, "EVIDENCE", tmp_path / "evidence")
    monkeypatch.setattr(backend, "DERIVED", tmp_path / "derived")
    monkeypatch.delenv("TE_QWEN_API_KEY", raising=False)
    monkeypatch.delenv("TE_GROQ_API_KEY", raising=False)
    backend.initialize()
    return backend

def test_opens_without_operator_password(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert not app.text_input
    assert app.radio and "Overview" in app.radio[0].options
    assert len(app.metric) >= 4
    assert list(app.session_state["te_case_ids"]) == []

def test_does_not_enumerate_other_browser_cases(tmp_path, monkeypatch):
    backend = prepare(tmp_path, monkeypatch)
    case_id = "a" * 32
    with backend.connect() as db:
        db.execute("""INSERT INTO incidents
            (id, filename, created_at, sha256, bytes, duration, video_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, "other-session-case.mp4", datetime.now(timezone.utc).isoformat(),
             "f" * 64, 128, 2.0, json.dumps({"width": 320, "height": 180}), "ready"))
    visitor = AppTest.from_file(APP, default_timeout=30).run()
    assert not visitor.exception, [str(x.message) for x in visitor.exception]
    assert visitor.metric[0].value == "0"
    assert not any("other-session-case" in str(x.value) for x in visitor.markdown)
    visitor.session_state["te_case_ids"] = [case_id]
    visitor.run()
    assert not visitor.exception, [str(x.message) for x in visitor.exception]
    assert visitor.metric[0].value == "1"

def test_visitors_do_not_need_any_password_secret(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    monkeypatch.delenv("TE_API_KEY", raising=False)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert not app.text_input
    assert app.radio and "Overview" in app.radio[0].options



def test_new_analysis_explains_trim_even_before_upload(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception, [str(e.message) for e in app.exception]
    app.radio[0].set_value("New analysis").run()
    assert not app.exception, [str(e.message) for e in app.exception]
    labels = [str(x.value) for x in app.markdown]
    assert any("Optional clip trimming" in x for x in labels)
    assert any("full" in str(x.message).lower() or "Choose a video" in str(x.message) for x in app.info)
