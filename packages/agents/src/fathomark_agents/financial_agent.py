"""Financial Agent: financial_health + earnings_quality proposals (design §5.3)."""

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

FINANCIAL_FACTORS = ("financial_health", "earnings_quality")

_INSTRUCTIONS = """You are the Financial Agent for an equity research pipeline.
Return JSON {"proposals": [...]} proposing scores for exactly these factors:
financial_health, earnings_quality.
Each proposal: factor, proposed_score (0-10, 0.5 steps), rationale,
evidence_ids, counter_evidence_ids, confidence (high|medium|low|insufficient),
missing_data, as_of_date. Only cite evidence ids listed below. Never cite
evidence published after the data cutoff. Return JSON only.

INPUT:
"""


def build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem]) -> str:
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
    return _INSTRUCTIONS + json.dumps(payload, sort_keys=True, ensure_ascii=False)


class FinancialAgent:
    name = "financial-agent"
    version = "1.0.0"

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
                if p.factor not in FINANCIAL_FACTORS:
                    raise ValueError(f"financial agent may not propose {p.factor}")
                validate_proposal(
                    p,
                    framework=framework,
                    evidence=evidence_index,
                    data_cutoff=scope.data_cutoff,
                )
            return proposals

        return complete_with_repairs(
            self.llm,
            build_prompt(scope, evidence),
            "factor_proposals",
            parse_validate,
            self.max_repairs,
        )
