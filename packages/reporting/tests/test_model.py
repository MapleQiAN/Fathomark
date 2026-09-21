import json
from pathlib import Path

import pytest
from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from fathomark_reporting import ReportModel

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def _inputs():
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    scope = ScopeSnapshot.model_validate(data["scope"])
    evidence = [EvidenceItem.model_validate(item) for item in data["evidence"]]
    proposals = [FactorProposal.model_validate(item) for item in data["proposals"]]
    framework = load_framework(ROOT / "frameworks" / "common-stock.yaml")
    snapshot = evaluate(
        framework=framework, scope=scope, evidence=evidence, proposals=proposals
    )
    return snapshot, evidence, proposals


def test_report_model_copies_snapshot_and_sorts_inputs():
    snapshot, evidence, proposals = _inputs()

    report = ReportModel.from_snapshot(
        snapshot=snapshot,
        evidence=list(reversed(evidence)),
        proposals=list(reversed(proposals)),
        review_issues=[],
        status="draft",
    )

    assert report.status == "draft"
    assert report.snapshot_hash == snapshot.content_hash
    assert list(report.factors) == sorted(
        report.factors, key=lambda factor: factor.factor
    )
    assert list(report.evidence) == sorted(report.evidence, key=lambda item: item.id)
    assert report.factors[0].evidence_ids
    assert report.model_hash.startswith("sha256:")


def test_report_model_is_deterministic_for_same_inputs():
    snapshot, evidence, proposals = _inputs()
    first = ReportModel.from_snapshot(
        snapshot=snapshot,
        evidence=evidence,
        proposals=proposals,
        review_issues=[],
        status="approved",
    )
    second = ReportModel.from_snapshot(
        snapshot=snapshot,
        evidence=evidence,
        proposals=proposals,
        review_issues=[],
        status="approved",
    )

    assert first == second
    assert first.model_hash == second.model_hash


def test_report_model_rejects_proposal_score_mismatch():
    snapshot, evidence, proposals = _inputs()
    proposals[0] = proposals[0].model_copy(
        update={"proposed_score": proposals[0].proposed_score - 1}
    )

    with pytest.raises(ValueError, match="score mismatch"):
        ReportModel.from_snapshot(
            snapshot=snapshot,
            evidence=evidence,
            proposals=proposals,
            review_issues=[],
            status="approved",
        )


def test_report_model_rejects_unknown_provenance_reference():
    snapshot, evidence, proposals = _inputs()
    proposals[0] = proposals[0].model_copy(update={"evidence_ids": ["ev_missing"]})

    with pytest.raises(ValueError, match="unknown evidence"):
        ReportModel.from_snapshot(
            snapshot=snapshot,
            evidence=evidence,
            proposals=proposals,
            review_issues=[],
            status="draft",
        )


def test_report_model_requires_exact_snapshot_factor_coverage():
    snapshot, evidence, proposals = _inputs()

    with pytest.raises(ValueError, match="exactly match"):
        ReportModel.from_snapshot(
            snapshot=snapshot,
            evidence=evidence,
            proposals=proposals[:-1],
            review_issues=[],
            status="draft",
        )


def test_report_model_nested_collections_are_immutable():
    snapshot, evidence, proposals = _inputs()
    report = ReportModel.from_snapshot(
        snapshot=snapshot,
        evidence=evidence,
        proposals=proposals,
        review_issues=[],
        status="draft",
    )

    with pytest.raises(AttributeError):
        report.factors[0].evidence_ids.append("ev_extra")
