"""Free multimodal failover tests — no credit spending, no invented findings."""
import json
import httpx
import pytest
from services.api import qwen
from services.api.vision_routing import (
    no_cost_model,free_qwen_vision_options,request_free_vision,RoutingFailure,
)


def fake_response(code, model=None):
    request=httpx.Request("POST","https://openrouter.ai/api/v1/chat/completions")
    if code>=400:
        return httpx.Response(code,request=request,json={"error":{"message":"Model unavailable"}})
    return httpx.Response(200,request=request,json={
        "model":model or "nvidia/free-vision-backend:free",
        "choices":[{"message":{"content":json.dumps({
            "scene_summary":"Cars are visible in traffic",
            "potential_events":[],"uncertainty_notes":"Insufficient evidence"})}}]})


def test_catalog_rejects_paid_or_text_only_qwen():
    choices=[
      {"id":"qwen/qwen3.8-27b:free",
       "architecture":{"input_modalities":["text","image"]},
       "pricing":{"prompt":"0","completion":"0"}},
      {"id":"qwen/paid-vision","architecture":{"input_modalities":["image"]},
       "pricing":{"prompt":"0.1","completion":"0.2"}},
      {"id":"qwen/text-only:free","architecture":{"input_modalities":["text"]},
       "pricing":{"prompt":"0","completion":"0"}},
    ]
    assert free_qwen_vision_options(choices)==["qwen/qwen3.8-27b:free"]


def test_qwen_404_then_free_vision_router_with_actual_model():
    calls=[]
    def post(url,**kwargs):
        calls.append(kwargs["json"]["model"])
        return fake_response(404) if len(calls)==1 else fake_response(200)
    def get(url,**kwargs):
        request=httpx.Request("GET",url)
        return httpx.Response(200,request=request,json={"data":[]})
    result,selected,tried=request_free_vision(
       "https://openrouter.ai/api/v1/chat/completions",
       {"Authorization":"Bearer test"},[{"type":"text","text":"test"},
       {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,AA=="}}],
       "qwen/qwen3.8-27b:free",post=post,get=get)
    assert calls==["qwen/qwen3.8-27b:free","openrouter/free"]
    assert result.json()["model"]=="nvidia/free-vision-backend:free"
    assert selected=="openrouter/free"
    assert tried==calls


def test_qwen_404_then_other_catalog_qwen_is_preferred():
    calls=[]
    def post(url,**kwargs):
        name=kwargs["json"]["model"]
        calls.append(name)
        return fake_response(404) if len(calls)==1 else fake_response(200,"qwen/new-qwen-vl:free")
    def get(url,**kwargs):
        return httpx.Response(200,request=httpx.Request("GET",url),json={"data":[{
          "id":"qwen/new-qwen-vl:free",
          "architecture":{"input_modalities":["text","image"]},
          "pricing":{"prompt":"0","completion":"0"}}]})
    _,selected,tried=request_free_vision(
      "https://openrouter.ai/api/v1/chat/completions",
      {},[],"qwen/retired:free",post=post,get=get)
    assert selected=="qwen/new-qwen-vl:free"
    assert calls==["qwen/retired:free","qwen/new-qwen-vl:free"]


def test_401_must_not_retry_other_providers():
    calls=[]
    def post(url,**kwargs):
        calls.append(1)
        return fake_response(401)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        request_free_vision("https://openrouter.ai/api/v1/chat/completions",
                            {},[],"qwen/qwen3.8-27b:free",post=post)
    assert exc.value.response.status_code==401
    assert len(calls)==1


def test_unavailable_free_router_fails_without_fake_violation():
    calls=[]
    def post(url,**kwargs):
        calls.append(kwargs["json"]["model"])
        return fake_response(404)
    def get(url,**kwargs):
        raise httpx.ConnectError("offline")
    with pytest.raises(RoutingFailure) as exc:
        request_free_vision("https://openrouter.ai/api/v1/chat/completions",
                            {},[],"qwen/qwen3.8-27b:free",post=post,get=get)
    assert calls==["qwen/qwen3.8-27b:free","openrouter/free"]
    assert exc.value.status_code==404


def test_paid_model_is_never_attempted():
    with pytest.raises(ValueError,match="non-free"):
        request_free_vision("https://openrouter.ai/api/v1/chat/completions",
                            {},[],"qwen/qwen3.8-27b")


def test_qwen_full_response_identifies_real_free_router_model(monkeypatch,tmp_path):
    def frames(source,folder,duration):
        file=folder/"frame.jpg"
        file.write_bytes(b"\xff\xd8\xff\xd9")
        return [(3.0,file)]
    calls=[]
    def fake_post(url,**kwargs):
        calls.append(kwargs["json"]["model"])
        return fake_response(404) if len(calls)==1 else fake_response(200)
    def fake_get(url,**kwargs):
        return httpx.Response(200,request=httpx.Request("GET",url),json={"data":[]})
    monkeypatch.setattr(qwen,"_capture_samples",frames)
    monkeypatch.setattr(httpx,"post",fake_post)
    monkeypatch.setattr(httpx,"get",fake_get)
    monkeypatch.setenv("TE_ENABLE_QWEN","1")
    monkeypatch.setenv("TE_QWEN_API_KEY","ci-redacted-value")
    monkeypatch.setenv("TE_QWEN_API_BASE","https://openrouter.ai/api/v1")
    monkeypatch.setenv("TE_QWEN_MODEL","qwen/qwen3.8-27b:free")
    output=qwen.describe_video(tmp_path/"mock.mp4",10,{"verbatim":"Test"})
    assert output["status"]=="completed",output
    assert output["model"]=="nvidia/free-vision-backend:free"
    assert output["requested_model"]=="qwen/qwen3.8-27b:free"
    assert output["observations"]["potential_events"]==[]
    assert output["routing"]=="OpenRouter free multimodal router"
    assert "ci-redacted-value" not in str(output)
