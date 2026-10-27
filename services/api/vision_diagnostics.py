"""OpenRouter diagnostics from actual catalog metadata and a harmless image probe.

No road footage, real images or credentials are ever returned to the UI.
Public /models and authenticated /models/user give different answers. A
successful catalog query alone does NOT verify actual inference access.
"""
from __future__ import annotations

import base64
import io

import httpx
from PIL import Image, ImageDraw

from .vision_routing import FREE_ROUTER, OPENROUTER_BASE, _free_price


def _free_image_models(models: list) -> tuple[list[str], list[str]]:
    qwen, other = [], []
    if not isinstance(models, list):
        return qwen, other
    for item in models:
        if not isinstance(item, dict):
            continue
        slug = item.get("id")
        arch = item.get("architecture") or {}
        modalities = arch.get("input_modalities") or item.get("input_modalities") or []
        if (not isinstance(slug,str) or not slug.endswith(":free")
                or "image" not in modalities or not _free_price(item)):
            continue
        price = item.get("pricing") or {}
        # Some models charge for image or request, even if token prices are 0.
        try:
            if any(float(price.get(cost,"0")) > 0 for cost in ("image","request")):
                continue
        except (TypeError,ValueError):
            continue
        (qwen if slug.startswith("qwen/") else other).append(slug)
    return sorted(set(qwen)), sorted(set(other))


def _get_catalog(url: str, *, get=None, headers=None) -> dict:
    if get is None:
        get = httpx.get
    try:
        opts={"timeout":httpx.Timeout(18,connect=7)}
        if headers:
            opts["headers"]=headers
        response=get(url,**opts)
        response.raise_for_status()
        data=response.json()
        models=data.get("data")
        if not isinstance(models,list):
            raise ValueError("OpenRouter did not return a model collection")
        qwen, other=_free_image_models(models)
        return {"status":"available","total_models":len(models),
                "free_image_qwen":qwen[:12],"free_image_other":other[:16],
                "count_free_image":len(qwen)+len(other)}
    except httpx.HTTPStatusError as exc:
        return {"status":"error","http_status":exc.response.status_code,
                "message":f"Model listing responded HTTP {exc.response.status_code}."}
    except (httpx.HTTPError,ValueError,TypeError,AttributeError) as exc:
        return {"status":"error","message":f"Catalog request failed: {type(exc).__name__}."}


def catalog_diagnostics(key: str = "", *, get=None) -> dict:
    public=_get_catalog(OPENROUTER_BASE+"/models?input_modalities=image",get=get)
    result={"public":public,"account":{"status":"not_configured"}}
    if key.strip():
        # Only send keys to OpenRouter official host and never display them.
        result["account"]=_get_catalog(OPENROUTER_BASE+"/models/user",
                                       get=get,headers={"Authorization":"Bearer "+key.strip()})
    result["router_model"]=FREE_ROUTER
    return result


def _synthetic_png() -> str:
    """Tiny non-sensitive synthetic probe, never sourced from uploaded footage."""
    image=Image.new("RGB",(40,40),(250,250,250))
    pen=ImageDraw.Draw(image)
    pen.rectangle((10,10,31,31),outline=(10,48,120),width=3)
    pen.line((10,10,31,31),fill=(180,0,0),width=2)
    buffer=io.BytesIO()
    image.save(buffer,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode("ascii")


def test_free_image_inference(key: str, *, post=None) -> dict:
    """One explicit click = at most one actual free-model inference request."""
    if not key.strip():
        return {"status":"not_configured",
                "message":"TE_QWEN_API_KEY has not been configured in Streamlit Secrets."}
    if post is None:
        post=httpx.post
    try:
        response=post(
            OPENROUTER_BASE+"/chat/completions",
            headers={"Authorization":"Bearer "+key.strip(),
                     "Content-Type":"application/json"},
            json={"model":FREE_ROUTER,
                  "messages":[{"role":"user","content":[
                      {"type":"text","text":"This is a connectivity test. Reply with the color of the diagonal line in the square, in one word."},
                      {"type":"image_url","image_url":{"url":_synthetic_png()}}
                  ]}],
                  "max_tokens":30,
                  "temperature":0},
            timeout=httpx.Timeout(55,connect=8)
        )
        response.raise_for_status()
        data=response.json()
        chosen=str(data.get("model") or "Unreported by provider")[:110]
        choices=data.get("choices") or []
        if not choices:
            return {"status":"error","message":"Provider returned no completion choices."}
        return {"status":"success",
                "model":chosen,
                "message":"Free image inference accepted. This does not validate the model's road-safety accuracy."}
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        descriptions={
            401:"Invalid or revoked OpenRouter key; update Streamlit Secrets.",
            402:"This account cannot complete the request without credit allowance.",
            403:"The account or privacy/provider settings forbid this inference.",
            404:"No compatible free image provider was routed for this account/request. Review OpenRouter provider and privacy preferences.",
            429:"Free-model rate limit reached; retry when the limit resets.",
        }
        return {"status":"error","http_status":code,
                "message":descriptions.get(code,f"OpenRouter returned HTTP {code}.")}
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        return {"status":"error","message":f"Inference probe failed: {type(exc).__name__}."}
