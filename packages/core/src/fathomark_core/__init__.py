"""Fathomark deterministic scoring core."""

from fathomark_core.framework import Framework, FrameworkValidationError, load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueError,
    ScopeSnapshot,
    validate_review_issue,
)
from fathomark_core.snapshot import ScoreSnapshot, evaluate

__all__ = [
    "EvidenceItem",
    "FactorProposal",
    "Framework",
    "FrameworkValidationError",
    "MetricObservation",
    "ReviewIssue",
    "ReviewIssueCategory",
    "ReviewIssueError",
    "ScopeSnapshot",
    "ScoreSnapshot",
    "evaluate",
    "load_framework",
    "validate_review_issue",
]
