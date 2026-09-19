"""ScoreSnapshot assembly and the deterministic evaluate() pipeline."""

import hashlib
import json

from pydantic import BaseModel

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)
from fathomark_core.scoring import LensResult
from fathomark_core.veto import evaluate_lens, overall_confidence


class ScoreSnapshot(BaseModel):
    model_config = {"frozen": True}

    scope: ScopeSnapshot
    lens_results: dict[str, LensResult]
    factor_scores: dict[str, float]
    overall_confidence: str
    content_hash: str


def _content_hash(scope: ScopeSnapshot, factor_scores: dict[str, float]) -> str:
    canonical = json.dumps(
        {"scope": json.loads(scope.model_dump_json()), "factor_scores": factor_scores},
        sort_keys=True,
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate(
    *,
    framework: Framework,
    scope: ScopeSnapshot,
    evidence: list[EvidenceItem],
    proposals: list[FactorProposal],
) -> ScoreSnapshot:
    if scope.framework_ref != framework.framework_ref:
        raise ValueError(
            f"scope framework {scope.framework_ref} != loaded {framework.framework_ref}"
        )
    evidence_index: dict = {}
    for ev in evidence:
        if ev.id in evidence_index:
            raise ValueError(f"duplicate evidence id: {ev.id}")
        evidence_index[ev.id] = ev.published_date
    seen: set[str] = set()
    for p in proposals:
        if p.factor in seen:
            raise ValueError(f"duplicate proposal for factor {p.factor}")
        seen.add(p.factor)
        validate_proposal(
            p,
            framework=framework,
            evidence=evidence_index,
            data_cutoff=scope.data_cutoff,
        )
    missing = set(framework.factors) - seen
    if missing:
        raise ValueError(f"missing proposals for factors: {sorted(missing)}")

    scores = {p.factor: p.proposed_score for p in proposals}
    confidence = overall_confidence([p.confidence for p in proposals])
    lens_results = {
        lens: evaluate_lens(framework, lens, scores, confidence)
        for lens in framework.lenses
    }
    return ScoreSnapshot(
        scope=scope,
        lens_results=lens_results,
        factor_scores=scores,
        overall_confidence=confidence,
        content_hash=_content_hash(scope, scores),
    )
