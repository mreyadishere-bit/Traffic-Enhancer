import os
from services.api import qwen


def test_operator_configured_remote_qwen(monkeypatch, tmp_path):
    def stub_frames(original, folder, duration):
        file = folder / "sample.jpg"
        file.write_bytes(b"\xff\xd8\xff\xd9")
        return [(3.0, file)]

    calls = []
    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"choices": [{"message": {"content":
                '{"scene_summary":"Road with cars","potential_events":[],"uncertainty_notes":"No proof"}'}}]}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    import httpx
    monkeypatch.setattr(qwen, "_capture_samples", stub_frames)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("TE_ENABLE_QWEN", "1")
    monkeypatch.setenv("TE_QWEN_API_BASE", "https://authorized-vlm.example/v1")
    monkeypatch.setenv("TE_QWEN_API_KEY", "test-private-token")
    output = qwen.describe_video(tmp_path / "not-needed.mp4", 20, {"verbatim": "Take photo"})
    assert output["status"] == "completed", output
    assert output["observations"]["scene_summary"] == "Road with cars"
    assert output["observations"]["potential_events"] == []
    assert calls[0][0] == "https://authorized-vlm.example/v1/chat/completions"
    assert calls[0][1]["json"]["model"] == qwen.MODEL_DEFAULT
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-private-token"


def test_remote_api_refuses_insecure_nonlocal_http(monkeypatch, tmp_path):
    monkeypatch.setenv("TE_ENABLE_QWEN", "1")
    monkeypatch.setenv("TE_QWEN_API_BASE", "http://arbitrary-external-host/v1")
    out = qwen.describe_video(tmp_path / "unused.mp4", 20, {})
    assert out["status"] == "failed"
    assert "HTTPS" in out["note"]
