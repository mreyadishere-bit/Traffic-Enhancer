"""Safe, actionable provider API credential diagnostics for cloud demos.

No API key, token fragment, response body, or remote URL with secrets is returned
to Streamlit users. 401 means authentication failed; it is not an AI result.
"""
import os
import httpx

PROVIDERS = {
    "OpenRouter": ("TE_QWEN_API_KEY", "https://openrouter.ai/api/v1/key"),
    "Groq": ("TE_GROQ_API_KEY", "https://api.groq.com/openai/v1/models"),
}


def provider_failure(provider: str, error: Exception) -> str:
    names = {"OpenRouter": "TE_QWEN_API_KEY", "Groq": "TE_GROQ_API_KEY"}
    variable = names.get(provider, "provider API key")
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        if code == 401:
            return (f"{provider} HTTP 401: invalid or revoked API credential. Replace "
                    f"{variable} in Streamlit Cloud > App Settings > Secrets, save, "
                    "reboot the app, and re-run this clip.")
        if code == 403:
            return (f"{provider} HTTP 403: API access is forbidden for this key. "
                    f"Check provider permissions and {variable}.")
        if code == 429:
            return (f"{provider} HTTP 429: rate limit reached. Try again after "
                    "the provider limit resets; do not continuously retry.")
        if code in (402,):
            return f"{provider} HTTP 402: key/account has an insufficient credit allowance."
        if code in (404, 422):
            return (f"{provider} HTTP {code}: endpoint or model could be unavailable. "
                    "Check the configured model ID.")
        return f"{provider} HTTP {code}: inference request rejected. Check provider status."
    if isinstance(error, httpx.TimeoutException):
        return f"{provider} request timed out. Try a short clip if the service is available."
    return f"{provider} {type(error).__name__}: request failed; review provider settings."


def check_provider_credentials(provider: str) -> dict:
    """Minimal GET-only authentication check; never sends video/audio or triggers AI."""
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    key_name, url = PROVIDERS[provider]
    key = os.environ.get(key_name, "").strip()
    if not key:
        return {"status": "not_configured", "message": f"Set {key_name} in Streamlit Secrets."}
    try:
        response = httpx.get(url, headers={"Authorization": "Bearer " + key},
                             timeout=httpx.Timeout(12, connect=6), follow_redirects=False)
        response.raise_for_status()
        return {"status": "valid", "message": f"{provider} authenticated successfully. "
                "This does not confirm free model capacity or AI accuracy."}
    except httpx.HTTPError as exc:
        return {"status": "invalid" if isinstance(exc,httpx.HTTPStatusError) and
                exc.response.status_code in (401,403) else "error",
                "message": provider_failure(provider,exc)}
