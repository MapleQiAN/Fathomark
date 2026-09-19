"""Generic LLM provider protocol. No SDK imports — adapters live elsewhere."""

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Provider call failed. retriable=True means the host may retry the step."""

    def __init__(self, message: str, *, retriable: bool = False):
        super().__init__(message)
        self.retriable = retriable


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    schema_name: str
    max_tokens: int = 2048


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    version: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


def prompt_key(prompt: str) -> str:
    """Content-addressed cassette key for a prompt."""
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
