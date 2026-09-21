"""Validated, deterministic report input assembled from core facts."""

import hashlib
import json
from datetime import date
from typing import Literal

from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ReviewIssue,
    ScopeSnapshot,
)
from fathomark_core.snapshot import ScoreSnapshot
from pydantic import BaseModel, Field


class ReportEvidence(BaseModel):
    model_config = {"frozen": True}

    id: str
    source_name: str
    source_class: str
    url: str | None
    published_date: date
    data_period_end: date | None
    grade: str
    content_hash: str
    excerpt: str | None = None


class ReportFactor(BaseModel):
    model_config = {"frozen": True}

    factor: str
    proposed_score: float
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    confidence: str
    missing_data: list[str] = Field(default_factory=list)
    as_of_date: date


class ReportLens(BaseModel):
    model_config = {"frozen": True}

    lens: str
    total: float | None
    rating: str
    tactical_state: str | None = None
    vetoed: bool = False
    veto_reasons: list[str] = Field(default_factory=list)
    flagged: bool = False


class ReportModel(BaseModel):
    """The sole input contract shared by report renderers."""

    model_config = {"frozen": True}

    schema_version: Literal["1"] = "1"
    status: Literal["draft", "approved"]
    scope: ScopeSnapshot
    snapshot_hash: str
    overall_confidence: str
    lenses: list[ReportLens]
    factors: list[ReportFactor]
    evidence: list[ReportEvidence]
    review_issues: list[ReviewIssue] = Field(default_factory=list)
    model_hash: str

    @classmethod
    def from_snapshot(
        cls,
        *,
        snapshot: ScoreSnapshot,
        evidence: list[EvidenceItem],
        proposals: list[FactorProposal],
        review_issues: list[ReviewIssue],
        status: Literal["draft", "approved"],
    ) -> "ReportModel":
        report = cls(
            status=status,
            scope=snapshot.scope,
            snapshot_hash=snapshot.content_hash,
            overall_confidence=snapshot.overall_confidence,
            lenses=[
                ReportLens.model_validate(result.model_dump(mode="json"))
                for _, result in sorted(snapshot.lens_results.items())
            ],
            factors=[
                ReportFactor.model_validate(proposal.model_dump(mode="json"))
                for proposal in sorted(proposals, key=lambda item: item.factor)
            ],
            evidence=[
                ReportEvidence.model_validate(item.model_dump(mode="json"))
                for item in sorted(evidence, key=lambda item: item.id)
            ],
            review_issues=sorted(
                review_issues,
                key=lambda item: (item.category, item.factor or "", item.rationale),
            ),
            model_hash="",
        )
        canonical = json.dumps(
            report.model_dump(mode="json", exclude={"model_hash"}),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return report.model_copy(update={"model_hash": digest})
