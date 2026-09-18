from pathlib import Path

import pytest

from fathomark_core.framework import load_framework
from fathomark_core.scoring import rating_for_total, tactical_state_for_total, weighted_total

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")

# ADBE 长期核心仓研究 2026-09-03: core lens total 85.75 -> A+
ADBE_SCORES = {
    "business_moat": 9.0, "financial_health": 9.5, "governance": 7.5,
    "policy_risk": 6.5, "growth_sustainability": 7.5, "valuation": 10.0,
    "earnings_quality": 10.0, "trend_momentum": 7.0, "liquidity": 10.0,
    "volatility_downside": 4.0, "catalyst_window": 0.0,
}


def test_adbe_core_total_reproduces_report():
    assert weighted_total(FRAMEWORK, "core", ADBE_SCORES) == 85.75


def test_missing_factor_rejected():
    with pytest.raises(KeyError):
        weighted_total(FRAMEWORK, "core", {k: v for k, v in ADBE_SCORES.items() if k != "valuation"})


@pytest.mark.parametrize(
    "total,grade",
    [(100.0, "S"), (90.0, "S"), (89.99, "A+"), (85.0, "A+"), (84.5, "A"),
     (80.0, "A"), (79.5, "B+"), (75.0, "B+"), (74.5, "B"), (70.0, "B"),
     (69.5, "B-"), (65.0, "B-"), (64.5, "C"), (60.0, "C"), (59.5, "D"), (0.0, "D")],
)
def test_rating_spectrum_boundaries(total, grade):
    assert rating_for_total(FRAMEWORK, total) == grade


@pytest.mark.parametrize("total,state", [(80.0, "T1"), (79.5, "T2"), (65.0, "T2"), (64.5, "T3"), (0.0, "T3")])
def test_tactical_state_boundaries(total, state):
    assert tactical_state_for_total(FRAMEWORK, total) == state
