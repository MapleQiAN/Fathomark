"""Financial Agent: financial_health + earnings_quality proposals (design §5.3)."""

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot

from fathomark_agents.specialist_agent import SpecialistAgent
from fathomark_agents.specialist_agent import build_prompt as _build_prompt

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


class FinancialAgent(SpecialistAgent):
    name = "financial-agent"
    factors = FINANCIAL_FACTORS
    instructions = _INSTRUCTIONS


def build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem]) -> str:
    """2-arg compatibility wrapper (prompt identical to pre-refactor output)."""
    return _build_prompt(scope, evidence, _INSTRUCTIONS)
