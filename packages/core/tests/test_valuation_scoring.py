from pathlib import Path

import pytest
from fathomark_core import valuation
from fathomark_core.framework import load_framework
from fathomark_core.valuation import (
    SensitivityResult,
    deviation,
    score_backup_peg,
    score_deviation,
    score_valuation,
    solve_implied_growth_margin_model,
)

CFG = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml").valuation


@pytest.mark.parametrize(
    "d,expected",
    [(0.35, 0.0), (0.30, 0.0), (0.29, 4.0), (0.10, 4.0), (0.09, 7.0),
     (-0.10, 7.0), (-0.1000001, 7.5), (-0.15, 8.5), (-0.20, 9.5), (-0.21, 10.0)],
)
def test_deviation_anchor_bands(d, expected):
    # Left-closed right-open (framework rule): -0.10 belongs to the flat 7-band;
    # just below -0.10 the interp band applies and rounds to 7.5.
    assert score_deviation(d, CFG) == expected


def test_deviation_denominator_floor():
    # g_expected near zero must not blow up
    assert deviation(0.01, 0.001, 0.05) == pytest.approx((0.01 - 0.001) / 0.05)


@pytest.mark.parametrize("peg,expected", [(3.5, 0.0), (3.0, 4.0), (2.5, 4.0), (2.0, 4.0), (1.5, 7.0), (1.0, 7.0), (0.9, 10.0)])
def test_backup_peg_bands(peg, expected):
    assert score_backup_peg(peg, CFG) == expected


def test_adbe_scores_10():
    v = score_valuation(
        cfg=CFG, ev_market=111.5e9, fcff0=10.28e9, wacc=0.096,
        terminal_growth=0.03, g_expected=0.08,
    )
    assert v.method == "reverse_dcf"
    assert not v.switched_to_backup
    assert v.implied_growth == pytest.approx(-0.05, abs=0.01)
    assert v.score == 10.0  # deviation ≈ ( -0.05 - 0.08 ) / 0.08 ≈ -1.6 < -0.20
    assert v.confidence_downgrade is False  # robust sensitivity


def test_fragile_sensitivity_keeps_score_but_downgrades_confidence(monkeypatch):
    # Fragile: base-case score is kept, but confidence_downgrade must be set.
    fake = SensitivityResult(
        base_g=0.05, min_g=-0.02, max_g=0.12, width=0.14,
        valid_scenarios=9, classification="fragile",
    )
    monkeypatch.setattr(valuation, "run_sensitivity", lambda *a, **k: fake)
    v = score_valuation(
        cfg=CFG, ev_market=1e11, fcff0=1e9, wacc=0.10,
        terminal_growth=0.03, g_expected=1.0,
    )
    assert v.method == "reverse_dcf"
    assert not v.switched_to_backup
    assert v.score == 10.0  # deviation ≈ (0.05 - 1.0) / 1.0 = -0.95 < -0.20
    assert v.confidence_downgrade is True


def test_no_root_switches_to_backup():
    v = score_valuation(
        cfg=CFG, ev_market=1e15, fcff0=1.0, wacc=0.10,
        terminal_growth=0.03, g_expected=0.10, backup_peg=1.5,
    )
    assert v.switched_to_backup and v.method == "backup_peg" and v.score == 7.0


def test_no_backup_peg_when_required_raises():
    with pytest.raises(ValueError, match="backup"):
        score_valuation(cfg=CFG, ev_market=1e15, fcff0=1.0, wacc=0.10,
                        terminal_growth=0.03, g_expected=0.10)


def test_margin_model_solves_positive_growth():
    # company with negative current margin converging to 25%
    g = solve_implied_growth_margin_model(
        ev_market=50e9, revenue0=5e9, margin0=-0.10, margin_t=0.25,
        wacc=0.11, terminal_growth=0.03, cfg=CFG,
    )
    assert g is not None and -0.20 <= g <= 1.00


def test_cross_side_deviation_forces_invalid_and_backup():
    # ADBE sensitivity: min_g ≈ -0.1006, max_g ≈ -0.0112. With g_expected = -0.04
    # (denominator floor 0.05 applies), d_min ≈ -1.21 < -0.10 and d_max ≈ +0.58 >= +0.10,
    # so the sensitivity range spans both sides of ±10% -> invalid -> backup PEG.
    v = score_valuation(
        cfg=CFG, ev_market=111.5e9, fcff0=10.28e9, wacc=0.096,
        terminal_growth=0.03, g_expected=-0.04,
        backup_peg=2.5,
    )
    assert v.switched_to_backup and v.score == 4.0
