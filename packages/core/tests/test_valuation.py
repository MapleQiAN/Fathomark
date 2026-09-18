from pathlib import Path

import pytest
from fathomark_core.framework import load_framework
from fathomark_core.valuation import (
    run_sensitivity,
    solve_implied_growth,
    two_stage_ev,
)

CFG = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml").valuation


def test_two_stage_ev_terminal_value():
    # g=0: EV = sum of discounted FCFF + discounted perpetuity
    ev = two_stage_ev(100.0, 0.0, 0.10, 0.03, 5)
    expected = sum(100.0 / 1.1**t for t in range(1, 6)) + (100.0 * 1.03 / 0.07) / 1.1**5
    assert ev == pytest.approx(expected)


def test_adbe_implied_growth_approx_minus_5pct():
    g = solve_implied_growth(ev_market=111.5e9, fcff0=10.28e9, wacc=0.096, terminal_growth=0.03, cfg=CFG)
    assert g == pytest.approx(-0.05, abs=0.01)


def test_solver_returns_none_when_no_root():
    # EV far above anything reachable in [-20%, 100%] growth
    assert solve_implied_growth(ev_market=1e15, fcff0=1.0, wacc=0.10, terminal_growth=0.03, cfg=CFG) is None


def test_sensitivity_adbe_is_classified():
    r = run_sensitivity(ev_market=111.5e9, fcff0=10.28e9, wacc=0.096, terminal_growth=0.03, cfg=CFG)
    assert r.valid_scenarios == 9
    assert r.classification in {"robust", "fragile"}
    assert r.min_g <= r.base_g <= r.max_g
    assert r.width == pytest.approx(r.max_g - r.min_g)


def test_sensitivity_invalid_when_too_few_valid_scenarios():
    # wacc - 1pp == g_T + 0.5pp violates wacc > g_T in some cells only with crafted numbers
    r = run_sensitivity(ev_market=100.0, fcff0=10.0, wacc=0.04, terminal_growth=0.03, cfg=CFG)
    assert r.classification == "invalid"
    assert r.valid_scenarios < CFG.sensitivity.min_valid_scenarios
