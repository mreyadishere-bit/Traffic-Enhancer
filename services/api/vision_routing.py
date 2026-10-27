"""No-cost, vision-capable OpenRouter failover, with verifiable model identity.

The preferred Qwen model is tried first. Only an unavailable-model HTTP
404 triggers alternate Qwen free variants, then the documented
openrouter/free router (which may select a NON-QWEN model). Never silently
call a priced model, or use fallbacks to bypass authentication/rate limits.
"""
from __future__ import annotations

import httpx

FREE_ROUTER = "openrouter/free"
PREFERRED_QWEN = "qwen/qwen3.8-27b:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def no_cost_model(model: str) -> bool:
    return model == FREE_ROUTER or (model.endswith(":free") and "/" in model)


def _free_price(item: dict) -> bool:
    price = item.get("pricing") or {}
    try:
        return (all(float(price.get(k,"1")) == 0 for k in ("prompt","completion"))
                and all(float(price.get(k,"0")) == 0 for k in ("image","request")))
    except (TypeError, ValueError):
        return False


def free_qwen_vision_options(items) -> list[str]:
    """Ignore names alone; require free pricing and advertised image input."""
    matches=[]
    for item in items if isinstance(items,list) else []:
        if not isinstance(item,dict):
            continue
        slug=item.get("id","")
        modalities=((item.get("architecture") or {}).get("input_modalities") or
                    item.get("input_modalities") or [])
        if (isinstance(slug,str) and slug.startswith("qwen/")
                and slug.endswith(":free") and "image" in modalities
                and _free_price(item)):
            matches.append(slug)
    matches.sort(key=lambda s: (s!=PREFERRED_QWEN,s))
    return matches[:3]


def free_vision_options(items) -> list[str]:
    """Select ONLY catalog-confirmed zero-priced image-input model IDs.

    This is an *availability candidate*, not proof a given key is permitted to
    route to that model. Prefer Qwen when available, then general vision models.
    """
    choices=[]
    for item in items if isinstance(items,list) else []:
        if not isinstance(item,dict):
            continue
        slug=item.get("id")
        modalities=((item.get("architecture") or {}).get("input_modalities") or
                    item.get("input_modalities") or [])
        if (isinstance(slug,str) and slug.endswith(":free") and "/" in slug
                and "image" in modalities and _free_price(item)):
            choices.append(slug)
    choices=sorted(set(choices),key=lambda slug:(
        slug!=PREFERRED_QWEN,
        not slug.startswith("qwen/"),
        slug!="nvidia/nemotron-3.5-super-vl:free",
        slug))
    return choices[:24]


def fetch_free_vision_options(get=None) -> list[str]:
    """Best-effort public catalog read; no video, key or images are sent."""
    if get is None:
        get=httpx.get
    try:
        reply=get(OPENROUTER_BASE+"/models?input_modalities=image",
                  timeout=httpx.Timeout(12,connect=5))
        reply.raise_for_status()
        return free_vision_options(reply.json().get("data",[]))
    except (httpx.HTTPError,ValueError,KeyError,AttributeError,TypeError):
        return []


def fetch_free_qwen_options(get=None) -> list[str]:
    """Backward-compatible Qwen-only subset of the public free vision catalog."""
    return [slug for slug in fetch_free_vision_options(get=get)
            if slug.startswith("qwen/")][:3]


class RoutingFailure(Exception):
    def __init__(self, status_code: int, tried: list[str], reason: str = "unavailable"):
        self.status_code=status_code
        self.tried=tried
        self.reason=reason
        super().__init__(f"Free visual model routing failed: HTTP {status_code} ({reason}).")


def request_free_vision(endpoint: str, headers: dict, content: list,
                        model: str, *, post=None, get=None, inspect=None):
    """At most three FREE calls; retry 404 or empty 200 model responses only.

    An optional inspect(response) yields a sanitized {"status":"ok|retry|stop",
    "reason":"..."}; never retry on 401/402/403/429 or provider-declared error.
    """
    if post is None:
        post=httpx.post
    if not no_cost_model(model):
        raise ValueError("A non-free OpenRouter model is blocked in this free demo.")
    queue=[model]
    tried=[]
    last_reason="unavailable"
    last_code=404
    while queue and len(tried)<3:
        current=queue.pop(0)
        if current in tried:
            continue
        tried.append(current)
        response=post(endpoint,headers=headers,
                      json={"model":current,"messages":[{"role":"user","content":content}],
                            "max_tokens":900,"temperature":0},
                      timeout=httpx.Timeout(75,connect=8,read=70,write=30))
        code=getattr(response,"status_code",200)
        if code not in (200,404):
            # Do not bypass authorization, credits, provider refusals or limits.
            response.raise_for_status()
        if code==200:
            response.raise_for_status()
            verdict=inspect(response) if inspect is not None else {"status":"ok"}
            status=verdict.get("status","stop") if isinstance(verdict,dict) else "stop"
            if status=="ok":
                return response,current,tried
            last_code=200
            last_reason=str(verdict.get("reason","invalid_response"))[:70]
            if status!="retry":
                raise RoutingFailure(200,tried,last_reason)
        else:
            last_code=404
            last_reason="no_compatible_provider"
        if current != FREE_ROUTER:
            if len(tried)==1:
                options=fetch_free_vision_options(get=get)
                alternate=next((slug for slug in options
                                if slug not in tried and slug!=FREE_ROUTER),None)
                if alternate:
                    queue.append(alternate)
            if FREE_ROUTER not in queue and FREE_ROUTER not in tried:
                queue.append(FREE_ROUTER)
    raise RoutingFailure(last_code,tried,last_reason)
