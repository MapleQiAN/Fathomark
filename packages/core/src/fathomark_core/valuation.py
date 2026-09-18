"""Deterministic reverse DCF and sensitivity analysis (framework §B valuation rules)."""

from typing import Literal

from pydantic import BaseModel

from fathomark_core.framework import ValuationConfig


class SensitivityResult(BaseModel):
    model_config = {"frozen": True}

    base_g: float | None
    min_g: float | None
    max_g: float | None
    width: float | None
    valid_scenarios: int
    classification: Literal["robust", "fragile", "invalid"]


def two_stage_ev(fcff0: float, g: float, wacc: float, terminal_growth: float, years: int) -> float:
    pv = sum(fcff0 * (1 + g) ** t / (1 + wacc) ** t for t in range(1, years + 1))
    terminal = fcff0 * (1 + g) ** years * (1 + terminal_growth) / (wacc - terminal_growth)
    return pv + terminal / (1 + wacc) ** years


def solve_implied_growth(
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    cfg: ValuationConfig,
) -> float | None:
    if wacc <= terminal_growth or fcff0 <= 0:
        return None
    lo, hi = cfg.root_interval
    f_lo = two_stage_ev(fcff0, lo, wacc, terminal_growth, cfg.horizon_years) - ev_market
    f_hi = two_stage_ev(fcff0, hi, wacc, terminal_growth, cfg.horizon_years) - ev_market
    if f_lo > 0 or f_hi < 0:
        return None  # no root in interval — never extrapolate
    for _ in range(200):
        mid = (lo + hi) / 2
        if two_stage_ev(fcff0, mid, wacc, terminal_growth, cfg.horizon_years) < ev_market:
            lo = mid
        else:
            hi = mid
        if hi - lo < cfg.solver_tolerance:
            break
    return (lo + hi) / 2


def run_sensitivity(
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    cfg: ValuationConfig,
) -> SensitivityResult:
    sens = cfg.sensitivity
    base_g = solve_implied_growth(ev_market, fcff0, wacc, terminal_growth, cfg)
    solutions: list[float] = []
    unsolvable_valid = False
    for dw in sens.wacc_offsets:
        for dg in sens.terminal_growth_offsets:
            w, gt = wacc + dw, terminal_growth + dg
            if w <= gt:
                continue  # not economically valid, excluded from the matrix
            g = solve_implied_growth(ev_market, fcff0, w, gt, cfg)
            if g is None:
                unsolvable_valid = True
            else:
                solutions.append(g)

    valid = len(solutions)
    if valid == 0:
        return SensitivityResult(
            base_g=base_g, min_g=None, max_g=None, width=None,
            valid_scenarios=0, classification="invalid",
        )
    lo, hi = min(solutions), max(solutions)
    width = hi - lo
    if (
        unsolvable_valid
        or valid < sens.min_valid_scenarios
        or width > sens.fragile_max_width
    ):
        classification = "invalid"
    elif width <= sens.robust_max_width:
        classification = "robust"
    else:
        classification = "fragile"
    return SensitivityResult(
        base_g=base_g, min_g=lo, max_g=hi, width=width,
        valid_scenarios=valid, classification=classification,
    )
