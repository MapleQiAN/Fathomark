# packages/core/tests/test_veto.py
from pathlib import Path

from fathomark_core.framework import load_framework
from fathomark_core.veto import evaluate_lens, overall_confidence

FRAMEWORK = load_framework(
    Path(__file__).parents[3] / "frameworks" / "common-stock.yaml"
)

HIGH = {f.id: 9.0 for f in FRAMEWORK.raw_factors}


def test_high_scores_no_veto():
    r = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="high")
    assert r.rating == "S" and r.total == 90.0 and not r.vetoed


def test_financial_health_veto_beats_high_total():
    scores = HIGH | {"financial_health": 2.5}
    r = evaluate_lens(FRAMEWORK, "core", scores, confidence="high")
    assert r.rating == "X" and r.vetoed
    assert any("financial_health" in reason for reason in r.veto_reasons)


def test_governance_veto_applies_to_tactical():
    r = evaluate_lens(
        FRAMEWORK, "tactical", HIGH | {"governance": 2.0}, confidence="high"
    )
    assert r.vetoed and r.rating == "X"


def test_policy_risk_flags_but_does_not_veto_tactical():
    r = evaluate_lens(
        FRAMEWORK, "tactical", HIGH | {"policy_risk": 1.0}, confidence="high"
    )
    assert not r.vetoed and r.flagged and r.rating == "S"


def test_policy_risk_vetoes_core_and_offensive():
    for lens in ("core", "offensive"):
        r = evaluate_lens(
            FRAMEWORK, lens, HIGH | {"policy_risk": 2.5}, confidence="high"
        )
        assert r.vetoed and r.rating == "X"


def test_insufficient_confidence_forces_nr():
    r = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="insufficient")
    assert r.rating == "NR" and r.total is None


def test_tactical_state_only_on_tactical_lens():
    r = evaluate_lens(FRAMEWORK, "tactical", HIGH, confidence="high")
    assert r.tactical_state == "T1"
    r2 = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="high")
    assert r2.tactical_state is None


def test_overall_confidence_is_weakest_link():
    assert overall_confidence(["high", "medium", "high"]) == "medium"
    assert overall_confidence(["low", "insufficient", "high"]) == "insufficient"
    assert overall_confidence(["high"]) == "high"
