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
        return float(price.get("prompt","1")) == 0 and float(price.get("completion","1")) == 0
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


def fetch_free_qwen_options(get=None) -> list[str]:
    """Best-effort public catalog read, no video or key is sent."""
    if get is None:
        get=httpx.get
    try:
        reply=get(OPENROUTER_BASE+"/models?input_modalities=image",
                  timeout=httpx.Timeout(12,connect=5))
        reply.raise_for_status()
        return free_qwen_vision_options(reply.json().get("data",[]))
    except (httpx.HTTPError,ValueError,KeyError,AttributeError):
        return []


class RoutingFailure(Exception):
    def __init__(self, status_code: int, tried: list[str]):
        self.status_code=status_code
        self.tried=tried
        super().__init__(f"OpenRouter HTTP {status_code} after available free visual models were tried.")


def request_free_vision(endpoint: str, headers: dict, content: list,
                        model: str, *, post=None, get=None):
    """Bounded fallback: max 1 preferred + 1 alternate Qwen + free router."""
    if post is None:
        post=httpx.post
    if not no_cost_model(model):
        raise ValueError("A non-free OpenRouter model is blocked in this free demo.")
    queue=[model]
    tried=[]
    while queue and len(tried)<3:
        current=queue.pop(0)
        if current in tried:
            continue
        tried.append(current)
        response=post(endpoint,headers=headers,
                      json={"model":current,"messages":[{"role":"user","content":content}],
                            "max_tokens":450,"temperature":0},
                      timeout=httpx.Timeout(180,connect=10))
        code=getattr(response,"status_code",200)
        if code==404:
            if current != FREE_ROUTER:
                if len(tried)==1:
                    options=fetch_free_qwen_options(get=get)
                    next_qwen=next((slug for slug in options
                                    if slug not in tried and slug!=FREE_ROUTER),None)
                    if next_qwen:
                        queue.append(next_qwen)
                if FREE_ROUTER not in queue and FREE_ROUTER not in tried:
                    queue.append(FREE_ROUTER)
            continue
        if code>=400:
            # Unauthorized, insufficient credit, forbidden and rate limits do
            # not trigger another request. This prevents unnecessary retries.
            response.raise_for_status()
        response.raise_for_status()
        return response,current,tried
    raise RoutingFailure(404,tried)
