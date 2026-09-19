"""Provider protocols and offline test doubles."""

from fathomark_providers.fake import (
    FakeLLMProvider,
    RecordingLLMProvider,
    ReplayLLMProvider,
)
from fathomark_providers.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    prompt_key,
)

__all__ = [
    "FakeLLMProvider",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderError",
    "RecordingLLMProvider",
    "ReplayLLMProvider",
    "prompt_key",
]
