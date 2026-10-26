"""Streamlit Cloud smoke tests: secure gate and authenticated API integration.

Run separately from tests/test_api.py because the latter patches TE_API_KEY
globally during module import, whereas Streamlit uses its own process keys.
"""
import os
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'streamlit_app.py'

from streamlit.testing.v1 import AppTest


def test_operator_gate_and_real_api_on_private_cloud(tmp_path, monkeypatch):
    monkeypatch.setenv("TE_API_KEY","ci-streamlit-long-private-test-key")
    # Other API tests import the module at collection time with their own key.
    # Align this test's in-process TestClient with this Cloud instance's secret.
    from services.api import main as backend
    monkeypatch.setattr(backend, "KEY", "ci-streamlit-long-private-test-key")
    monkeypatch.setenv("TE_DATA_DIR",str(tmp_path/"app"))
    monkeypatch.delenv("TE_QWEN_API_KEY",raising=False)
    monkeypatch.delenv("TE_GROQ_API_KEY",raising=False)
    app = AppTest.from_file(APP,default_timeout=30)
    app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert len(app.text_input)>=1
    assert "Operator password" in str(app.text_input[0].label)
    # There must be no video/case workspace before login.
    assert not any("Incident library" in str(x.label) for x in app.radio)
    app.session_state["te_logged_in"]=True
    app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert len(app.radio)>=1
    assert "Overview" in app.radio[0].options
    assert len(app.metric)>=4


def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("TE_API_KEY",raising=False)
    app=AppTest.from_file(APP,default_timeout=30)
    app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert any("locked" in str(x.value).lower() for x in app.error)
    assert not app.radio
