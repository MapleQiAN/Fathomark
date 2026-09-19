"""Specialist scoring agent base: shared prompt, validation, repair (§5, §14).

Each specialist owns an exclusive factor set and a domain instruction header.
One LLM call proposes all owned factors; output is schema-validated, checked
for foreign factors and unknown/post-cutoff evidence references, and repaired
at most twice before AgentError propagates to the orchestrator.
"""

import json

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)
from fathomark_providers import LLMProvider

from fathomark_agents.repair import complete_with_repairs


def build_prompt(
    scope: ScopeSnapshot, evidence: list[EvidenceItem], instructions: str
) -> str:
    payload = {
        "scope": json.loads(scope.model_dump_json()),
        "evidence": [
            {
                "id": e.id,
                "source_name": e.source_name,
                "source_class": e.source_class,
                "published_date": e.published_date.isoformat(),
                "data_period_end": e.data_period_end.isoformat()
                if e.data_period_end
                else None,
                "grade": e.grade,
                "excerpt": e.excerpt,
            }
            for e in sorted(evidence, key=lambda e: e.id)
        ],
    }
    return instructions + json.dumps(payload, sort_keys=True, ensure_ascii=False)


class SpecialistAgent:
    """Base class for factor-proposing agents. Subclasses set class attrs."""

    name = "specialist-agent"
    version = "1.0.0"
    factors: tuple[str, ...] = ()
    instructions = ""

    def __init__(self, llm: LLMProvider, max_repairs: int = 2):
        self.llm = llm
        self.max_repairs = max_repairs

    def run(
        self,
        *,
        scope: ScopeSnapshot,
        framework: Framework,
        evidence: list[EvidenceItem],
    ) -> list[FactorProposal]:
        evidence_index = {e.id: e.published_date for e in evidence}

        def parse_validate(text: str) -> list[FactorProposal]:
            # Every failure path must raise ValueError: complete_with_repairs
            # catches ValueError only (ruff BLE001), so structural errors that
            # would surface as KeyError/TypeError are normalized here.
            # json.JSONDecodeError, pydantic.ValidationError and ProposalError
            # are already ValueError subclasses.
            try:
                proposal_dicts = json.loads(text)["proposals"]
                proposals = [FactorProposal.model_validate(p) for p in proposal_dicts]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"malformed proposals payload: {exc}") from exc
            if not proposals:
                raise ValueError("no proposals returned")
            for p in proposals:
                if p.factor not in self.factors:
                    raise ValueError(f"{self.name} may not propose {p.factor}")
                validate_proposal(
                    p,
                    framework=framework,
                    evidence=evidence_index,
                    data_cutoff=scope.data_cutoff,
                )
            return proposals

        return complete_with_repairs(
            self.llm,
            build_prompt(scope, evidence, self.instructions),
            "factor_proposals",
            parse_validate,
            self.max_repairs,
        )
