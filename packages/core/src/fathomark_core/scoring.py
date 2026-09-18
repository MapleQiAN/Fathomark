"""Deterministic lens scoring and rating mapping."""

from pydantic import BaseModel

from fathomark_core.framework import Framework


class LensResult(BaseModel):
    model_config = {"frozen": True}

    lens: str
    total: float | None          # None only on NR (veto preserves the computed total)
    rating: str                  # spectrum grade, or "X" / "NR"
    tactical_state: str | None = None
    vetoed: bool = False
    veto_reasons: list[str] = []
    flagged: bool = False        # policy_risk veto on tactical lens


def weighted_total(framework: Framework, lens: str, scores: dict[str, float]) -> float:
    weights = framework.lenses[lens]
    missing = set(weights) - set(scores)
    if missing:
        raise KeyError(f"missing factor scores: {sorted(missing)}")
    return round(sum(scores[f] * w for f, w in weights.items()) * 10, 2)


def _band_for(bands, total: float, label: str) -> str:
    for band in bands:
        if band.min <= total < band.max_exclusive:
            return band.grade if label == "rating" else band.state
    raise ValueError(f"total {total} outside all {label} bands")


def rating_for_total(framework: Framework, total: float) -> str:
    return _band_for(framework.ratings, total, "rating")


def tactical_state_for_total(framework: Framework, total: float) -> str:
    return _band_for(framework.tactical_states, total, "tactical")
