"""Offline LLM doubles: scripted fake, hash cassette replay, recorder."""

import json
from collections.abc import Iterable
from pathlib import Path

from fathomark_providers.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    prompt_key,
)


class FakeLLMProvider:
    """Queue-scripted provider for unit tests. Never touches network."""

    def __init__(
        self,
        responses: Iterable[str | Exception],
        *,
        name: str = "fake",
        version: str = "0",
    ):
        self._responses = list(responses)
        self.name = name
        self.version = version
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise ProviderError("fake provider queue exhausted", retriable=False)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(text=item, model=f"{self.name}-{self.version}")


class ReplayLLMProvider:
    """Replays recorded responses keyed by prompt content hash."""

    def __init__(
        self, cassette_path: Path, *, name: str = "replay", version: str = "0"
    ):
        self.name = name
        self.version = version
        self._cassette: dict[str, str] = json.loads(
            Path(cassette_path).read_text(encoding="utf-8")
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        key = prompt_key(request.prompt)
        try:
            text = self._cassette[key]
        except KeyError:
            raise ProviderError(f"cassette miss: {key}", retriable=False) from None
        return LLMResponse(text=text, model=f"{self.name}-{self.version}")


class RecordingLLMProvider:
    """Wraps a live provider and records responses into a cassette file."""

    def __init__(self, inner: LLMProvider, cassette_path: Path):
        self._inner = inner
        self._path = Path(cassette_path)
        self.name = inner.name
        self.version = inner.version

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self._inner.complete(request)
        cassette = {}
        if self._path.exists():
            cassette = json.loads(self._path.read_text(encoding="utf-8"))
        cassette[prompt_key(request.prompt)] = response.text
        self._path.write_text(
            json.dumps(cassette, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        return response
