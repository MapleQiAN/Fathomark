from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")
DAY = date(2026, 9, 18)

SCOPE = ScopeSnapshot(
    symbol="ADBE", exchange="NASDAQ", research_role="core", horizon="5-10y",
    research_date=DAY, data_cutoff=DAY, framework_ref="common-stock@1.0.0",
)

ADBE = {
    "business_moat": 9.0, "financial_health": 9.5, "governance": 7.5,
    "policy_risk": 6.5, "growth_sustainability": 7.5, "valuation": 10.0,
    "earnings_quality": 10.0, "trend_momentum": 7.0, "liquidity": 10.0,
    "volatility_downside": 4.0, "catalyst_window": 0.0,
}


def _evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"ev_{i:03d}", source_name="fixture", source_class="filings",
            url=None, published_date=date(2026, 9, 1), data_period_end=None,
            accessed_at=datetime(2026, 9, 18, tzinfo=UTC), grade="A", content_hash=f"sha256:{i}",
        )
        for i in range(1, 12)
    ]


def _proposals(scores=None) -> list[FactorProposal]:
    scores = scores or ADBE
    return [
        FactorProposal(
            factor=factor, proposed_score=score, rationale=f"依据 {factor}",
            evidence_ids=[f"ev_{i:03d}"], counter_evidence_ids=[],
            confidence="high", missing_data=[], as_of_date=DAY,
        )
        for i, (factor, score) in enumerate(scores.items(), start=1)
    ]


def test_evaluate_adbe_reproduces_report():
    snap = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    assert snap.lens_results["core"].total == 85.75
    assert snap.lens_results["core"].rating == "A+"
    assert snap.overall_confidence == "high"
    assert snap.lens_results["tactical"].tactical_state is not None


def test_duplicate_factor_proposal_rejected():
    dup = _proposals() + [_proposals()[0]]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=dup)


def test_missing_factor_proposal_rejected():
    with pytest.raises(ValueError, match="missing"):
        evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals()[:-1])


def test_identical_inputs_identical_hash():
    a = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    b = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    assert a.content_hash == b.content_hash
    assert a == b


def test_different_inputs_different_hash():
    a = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    changed = ADBE | {"valuation": 9.5}
    b = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals(changed))
    assert a.content_hash != b.content_hash
