"""Immutable LLM budget configuration and accumulated usage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMBudget:
    """Run-level limits; ``None`` means no limit for that dimension."""

    max_calls: int = 32
    max_prompt_tokens: int | None = None
    max_completion_tokens: int | None = None
    max_cost_usd: float | None = None
    max_runtime_seconds: float | None = None
    prompt_cost_per_million: float = 0.0
    completion_cost_per_million: float = 0.0

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")
        for name in (
            "max_prompt_tokens",
            "max_completion_tokens",
            "max_cost_usd",
            "max_runtime_seconds",
            "prompt_cost_per_million",
            "completion_cost_per_million",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class LLMBudgetUsage:
    """Cumulative provider usage suitable for a step-run JSON record."""

    calls: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    elapsed_seconds: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
            "elapsed_seconds": round(self.elapsed_seconds, 6),
        }
