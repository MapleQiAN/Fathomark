"""Versioned scoring framework loading and validation."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class FrameworkValidationError(ValueError):
    """Raised when a framework file fails validation."""


class Scale(BaseModel):
    min: float
    max: float
    step: float


class Factor(BaseModel):
    id: str
    name: str
    category: str
    anchors: dict[int, str]


class RatingBand(BaseModel):
    grade: str
    min: float
    max_exclusive: float


class TacticalBand(BaseModel):
    state: str
    min: float
    max_exclusive: float


class VetoRule(BaseModel):
    factor: str
    below: float
    applies_to: list[str]


class DeviationAnchor(BaseModel):
    min: float | None
    max_exclusive: float | None
    score: float | None = None
    score_low: float | None = None
    score_high: float | None = None


class SensitivityConfig(BaseModel):
    wacc_offsets: list[float]
    terminal_growth_offsets: list[float]
    min_valid_scenarios: int
    robust_max_width: float
    fragile_max_width: float


class ValuationConfig(BaseModel):
    root_interval: tuple[float, float]
    solver_tolerance: float
    horizon_years: int
    sensitivity: SensitivityConfig
    deviation: dict
    backup_peg_anchors: list[dict]


class Framework(BaseModel):
    model_config = {"frozen": True}

    id: str
    version: str
    asset_type: str
    scale: Scale
    lenses: dict[str, dict[str, float]]
    ratings: list[RatingBand]
    tactical_states: list[TacticalBand]
    veto_rules: list[VetoRule]
    confidence_levels: dict[str, dict]
    freshness: dict[str, dict]
    valuation: ValuationConfig
    raw_factors: list[Factor] = Field(alias="factors")

    @property
    def factors(self) -> dict[str, Factor]:
        return {f.id: f for f in self.raw_factors}

    @property
    def framework_ref(self) -> str:
        return f"{self.id}@{self.version}"

    @model_validator(mode="after")
    def _validate(self) -> "Framework":
        errors: list[str] = []
        known = set(self.factors)
        if len(self.raw_factors) != len(known):
            errors.append("duplicate factor ids")
        for lens_name, weights in self.lenses.items():
            unknown = set(weights) - known
            if unknown:
                errors.append(f"lens {lens_name} references unknown factors: {sorted(unknown)}")
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-9:
                errors.append(f"lens {lens_name} weights sum to {total}, must sum to 1.0")
            if set(weights) != known:
                errors.append(f"lens {lens_name} must weight every factor")
        for band_set, label in ((self.ratings, "rating"), (self.tactical_states, "tactical")):
            covered = sorted((b.min, b.max_exclusive) for b in band_set)
            if covered[0][0] != 0 or any(covered[i][1] != covered[i + 1][0] for i in range(len(covered) - 1)):
                errors.append(f"{label} bands must be contiguous from 0 with no gaps")
        for rule in self.veto_rules:
            if rule.factor not in known:
                errors.append(f"veto rule references unknown factor {rule.factor}")
            unknown_lenses = set(rule.applies_to) - set(self.lenses)
            if unknown_lenses:
                errors.append(f"veto rule references unknown lenses: {sorted(unknown_lenses)}")
        if errors:
            raise FrameworkValidationError("; ".join(errors))
        return self


def load_framework(path: Path) -> Framework:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Framework.model_validate(data)
    except FrameworkValidationError:
        raise
    except Exception as exc:  # yaml errors, pydantic errors
        raise FrameworkValidationError(f"invalid framework {path}: {exc}") from exc
