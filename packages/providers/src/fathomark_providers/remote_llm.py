"""Dependency-free HTTP adapters for hosted and OpenAI-compatible LLMs."""

import json
import os
from collections.abc import Mapping
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fathomark_providers.llm import LLMRequest, LLMResponse, ProviderError


class JsonHttpTransport(Protocol):
    """Small seam that keeps provider tests fully offline."""

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> object: ...


def _error_detail(body: bytes, *, headers: Mapping[str, str]) -> str:
    try:
        parsed = json.loads(body.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            detail = error["message"]
        elif isinstance(parsed.get("message"), str):
            detail = parsed["message"]
        else:
            detail = "provider returned an error"
    else:
        detail = "provider returned an error"

    # Provider bodies are untrusted. Avoid echoing credential values if a
    # gateway accidentally reflects an Authorization or API-key header.
    for key, value in headers.items():
        if key.lower() in {"authorization", "x-api-key"} and value:
            secret = value.removeprefix("Bearer ")
            if secret:
                detail = detail.replace(secret, "[redacted]")
    return detail[:300]


class _UrllibJsonTransport:
    """POST JSON using only the Python standard library."""

    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> object:
        request_headers = {"Accept": "application/json", **headers}
        request_headers.setdefault("Content-Type", "application/json")
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            body = exc.read()
            detail = _error_detail(body, headers=request_headers)
            raise ProviderError(
                f"HTTP {exc.code}: {detail}",
                retriable=exc.code == 429 or exc.code >= 500,
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError(
                f"network error: {type(exc).__name__}", retriable=True
            ) from None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(
                "provider returned invalid JSON", retriable=False
            ) from exc


def _text_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = [
            item.get("text", "")
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "".join(chunks)
    return ""


def _usage_int(usage: object, *names: str) -> int:
    if not isinstance(usage, dict):
        return 0
    for name in names:
        value = usage.get(name)
        if isinstance(value, int) and value >= 0:
            return value
    return 0


def _parse_openai_response(
    payload: object, *, fallback_model: str, secret: str | None = None
) -> LLMResponse:
    if not isinstance(payload, dict):
        raise ProviderError("provider returned malformed response", retriable=False)
    if "error" in payload:
        _raise_api_error(payload, secret=secret)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("provider response has no choices", retriable=False)
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError("provider response has malformed choice", retriable=False)
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    text = _text_content(content)
    if not text.strip():
        raise ProviderError("provider response has empty content", retriable=False)
    model = payload.get("model")
    return LLMResponse(
        text=text,
        model=model if isinstance(model, str) and model else fallback_model,
        prompt_tokens=_usage_int(payload.get("usage"), "prompt_tokens", "input_tokens"),
        completion_tokens=_usage_int(
            payload.get("usage"), "completion_tokens", "output_tokens"
        ),
    )


def _raise_api_error(payload: dict[str, object], *, secret: str | None = None) -> None:
    error = payload.get("error")
    message = "provider request failed"
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        message = error["message"][:300]
    if secret:
        message = message.replace(secret, "[redacted]")
    raise ProviderError(message, retriable=False)


class _OpenAIChatProvider:
    _endpoint: str
    _api_key: str | None
    _model: str
    _transport: JsonHttpTransport
    _timeout_seconds: float
    _require_credentials: bool

    def _complete_openai(self, request: LLMRequest) -> LLMResponse:
        if self._require_credentials:
            api_key = self._api_key
            if not api_key:
                raise ProviderError(
                    "missing credentials: set OPENAI_API_KEY", retriable=False
                )
        else:
            api_key = self._api_key
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": 0,
        }
        response = self._transport.post_json(
            self._endpoint,
            headers=headers,
            payload=payload,
            timeout_seconds=self._timeout_seconds,
        )
        return _parse_openai_response(
            response, fallback_model=self._model, secret=api_key
        )


class OpenAIProvider(_OpenAIChatProvider):
    """OpenAI Chat Completions adapter."""

    name = "openai"
    version = "1.0.0"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        transport: JsonHttpTransport | None = None,
        timeout_seconds: float = 30.0,
    ):
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._endpoint = endpoint
        self._transport = transport or _UrllibJsonTransport()
        self._timeout_seconds = timeout_seconds
        self._require_credentials = True

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self._complete_openai(request)


class OpenAICompatibleProvider(_OpenAIChatProvider):
    """Adapter for servers exposing an OpenAI-compatible endpoint."""

    name = "openai-compatible"
    version = "1.0.0"

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        transport: JsonHttpTransport | None = None,
        timeout_seconds: float = 30.0,
    ):
        self._model = model
        self._api_key = api_key
        self._endpoint = endpoint
        self._transport = transport or _UrllibJsonTransport()
        self._timeout_seconds = timeout_seconds
        self._require_credentials = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self._complete_openai(request)


class AnthropicProvider:
    """Anthropic Messages API adapter."""

    name = "anthropic"
    version = "1.0.0"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        endpoint: str = "https://api.anthropic.com/v1/messages",
        transport: JsonHttpTransport | None = None,
        timeout_seconds: float = 30.0,
    ):
        self._model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._endpoint = endpoint
        self._transport = transport or _UrllibJsonTransport()
        self._timeout_seconds = timeout_seconds

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self._api_key:
            raise ProviderError(
                "missing credentials: set ANTHROPIC_API_KEY", retriable=False
            )
        response = self._transport.post_json(
            self._endpoint,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            payload={
                "model": self._model,
                "max_tokens": request.max_tokens,
                "messages": [{"role": "user", "content": request.prompt}],
            },
            timeout_seconds=self._timeout_seconds,
        )
        if not isinstance(response, dict):
            raise ProviderError("provider returned malformed response", retriable=False)
        if "error" in response:
            _raise_api_error(cast(dict[str, object], response), secret=self._api_key)
        text = _text_content(response.get("content"))
        if not text.strip():
            raise ProviderError("provider response has empty content", retriable=False)
        model = response.get("model")
        usage = response.get("usage")
        return LLMResponse(
            text=text,
            model=model if isinstance(model, str) and model else self._model,
            prompt_tokens=_usage_int(usage, "input_tokens", "prompt_tokens"),
            completion_tokens=_usage_int(usage, "output_tokens", "completion_tokens"),
        )


__all__ = [
    "AnthropicProvider",
    "JsonHttpTransport",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
]
