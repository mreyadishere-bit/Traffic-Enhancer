"""Guard against silent HTTP 200 replies with no final visual interpretation."""
import httpx
from services.api.vision_reply import inspect_chat_reply
from services.api.vision_routing import RoutingFailure, request_free_vision
from services.api import qwen
from services.api.vision_diagnostics import test_free_image_inference as check_image
import pytest


URL="https://openrouter.ai/api/v1/chat/completions"


def result(status, data):
    return httpx.Response(status,request=httpx.Request("POST",URL),json=data)


def readable(model="vendor/free-vision:free",content=None):
    if content is None:
        content='{"scene_summary":"Cars visible","potential_events":[],"uncertainty_notes":"Unverified"}'
    return result(200,{"model":model,"choices":[{"message":{"content":content},"finish_reason":"stop"}]})


def test_structured_multimodal_output_text_blocks():
    assert inspect_chat_reply({
        "choices":[{"message":{"content":[{"type":"text","text":"{\"scene_summary\":"},
                      {"type":"output_text","text":{"value":"\"Road\"}"}}]}}]
    })["text"]=='{"scene_summary":\n"Road"}'


def test_reasoning_only_http_200_is_not_success():
    diagnosis=inspect_chat_reply({"choices":[{"message":{
        "content":None,"reasoning":"private reasoning should not be displayed"
    },"finish_reason":"length"}]})
    assert diagnosis["status"]=="retry"
    assert diagnosis["reason"]=="output_token_limit"
    assert "private reasoning" not in str({k:v for k,v in diagnosis.items()
                                             if k!="text"})


def test_provider_error_in_200_does_not_retry_or_leak_provider_message():
    calls=[]
    def post(*args,**kwargs):
        calls.append(kwargs["json"]["model"])
        return result(200,{"error":{"message":"secret api token DO NOT PRINT"}})
    with pytest.raises(RoutingFailure) as exc:
        request_free_vision(URL,{},[], "qwen/qwen3.8-27b:free",
                            post=post,inspect=lambda response: inspect_chat_reply(response.json()))
    assert exc.value.reason=="provider_error_in_success_reply"
    assert calls==["qwen/qwen3.8-27b:free"]
    assert "secret" not in str(exc.value)


def test_qwen_empty_200_falls_back_to_free_alternative():
    calls=[]
    def post(*args,**kwargs):
        model=kwargs["json"]["model"]
        calls.append(model)
        if len(calls)==1:
            return result(200,{"choices":[{"message":{"content":None},
                                            "finish_reason":"length"}]})
        return readable(model)
    def get(url,**kwargs):
        return httpx.Response(200,request=httpx.Request("GET",url),
            json={"data":[{"id":"nvidia/nemotron-3.5-super-vl:free",
                           "architecture":{"input_modalities":["text","image"]},
                           "pricing":{"prompt":"0","completion":"0","request":"0","image":"0"}}]})
    reply,selected,tried=request_free_vision(
        URL,{},[], "qwen/qwen3.8-27b:free",
        post=post,get=get,inspect=lambda response:inspect_chat_reply(response.json()))
    assert selected=="nvidia/nemotron-3.5-super-vl:free"
    assert tried==calls
    assert len(calls)==2
    assert kwargs_is_safe_model(reply)


def kwargs_is_safe_model(reply):
    return reply.json().get("model")=="nvidia/nemotron-3.5-super-vl:free"


def test_200_empty_across_all_free_models_reports_unparseable(monkeypatch,tmp_path):
    monkeypatch.setenv("TE_ENABLE_QWEN","1")
    monkeypatch.setenv("TE_QWEN_API_BASE","https://openrouter.ai/api/v1")
    monkeypatch.setenv("TE_QWEN_API_KEY","private-do-not-expose")
    monkeypatch.setenv("TE_QWEN_MODEL","qwen/qwen3.8-27b:free")
    def frames(source,folder,duration):
        image=folder/"source.jpg"
        image.write_bytes(b"fake-jpeg")
        return [(2.0,image)]
    monkeypatch.setattr(qwen,"_capture_samples",frames)
    monkeypatch.setattr(httpx,"post",lambda *a,**k:result(200,{
        "choices":[{"message":{"content":None},"finish_reason":"length"}]}))
    monkeypatch.setattr(httpx,"get",lambda url,**k:httpx.Response(
        200,request=httpx.Request("GET",url),json={"data":[]}))
    analysis=qwen.describe_video(tmp_path/"input.mp4",10,{"verbatim":"take photo"})
    assert analysis["status"]=="unparseable"
    assert analysis["diagnostic_code"]=="output_token_limit"
    assert analysis["attempted_models"]==["qwen/qwen3.8-27b:free","openrouter/free"]
    assert "private-do-not-expose" not in str(analysis)
    assert analysis["observations"] is None


def test_remote_list_content_is_parsed_without_generic_value_error(monkeypatch,tmp_path):
    monkeypatch.setenv("TE_ENABLE_QWEN","1")
    monkeypatch.setenv("TE_QWEN_API_BASE","https://openrouter.ai/api/v1")
    monkeypatch.setenv("TE_QWEN_API_KEY","private")
    monkeypatch.setenv("TE_QWEN_MODEL","openrouter/free")
    def frames(source,folder,duration):
        image=folder/"source.jpg"
        image.write_bytes(b"fake-jpeg")
        return [(2.0,image)]
    monkeypatch.setattr(qwen,"_capture_samples",frames)
    monkeypatch.setattr(httpx,"post",lambda *a,**k:readable(
        "vendor/free-vision:free",[{"type":"text","text":
            '{"scene_summary":"Cars on road","potential_events":[],"uncertainty_notes":"none"}'}]))
    analysis=qwen.describe_video(tmp_path/"input.mp4",10,{})
    assert analysis["status"]=="completed",analysis
    assert analysis["model"]=="vendor/free-vision:free"
    assert analysis["observations"]["scene_summary"]=="Cars on road"


def test_diagnostic_does_not_claim_success_on_empty_200():
    response=lambda *a,**k:result(200,{
        "choices":[{"message":{"content":None},"finish_reason":"length"}]})
    verdict=check_image("secret-key",post=response)
    assert verdict["status"]=="error"
    assert verdict["diagnostic_code"]=="output_token_limit"
    assert "secret-key" not in str(verdict)
