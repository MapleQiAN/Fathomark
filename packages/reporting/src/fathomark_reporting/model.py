"""Validated, deterministic report input assembled from core facts."""

import hashlib
import json
from datetime import date
from typing import Literal

from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ReviewIssue,
    ReviewIssueCategory,
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
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    counter_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    confidence: str
    missing_data: tuple[str, ...] = Field(default_factory=tuple)
    as_of_date: date


class ReportLens(BaseModel):
    model_config = {"frozen": True}

    lens: str
    total: float | None
    rating: str
    tactical_state: str | None = None
    vetoed: bool = False
    veto_reasons: tuple[str, ...] = Field(default_factory=tuple)
    flagged: bool = False


class ReportIssue(BaseModel):
    """Immutable, renderer-owned representation of a review issue."""

    model_config = {"frozen": True}

    category: ReviewIssueCategory
    factor: str | None = None
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str
    blocking: bool
    as_of_date: date


class ReportModel(BaseModel):
    """The sole input contract shared by report renderers."""

    model_config = {"frozen": True}

    schema_version: Literal["1"] = "1"
    status: Literal["draft", "approved"]
    scope: ScopeSnapshot
    snapshot_hash: str
    overall_confidence: str
    lenses: tuple[ReportLens, ...]
    factors: tuple[ReportFactor, ...]
    evidence: tuple[ReportEvidence, ...]
    review_issues: tuple[ReportIssue, ...] = Field(default_factory=tuple)
    model_hash: str

    @staticmethod
    def _canonical_payload(report: "ReportModel") -> str:
        return json.dumps(
            report.model_dump(mode="json", exclude={"model_hash"}),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def verify_integrity(self) -> None:
        """Reject model copies whose content hash no longer matches their data."""
        digest = (
            "sha256:"
            + hashlib.sha256(self._canonical_payload(self).encode("utf-8")).hexdigest()
        )
        if digest != self.model_hash:
            raise ValueError(
                f"model hash mismatch: expected {self.model_hash}, computed {digest}"
            )

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
        if not proposals:
            raise ValueError("report requires at least one proposal")
        if not evidence:
            raise ValueError("report requires at least one evidence item")

        evidence_ids = [item.id for item in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence id")
        known_evidence = set(evidence_ids)

        proposal_factors = [proposal.factor for proposal in proposals]
        if len(proposal_factors) != len(set(proposal_factors)):
            raise ValueError("duplicate proposal for factor")
        expected_factors = set(snapshot.factor_scores)
        if set(proposal_factors) != expected_factors:
            raise ValueError(
                "proposal factors must exactly match snapshot factor scores"
            )
        for proposal in proposals:
            expected_score = snapshot.factor_scores[proposal.factor]
            if proposal.proposed_score != expected_score:
                raise ValueError(
                    f"score mismatch for {proposal.factor}: "
                    f"proposal={proposal.proposed_score}, snapshot={expected_score}"
                )
            for evidence_id in proposal.evidence_ids + proposal.counter_evidence_ids:
                if evidence_id not in known_evidence:
                    raise ValueError(f"unknown evidence id: {evidence_id}")
        for issue in review_issues:
            for evidence_id in issue.evidence_ids:
                if evidence_id not in known_evidence:
                    raise ValueError(f"unknown evidence id: {evidence_id}")

        report = cls(
            status=status,
            scope=snapshot.scope,
            snapshot_hash=snapshot.content_hash,
            overall_confidence=snapshot.overall_confidence,
            lenses=tuple(
                ReportLens.model_validate(result.model_dump(mode="json"))
                for _, result in sorted(snapshot.lens_results.items())
            ),
            factors=tuple(
                ReportFactor.model_validate(proposal.model_dump(mode="json"))
                for proposal in sorted(proposals, key=lambda item: item.factor)
            ),
            evidence=tuple(
                ReportEvidence.model_validate(item.model_dump(mode="json"))
                for item in sorted(evidence, key=lambda item: item.id)
            ),
            review_issues=tuple(
                ReportIssue.model_validate(item.model_dump(mode="json"))
                for item in sorted(
                    review_issues,
                    key=lambda item: (
                        item.category,
                        item.factor or "",
                        item.rationale,
                    ),
                )
            ),
            model_hash="",
        )
        digest = (
            "sha256:"
            + hashlib.sha256(cls._canonical_payload(report).encode("utf-8")).hexdigest()
        )
        return report.model_copy(update={"model_hash": digest})
