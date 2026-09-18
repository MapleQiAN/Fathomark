"""Veto, NR, and confidence aggregation rules."""

from fathomark_core.framework import Framework
from fathomark_core.scoring import (
    LensResult,
    rating_for_total,
    tactical_state_for_total,
    weighted_total,
)

_CONFIDENCE_ORDER = ["insufficient", "low", "medium", "high"]


def overall_confidence(proposals_confidence: list[str]) -> str:
    if not proposals_confidence:
        return "insufficient"
    return min(proposals_confidence, key=_CONFIDENCE_ORDER.index)


def evaluate_lens(
    framework: Framework,
    lens: str,
    scores: dict[str, float],
    confidence: str,
) -> LensResult:
    conf = framework.confidence_levels.get(confidence)
    if conf is None:
        raise ValueError(f"unknown confidence level: {confidence}")
    if conf.get("forces_nr"):
        return LensResult(lens=lens, total=None, rating="NR")

    total = weighted_total(framework, lens, scores)
    veto_reasons = [
        f"{rule.factor} {scores[rule.factor]} below {rule.below}"
        for rule in framework.veto_rules
        if lens in rule.applies_to and scores[rule.factor] < rule.below
    ]
    flagged = any(
        lens not in rule.applies_to and scores[rule.factor] < rule.below
        for rule in framework.veto_rules
    )
    vetoed = bool(veto_reasons)
    return LensResult(
        lens=lens,
        total=total,
        rating="X" if vetoed else rating_for_total(framework, total),
        tactical_state=tactical_state_for_total(framework, total) if lens == "tactical" and not vetoed else None,
        vetoed=vetoed,
        veto_reasons=veto_reasons,
        flagged=flagged and not vetoed,
    )
