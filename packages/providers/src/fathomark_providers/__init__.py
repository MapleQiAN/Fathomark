"""Provider protocols and offline test doubles."""

from fathomark_providers.evidence import (
    EvidenceNormalizationError,
    EvidenceNormalizationResult,
    EvidenceNormalizer,
    EvidenceProvider,
    FixtureEvidenceProvider,
    MetricNormalizationError,
    MetricNormalizer,
    ProviderResult,
    RawMetricObservation,
    SecEdgarEvidenceProvider,
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
    "EvidenceNormalizationError",
    "EvidenceNormalizationResult",
    "EvidenceNormalizer",
    "EvidenceProvider",
    "FakeLLMProvider",
    "FixtureEvidenceProvider",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MetricNormalizationError",
    "MetricNormalizer",
    "ProviderError",
    "ProviderResult",
    "RawMetricObservation",
    "RecordingLLMProvider",
    "ReplayLLMProvider",
    "SecEdgarEvidenceProvider",
    "prompt_key",
]
