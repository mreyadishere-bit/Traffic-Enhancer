"""Provider credential checks and safe, actionable error messages."""
import os
import httpx
import pytest
from services.api.provider_status import provider_failure, check_provider_credentials


def error(status):
    request=httpx.Request("POST","https://api.example.test/video")
    response=httpx.Response(status,request=request)
    return httpx.HTTPStatusError("failure",request=request,response=response)


def test_401_messages_do_not_print_tokens(monkeypatch):
    monkeypatch.setenv("TE_QWEN_API_KEY","secret-must-never-show-123")
    monkeypatch.setenv("TE_GROQ_API_KEY","secret-must-never-show-456")
    for provider,var in [("OpenRouter","TE_QWEN_API_KEY"),("Groq","TE_GROQ_API_KEY")]:
        message=provider_failure(provider,error(401))
        assert var in message and "401" in message
        assert "secret-must-never-show" not in message
        assert "Streamlit Cloud" in message


@pytest.mark.parametrize("code", [402,403,404,429,503])
def test_status_code_messages_are_meaningful(code):
    message=provider_failure("OpenRouter",error(code))
    assert str(code) in message


def test_auth_probe_reads_provider_keys_and_does_not_send_video(monkeypatch):
    called=[]
    def fake_get(url, headers, timeout, follow_redirects):
        called.append((url,headers))
        return httpx.Response(200,request=httpx.Request("GET",url))
    monkeypatch.setattr(httpx,"get",fake_get)
    monkeypatch.setenv("TE_GROQ_API_KEY","ci-test-key")
    result=check_provider_credentials("Groq")
    assert result["status"]=="valid"
    assert called[0][0]=="https://api.groq.com/openai/v1/models"
    assert called[0][1]=={"Authorization":"Bearer ci-test-key"}


def test_failed_auth_probe_redacts_credentials(monkeypatch):
    monkeypatch.setenv("TE_QWEN_API_KEY","ci-other-secret")
    def fake_get(url,headers,timeout,follow_redirects):
        return httpx.Response(401,request=httpx.Request("GET",url))
    monkeypatch.setattr(httpx,"get",fake_get)
    check=check_provider_credentials("OpenRouter")
    assert check["status"]=="invalid"
    assert "TE_QWEN_API_KEY" in check["message"]
    assert "ci-other-secret" not in check["message"]


def test_missing_api_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("TE_GROQ_API_KEY",raising=False)
    assert check_provider_credentials("Groq")["status"]=="not_configured"
