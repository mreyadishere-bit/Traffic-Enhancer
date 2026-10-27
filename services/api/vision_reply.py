"""Safely normalize real OpenAI-compatible chat completion responses.

Some free multimodal providers return content blocks or no final text despite
HTTP 200 (for example, a reasoning-only completion that exhausted its budget).
Never treat empty text, provider errors, or refusal as evidence of a violation.
Never copy untrusted provider error messages into the case report.
"""
from __future__ import annotations


def _text_from_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content[:32]:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in (
                    "text", "output_text"):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif isinstance(text, dict) and isinstance(text.get("value"), str):
                    parts.append(text["value"])
        return "\n".join(parts).strip()
    return ""


def inspect_chat_reply(data) -> dict:
    """Return normalized text plus a non-secret, machine-readable diagnosis.

    'retry' means another no-cost provider may improve the outcome; 'stop'
    means do not bypass a provider refusal or an error reported in HTTP 200.
    """
    if not isinstance(data, dict):
        return {"status": "stop", "reason": "invalid_response_shape", "text": ""}
    if data.get("error"):
        return {"status": "stop", "reason": "provider_error_in_success_reply",
                "text": ""}
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {"status": "retry", "reason": "no_completion_choices", "text": ""}
    first = choices[0]
    message = first.get("message")
    if not isinstance(message, dict):
        return {"status": "retry", "reason": "missing_message", "text": ""}
    text = _text_from_content(message.get("content"))
    if text:
        return {"status": "ok", "reason": None, "text": text}
    if message.get("refusal"):
        return {"status": "stop", "reason": "model_refused", "text": ""}
    reason = first.get("finish_reason")
    if reason == "length":
        code = "output_token_limit"
    elif message.get("reasoning") or message.get("reasoning_details"):
        code = "reasoning_without_answer"
    else:
        code = "empty_completion"
    return {"status": "retry", "reason": code, "text": ""}
