"""Free image vision diagnostics: no footage sent, no API token displayed."""
import base64
import json
import httpx
from services.api.vision_diagnostics import (
    catalog_diagnostics, test_free_image_inference as check_image,
    _free_image_models,
)


def model(slug, modalities=("text","image"), price="0", image_price="0"):
    return {"id":slug,"architecture":{"input_modalities":list(modalities)},
            "pricing":{"prompt":price,"completion":price,
                       "request":"0","image":image_price}}


def response(method,url,code,data):
    return httpx.Response(code,request=httpx.Request(method,url),json=data)


def test_catalog_finds_all_free_vision_models_not_just_qwen():
    items=[
      model("qwen/new:free"), model("nvidia/vision:free"),
      model("nvidia/text:free",("text",)),
      model("vendor/paid:free",price="0.001"),
      model("vendor/images-billed:free",image_price="0.003")]
    qwen,others=_free_image_models(items)
    assert qwen==["qwen/new:free"]
    assert others==["nvidia/vision:free"]


def test_catalog_public_access_ok_and_account_access_denied_are_distinct():
    seen=[]
    def get(url,**kwargs):
        seen.append((url,kwargs.get("headers")))
        if url.endswith("/models/user"):
            return response("GET",url,403,{"error":"management key needed"})
        return response("GET",url,200,{"data":[model("nvidia/vision:free")]})
    diag=catalog_diagnostics("secret-do-not-display",get=get)
    assert diag["public"]["status"]=="available"
    assert diag["public"]["free_image_other"]==["nvidia/vision:free"]
    assert diag["account"]["status"]=="error"
    assert diag["account"]["http_status"]==403
    assert "secret-do-not-display" not in str(diag)
    assert seen[1][1]=={"Authorization":"Bearer secret-do-not-display"}


def test_catalog_connection_error_is_not_reported_as_no_models():
    def get(url,**kwargs):
        raise httpx.ConnectError("connect refused")
    result=catalog_diagnostics("",get=get)
    assert result["public"]["status"]=="error"
    assert result["public"]["message"]=="Catalog request failed: ConnectError."
    assert result["account"]["status"]=="not_configured"


def test_empty_valid_catalog_is_not_transport_error():
    def get(url,**kwargs):
        return response("GET",url,200,{"data":[]})
    result=catalog_diagnostics("",get=get)
    assert result["public"]["status"]=="available"
    assert result["public"]["count_free_image"]==0


def test_generated_image_probe_contains_no_real_video_and_one_request_only():
    calls=[]
    def post(url,**kwargs):
        calls.append(kwargs)
        return response("POST",url,200,{
            "model":"nvidia/a-vision-model:free",
            "choices":[{"message":{"content":"red"}}]})
    result=check_image("a-secret-token",post=post)
    assert result["status"]=="success"
    assert result["model"]=="nvidia/a-vision-model:free"
    assert len(calls)==1
    payload=calls[0]["json"]
    assert payload["model"]=="openrouter/free"
    url=payload["messages"][0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",")[1]).startswith(b"\x89PNG")
    assert "a-secret-token" not in str(result)


def test_live_404_offers_account_routing_next_step_without_leak():
    def post(url,**kwargs):
        return response("POST",url,404,{"error":{"message":"not found","secret":"dont print"}})
    result=check_image("private-key-value",post=post)
    assert result["status"]=="error"
    assert result["http_status"]==404
    assert "privacy" in result["message"]
    assert "private-key-value" not in str(result)
    assert "dont print" not in str(result)


def test_cpu_probe_executes_both_real_model_interfaces_on_synthetic_image(monkeypatch):
    from services.api.vision_diagnostics import cpu_detector_readiness
    import subprocess
    monkeypatch.setenv("TE_CLOUD_VISION","1")
    visited=[]
    def fake_predict(kind,image):
        visited.append((kind,image.size))
        return []
    result=cpu_detector_readiness(
        predict=fake_predict,which=lambda _: "/usr/bin/tesseract",
        run=lambda *args,**kwargs: subprocess.CompletedProcess(
            args[0],0,"List of available languages:\neng\nara\n",""))
    assert visited == [("vehicle",(320,192)),("plate",(320,192))]
    assert result["vehicle"]["status"]=="ready"
    assert result["plate"]["status"]=="ready"
    assert result["arabic_ocr"]["status"]=="ready"


def test_cpu_probe_failure_does_not_leak_private_exception_message(monkeypatch):
    from services.api.vision_diagnostics import cpu_detector_readiness
    monkeypatch.setenv("TE_CLOUD_VISION","1")
    def fake_predict(kind,image):
        if kind=="vehicle":
            raise ValueError("token-to-keep-private")
        return []
    result=cpu_detector_readiness(predict=fake_predict,which=lambda _: None)
    assert result["vehicle"]=={"status":"failed","error_type":"ValueError"}
    assert result["plate"]["status"]=="ready"
    assert result["arabic_ocr"]["error_type"]=="TesseractNotInstalled"
    assert "token-to-keep-private" not in str(result)


def test_disabled_cpu_probe_does_not_load_models(monkeypatch):
    from services.api.vision_diagnostics import cpu_detector_readiness
    monkeypatch.setenv("TE_CLOUD_VISION","0")
    def forbidden(*args,**kwargs):
        raise AssertionError("disabled must not invoke any CPU detector")
    result=cpu_detector_readiness(predict=forbidden,which=forbidden,run=forbidden)
    assert {v["status"] for v in result.values()}=={"disabled"}


def test_no_key_does_not_trigger_network():
    result=check_image("   ",post=lambda *a,**k: (_ for _ in ()).throw(AssertionError()))
    assert result["status"]=="not_configured"
