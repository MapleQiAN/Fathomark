"""Fathomark deterministic scoring core."""

from fathomark_core.framework import Framework, FrameworkValidationError, load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ScopeSnapshot,
)
from fathomark_core.snapshot import ScoreSnapshot, evaluate

__all__ = [
    "EvidenceItem",
    "FactorProposal",
    "Framework",
    "FrameworkValidationError",
    "MetricObservation",
    "ScopeSnapshot",
    "ScoreSnapshot",
    "evaluate",
    "load_framework",
]
