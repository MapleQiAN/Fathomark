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


def margin_convergence_ev(
    revenue0: float, margin0: float, margin_t: float,
    g: float, wacc: float, terminal_growth: float, years: int,
) -> float:
    pv = 0.0
    for t in range(1, years + 1):
        revenue_t = revenue0 * (1 + g) ** t
        margin = margin0 + (margin_t - margin0) * t / years
        pv += revenue_t * margin / (1 + wacc) ** t
    revenue_n = revenue0 * (1 + g) ** years
    terminal = revenue_n * margin_t * (1 + terminal_growth) / (wacc - terminal_growth)
    return pv + terminal / (1 + wacc) ** years


def solve_implied_growth_margin_model(
    ev_market: float, revenue0: float, margin0: float, margin_t: float,
    wacc: float, terminal_growth: float, cfg: ValuationConfig,
) -> float | None:
    if wacc <= terminal_growth or revenue0 <= 0:
        return None
    lo, hi = cfg.root_interval
    f = lambda g: margin_convergence_ev(revenue0, margin0, margin_t, g, wacc, terminal_growth, cfg.horizon_years)
    if f(lo) > ev_market or f(hi) < ev_market:
        return None  # no root in interval — never extrapolate
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < ev_market:
            lo = mid
        else:
            hi = mid
        if hi - lo < cfg.solver_tolerance:
            break
    return (lo + hi) / 2


def deviation(g_implied: float, g_expected: float, denominator_floor: float) -> float:
    return (g_implied - g_expected) / max(abs(g_expected), denominator_floor)


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def score_deviation(d: float, cfg: ValuationConfig) -> float:
    # Left-closed right-open matching in YAML anchor order (framework: 边界统一
    # 采用左闭右开规则). d == -0.10 belongs to the flat band [-0.10, 0.10) -> 7.0;
    # the interp band [-0.20, -0.10) approaches 7.5 only from below ("接近-10%
    # 取7.5分" means *near* -0.10, not at it) and gives 9.5 at d == -0.20.
    for anchor in cfg.deviation["anchors"]:
        lo = anchor["min"] if anchor["min"] is not None else float("-inf")
        hi = anchor["max_exclusive"] if anchor["max_exclusive"] is not None else float("inf")
        if lo <= d < hi:
            if anchor.get("score") is not None:
                return anchor["score"]
            # linear interpolation band: score_low at hi edge, score_high at lo edge
            frac = (hi - d) / (hi - lo)
            return _round_half(anchor["score_low"] + frac * (anchor["score_high"] - anchor["score_low"]))
    raise ValueError(f"deviation {d} outside anchor table")


def score_backup_peg(peg: float, cfg: ValuationConfig) -> float:
    if peg <= 0:
        raise ValueError("PEG must be positive; use industry adapter methods otherwise")
    # Anchors form an ordered partition of (0, +inf), listed highest band first.
    # An anchor with `gt: X` matches peg > X (strict), so the boundary value X
    # itself falls into the next band down; other anchors match peg >= min
    # (min: null is the catch-all bottom band). `max_exclusive` documents the
    # upper edge but the partition boundary is defined by the lower bounds.
    for anchor in cfg.backup_peg_anchors:
        if anchor.get("gt") is not None:
            if peg > anchor["gt"]:
                return anchor["score"]
        elif anchor.get("min") is None or peg >= anchor["min"]:
            return anchor["score"]
    raise ValueError(f"peg {peg} outside anchor table")


class ValuationScore(BaseModel):
    model_config = {"frozen": True}

    score: float | None
    method: Literal["reverse_dcf", "reverse_dcf_margin", "backup_peg"]
    implied_growth: float | None
    sensitivity: SensitivityResult | None
    switched_to_backup: bool
    switch_reason: str | None
    # A fragile reverse-DCF sensitivity keeps the base-case score but must
    # downgrade evidence confidence downstream (framework valuation rules).
    confidence_downgrade: bool = False


def _backup(peg: float | None, cfg: ValuationConfig, reason: str) -> "ValuationScore":
    if peg is None:
        raise ValueError(f"backup valuation path required ({reason}) but no backup_peg provided")
    return ValuationScore(
        score=score_backup_peg(peg, cfg), method="backup_peg",
        implied_growth=None, sensitivity=None, switched_to_backup=True, switch_reason=reason,
    )


def score_valuation(
    *,
    cfg: ValuationConfig,
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    g_expected: float,
    backup_peg: float | None = None,
    revenue0: float | None = None,
    margin0: float | None = None,
    margin_t: float | None = None,
) -> ValuationScore:
    use_margin_model = fcff0 <= 0
    if use_margin_model:
        if revenue0 is None or margin0 is None or margin_t is None:
            raise ValueError("margin model requires revenue0, margin0, margin_t")
        base_g = solve_implied_growth_margin_model(
            ev_market, revenue0, margin0, margin_t, wacc, terminal_growth, cfg
        )
        sensitivity = None  # margin-model sensitivity uses same grid; omitted in M1, noted in docs
        method: Literal["reverse_dcf", "reverse_dcf_margin", "backup_peg"] = "reverse_dcf_margin"
    else:
        sensitivity = run_sensitivity(ev_market, fcff0, wacc, terminal_growth, cfg)
        base_g = sensitivity.base_g
        method = "reverse_dcf"
        if sensitivity.classification == "invalid":
            return _backup(backup_peg, cfg, "sensitivity classification invalid")

    if base_g is None:
        return _backup(backup_peg, cfg, "no root in solver interval")

    floor = cfg.deviation["denominator_floor"]
    deviations = [deviation(g, g_expected, floor) for g in ([base_g] if sensitivity is None else
                  [sensitivity.min_g, sensitivity.max_g])]
    if any(d >= 0.10 for d in deviations) and any(d < -0.10 for d in deviations):
        return _backup(backup_peg, cfg, "sensitivity deviation spans undervalued and overvalued")

    return ValuationScore(
        score=score_deviation(deviation(base_g, g_expected, floor), cfg),
        method=method, implied_growth=base_g, sensitivity=sensitivity,
        switched_to_backup=False, switch_reason=None,
        confidence_downgrade=(
            method == "reverse_dcf"
            and sensitivity is not None
            and sensitivity.classification == "fragile"
        ),
    )
