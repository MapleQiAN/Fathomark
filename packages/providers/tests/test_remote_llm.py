import io
import json
from urllib.error import HTTPError

import pytest
from fathomark_providers import LLMRequest, ProviderError
from fathomark_providers.remote_llm import (
    AnthropicProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    _UrllibJsonTransport,
)


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class _Transport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, *, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def test_urllib_transport_posts_json_and_parses_response(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(b'{"ok": true}')

    monkeypatch.setattr("fathomark_providers.remote_llm.urlopen", fake_urlopen)

    result = _UrllibJsonTransport().post_json(
        "https://provider.test/v1/chat",
        headers={"Authorization": "Bearer redacted"},
        payload={"prompt": "hello"},
        timeout_seconds=12.5,
    )

    assert result == {"ok": True}
    assert captured["timeout"] == 12.5
    assert captured["request"].full_url == "https://provider.test/v1/chat"
    assert captured["request"].get_method() == "POST"
    assert json.loads(captured["request"].data) == {"prompt": "hello"}
    assert captured["request"].headers["Authorization"] == "Bearer redacted"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_urllib_transport_marks_rate_limit_and_server_errors_retryable(
    monkeypatch, status
):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            status,
            "failure",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"provider down"}}'),
        )

    monkeypatch.setattr("fathomark_providers.remote_llm.urlopen", fake_urlopen)

    with pytest.raises(ProviderError, match="provider down") as caught:
        _UrllibJsonTransport().post_json(
            "https://provider.test/v1/chat",
            headers={},
            payload={},
            timeout_seconds=1,
        )

    assert caught.value.retriable is True


def test_urllib_transport_marks_authentication_errors_non_retriable(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("fathomark_providers.remote_llm.urlopen", fake_urlopen)

    with pytest.raises(ProviderError, match="HTTP 401") as caught:
        _UrllibJsonTransport().post_json(
            "https://provider.test/v1/chat",
            headers={},
            payload={},
            timeout_seconds=1,
        )

    assert caught.value.retriable is False


def test_urllib_transport_rejects_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "fathomark_providers.remote_llm.urlopen",
        lambda request, timeout: _Response(b"not-json"),
    )

    with pytest.raises(ProviderError, match="invalid JSON") as caught:
        _UrllibJsonTransport().post_json(
            "https://provider.test/v1/chat",
            headers={},
            payload={},
            timeout_seconds=1,
        )

    assert caught.value.retriable is False


def test_llm_request_fixture_for_adapter_tests():
    assert LLMRequest(prompt="hello", schema_name="factor_proposals").max_tokens == 2048


def test_openai_provider_builds_chat_request_and_maps_usage():
    transport = _Transport(
        {
            "model": "gpt-test",
            "choices": [{"message": {"content": '{"factor": "moat"}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }
    )
    provider = OpenAIProvider(
        model="gpt-test",
        api_key="secret-key",
        endpoint="https://example.test/chat",
        transport=transport,
        timeout_seconds=4,
    )

    result = provider.complete(
        LLMRequest(prompt="Return JSON", schema_name="factor_proposals", max_tokens=99)
    )

    assert result.text == '{"factor": "moat"}'
    assert result.model == "gpt-test"
    assert (result.prompt_tokens, result.completion_tokens) == (11, 7)
    call = transport.calls[0]
    assert call["url"] == "https://example.test/chat"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["payload"] == {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "Return JSON"}],
        "max_tokens": 99,
        "temperature": 0,
    }


def test_openai_provider_requires_key_without_network_call(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transport = _Transport({})
    provider = OpenAIProvider(model="gpt-test", transport=transport)

    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        provider.complete(LLMRequest(prompt="p", schema_name="s"))

    assert transport.calls == []


def test_openai_compatible_provider_allows_keyless_local_endpoint():
    transport = _Transport(
        {
            "choices": [{"message": {"content": "local response"}}],
        }
    )
    provider = OpenAICompatibleProvider(
        endpoint="http://localhost:8000/v1/chat/completions",
        model="local-model",
        transport=transport,
    )

    result = provider.complete(LLMRequest(prompt="p", schema_name="s"))

    assert result.text == "local response"
    assert "Authorization" not in transport.calls[0]["headers"]


def test_openai_provider_rejects_empty_or_malformed_content():
    transport = _Transport({"choices": [{"message": {"content": []}}]})
    provider = OpenAIProvider(model="gpt-test", api_key="secret", transport=transport)

    with pytest.raises(ProviderError, match="empty content"):
        provider.complete(LLMRequest(prompt="p", schema_name="s"))


def test_provider_error_does_not_echo_api_key():
    secret = "secret-key"
    transport = _Transport({"error": {"message": f"invalid key {secret}"}})
    provider = OpenAIProvider(model="gpt-test", api_key=secret, transport=transport)

    with pytest.raises(ProviderError) as caught:
        provider.complete(LLMRequest(prompt="p", schema_name="s"))

    assert secret not in str(caught.value)
    assert "[redacted]" in str(caught.value)


def test_anthropic_provider_builds_messages_request_and_maps_usage():
    transport = _Transport(
        {
            "model": "claude-test",
            "content": [{"type": "text", "text": "anthropic response"}],
            "usage": {"input_tokens": 13, "output_tokens": 5},
        }
    )
    provider = AnthropicProvider(
        model="claude-test",
        api_key="anthropic-secret",
        endpoint="https://example.test/messages",
        transport=transport,
    )

    result = provider.complete(
        LLMRequest(prompt="prompt", schema_name="s", max_tokens=88)
    )

    assert result.text == "anthropic response"
    assert (result.prompt_tokens, result.completion_tokens) == (13, 5)
    call = transport.calls[0]
    assert call["headers"]["x-api-key"] == "anthropic-secret"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["payload"] == {
        "model": "claude-test",
        "max_tokens": 88,
        "messages": [{"role": "user", "content": "prompt"}],
    }


def test_anthropic_provider_requires_key_without_network_call(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    transport = _Transport({})
    provider = AnthropicProvider(model="claude-test", transport=transport)

    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        provider.complete(LLMRequest(prompt="p", schema_name="s"))

    assert transport.calls == []
