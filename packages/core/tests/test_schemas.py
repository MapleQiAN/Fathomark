from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fathomark_core.framework import load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ProposalError,
    ReviewIssue,
    ReviewIssueError,
    ScopeSnapshot,
    validate_proposal,
    validate_review_issue,
)

FRAMEWORK = load_framework(
    Path(__file__).parents[3] / "frameworks" / "common-stock.yaml"
)
CUTOFF = date(2026, 9, 18)
EVIDENCE = {"ev_001": date(2026, 9, 1)}


def _evidence(
    ev_id: str = "ev_001", published: date = date(2026, 9, 1)
) -> EvidenceItem:
    return EvidenceItem(
        id=ev_id,
        source_name="SEC 10-Q",
        source_class="filings",
        url="https://www.sec.gov/example",
        published_date=published,
        data_period_end=None,
        accessed_at=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC),
        grade="A",
        content_hash="sha256:abc",
        excerpt=None,
    )


def _proposal(**kw) -> FactorProposal:
    base = {
        "factor": "financial_health",
        "proposed_score": 7.5,
        "rationale": "现金流覆盖未来两年债务，但利息覆盖率正在下降",
        "evidence_ids": ["ev_001"],
        "counter_evidence_ids": [],
        "confidence": "medium",
        "missing_data": [],
        "as_of_date": date(2026, 9, 18),
    }
    return FactorProposal(**(base | kw))


def _review_issue(**kw) -> ReviewIssue:
    base = {
        "category": "veto_candidate",
        "factor": "governance",
        "evidence_ids": ["ev_001"],
        "rationale": "The filing discloses an unresolved restatement.",
        "blocking": True,
        "as_of_date": date(2026, 9, 3),
    }
    return ReviewIssue(**(base | kw))


def test_scope_snapshot_and_evidence_round_trip():
    scope = ScopeSnapshot(
        symbol="ADBE",
        exchange="NASDAQ",
        research_role="core",
        horizon="5-10y",
        research_date=date(2026, 9, 18),
        data_cutoff=date(2026, 9, 18),
        framework_ref="common-stock@1.0.0",
    )
    assert scope.framework_ref == "common-stock@1.0.0"
    ev = _evidence()
    assert EvidenceItem.model_validate_json(ev.model_dump_json()) == ev


def test_metric_observation_round_trip():
    obs = MetricObservation(
        metric="fcff",
        value=10.28e9,
        unit="USD",
        currency="USD",
        basis="FY2025 10-K",
        formula="cfo - capex",
        data_date=date(2025, 12, 31),
        evidence_id="ev_001",
    )
    assert obs.currency == "USD"
    assert MetricObservation.model_validate_json(obs.model_dump_json()) == obs


def test_review_issue_with_known_evidence_passes():
    issue = ReviewIssue(
        category="veto_candidate",
        factor="governance",
        evidence_ids=["ev_001"],
        rationale="The filing discloses an unresolved restatement.",
        blocking=True,
        as_of_date=date(2026, 9, 3),
    )

    validate_review_issue(
        issue, framework=FRAMEWORK, evidence=EVIDENCE, data_cutoff=CUTOFF
    )


def test_review_issue_with_unknown_evidence_is_rejected():
    issue = ReviewIssue(
        category="unsupported_claim",
        factor=None,
        evidence_ids=["ev_missing"],
        rationale="The conclusion is not supported by a cited filing.",
        blocking=False,
        as_of_date=CUTOFF,
    )

    with pytest.raises(ReviewIssueError, match="unknown evidence"):
        validate_review_issue(
            issue, framework=FRAMEWORK, evidence=EVIDENCE, data_cutoff=CUTOFF
        )


def test_valid_proposal_passes():
    validate_proposal(
        _proposal(), framework=FRAMEWORK, evidence=EVIDENCE, data_cutoff=CUTOFF
    )


def test_score_must_be_on_half_step():
    with pytest.raises(ProposalError, match="step"):
        validate_proposal(
            _proposal(proposed_score=7.3),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_unknown_evidence_rejected():
    with pytest.raises(ProposalError, match="ev_999"):
        validate_proposal(
            _proposal(evidence_ids=["ev_999"]),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_unknown_factor_rejected():
    with pytest.raises(ProposalError):
        validate_proposal(
            _proposal(factor="vibes"),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_proposal_after_cutoff_rejected():
    with pytest.raises(ProposalError, match="cutoff"):
        validate_proposal(
            _proposal(as_of_date=date(2026, 9, 19)),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_empty_rationale_rejected():
    with pytest.raises(ProposalError):
        validate_proposal(
            _proposal(rationale="  "),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_evidence_after_cutoff_rejected():
    with pytest.raises(ProposalError, match="cutoff"):
        validate_proposal(
            _proposal(),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=date(2026, 8, 31),
        )


def test_evidence_after_cutoff_rejected_with_as_of_within_cutoff():
    # Isolates the evidence-published-after-cutoff branch: as_of_date is within
    # the cutoff, so only the evidence-date check can fire.
    with pytest.raises(ProposalError, match="cutoff"):
        validate_proposal(
            _proposal(as_of_date=date(2026, 8, 31)),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=date(2026, 8, 31),
        )


def test_on_step_score_outside_range_rejected():
    # 10.5 is on the 0.5 step grid but above scale.max — isolates the range
    # half of the score check.
    with pytest.raises(ProposalError, match="scale"):
        validate_proposal(
            _proposal(proposed_score=10.5),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_valid_review_issue_passes():
    validate_review_issue(
        _review_issue(), framework=FRAMEWORK, evidence=EVIDENCE, data_cutoff=CUTOFF
    )


def test_review_issue_unknown_evidence_rejected():
    with pytest.raises(ReviewIssueError, match="unknown evidence"):
        validate_review_issue(
            _review_issue(evidence_ids=["ev_missing"]),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_review_issue_unknown_factor_rejected():
    with pytest.raises(ReviewIssueError, match="unknown factor"):
        validate_review_issue(
            _review_issue(factor="vibes"),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_review_issue_after_cutoff_rejected():
    with pytest.raises(ReviewIssueError, match="cutoff"):
        validate_review_issue(
            _review_issue(as_of_date=date(2026, 9, 19)),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )


def test_review_issue_empty_rationale_rejected():
    with pytest.raises(ReviewIssueError, match="rationale"):
        validate_review_issue(
            _review_issue(rationale="  "),
            framework=FRAMEWORK,
            evidence=EVIDENCE,
            data_cutoff=CUTOFF,
        )
