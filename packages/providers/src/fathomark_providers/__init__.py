"""Provider protocols and offline test doubles."""

from fathomark_providers.evidence import (
    EvidenceProvider,
    FixtureEvidenceProvider,
)
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
    "EvidenceProvider",
    "FakeLLMProvider",
    "FixtureEvidenceProvider",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderError",
    "RecordingLLMProvider",
    "ReplayLLMProvider",
    "prompt_key",
]
