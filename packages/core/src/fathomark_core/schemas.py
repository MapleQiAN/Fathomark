"""Core domain schemas for research runs (M1 subset)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from fathomark_core.framework import Framework


class ProposalError(ValueError):
    """Raised when a FactorProposal violates the scoring contract."""


class ReviewIssueError(ValueError):
    """Raised when a Red-Team review issue violates the audit contract."""


type ReviewIssueCategory = Literal[
    "unsupported_claim",
    "evidence_conflict",
    "date_or_currency_conflict",
    "duplicate_counting",
    "valuation_cherry_picking",
    "missing_counter_evidence",
    "veto_candidate",
    "data_gap",
]


class ScopeSnapshot(BaseModel):
    model_config = {"frozen": True}

    symbol: str
    exchange: str
    research_role: Literal["core", "offensive", "tactical"]
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str


class EvidenceItem(BaseModel):
    model_config = {"frozen": True}

    id: str
    source_name: str
    source_class: Literal["market_data", "filings", "consensus", "news", "ir", "other"]
    url: str | None
    published_date: date
    data_period_end: date | None
    accessed_at: datetime
    grade: Literal["A", "B", "C"]
    content_hash: str
    excerpt: str | None = None


class MetricObservation(BaseModel):
    model_config = {"frozen": True}

    metric: str
    value: float
    unit: str
    currency: str | None = None
    basis: str
    formula: str | None = None
    data_date: date
    evidence_id: str


class FactorProposal(BaseModel):
    model_config = {"frozen": True}

    factor: str
    proposed_score: float
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "insufficient"]
    missing_data: list[str] = Field(default_factory=list)
    as_of_date: date


class ReviewIssue(BaseModel):
    """An evidence-linked Red-Team objection awaiting human review."""

    model_config = {"frozen": True}

    category: ReviewIssueCategory
    factor: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    blocking: bool
    as_of_date: date


def validate_proposal(
    proposal: FactorProposal,
    *,
    framework: Framework,
    evidence: dict[str, date],
    data_cutoff: date,
) -> None:
    scale = framework.scale
    if proposal.factor not in framework.factors:
        raise ProposalError(f"unknown factor: {proposal.factor}")
    steps = round((proposal.proposed_score - scale.min) / scale.step)
    snapped = scale.min + steps * scale.step
    if abs(proposal.proposed_score - snapped) > 1e-9 or not (
        scale.min <= proposal.proposed_score <= scale.max
    ):
        raise ProposalError(
            f"score {proposal.proposed_score} violates scale [{scale.min}, {scale.max}] step {scale.step}"
        )
    if not proposal.rationale.strip():
        raise ProposalError("rationale must not be empty")
    if proposal.as_of_date > data_cutoff:
        raise ProposalError(
            f"proposal as_of_date {proposal.as_of_date} beyond cutoff {data_cutoff}"
        )
    for ev_id in proposal.evidence_ids + proposal.counter_evidence_ids:
        if ev_id not in evidence:
            raise ProposalError(f"unknown evidence id: {ev_id}")
        if evidence[ev_id] > data_cutoff:
            raise ProposalError(
                f"evidence {ev_id} published after cutoff {data_cutoff}"
            )


def validate_review_issue(
    issue: ReviewIssue,
    *,
    framework: Framework,
    evidence: dict[str, date],
    data_cutoff: date,
) -> None:
    """Reject audit objections that cannot be traced to the frozen run input."""
    if issue.factor is not None and issue.factor not in framework.factors:
        raise ReviewIssueError(f"unknown factor: {issue.factor}")
    if not issue.rationale.strip():
        raise ReviewIssueError("rationale must not be empty")
    if issue.as_of_date > data_cutoff:
        raise ReviewIssueError(
            f"issue as_of_date {issue.as_of_date} beyond cutoff {data_cutoff}"
        )
    for ev_id in issue.evidence_ids:
        if ev_id not in evidence:
            raise ReviewIssueError(f"unknown evidence id: {ev_id}")
        if evidence[ev_id] > data_cutoff:
            raise ReviewIssueError(
                f"evidence {ev_id} published after cutoff {data_cutoff}"
            )
