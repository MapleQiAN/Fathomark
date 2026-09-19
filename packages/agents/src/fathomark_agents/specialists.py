"""Specialist scoring agents (design §5.2-§5.7).

Each subclass is only a factor set plus a domain instruction header; all
behavior lives in SpecialistAgent. Factor ownership is mutually exclusive —
FinancialAgent owns financial_health/earnings_quality, these five own the
remaining nine framework factors.
"""

from fathomark_agents.specialist_agent import SpecialistAgent

_TEMPLATE = """You are the {title} for an equity research pipeline.
Return JSON {{"proposals": [...]}} proposing scores for exactly these factors:
{factors}.
{domain}
Each proposal: factor, proposed_score (0-10, 0.5 steps), rationale,
evidence_ids, counter_evidence_ids, confidence (high|medium|low|insufficient),
missing_data, as_of_date. Only cite evidence ids listed below. Never cite
evidence published after the data cutoff. Return JSON only.

INPUT:
"""


def _instructions(title: str, factors: tuple[str, ...], domain: str) -> str:
    return _TEMPLATE.format(title=title, factors=", ".join(factors), domain=domain)


class BusinessAgent(SpecialistAgent):
    name = "business-agent"
    factors = ("business_moat",)
    instructions = _instructions(
        "Business Agent",
        factors,
        "Analyze the business model, moat, competitive landscape, and customer "
        "and product concentration.",
    )


class GrowthAgent(SpecialistAgent):
    name = "growth-agent"
    factors = ("growth_sustainability",)
    instructions = _instructions(
        "Growth Agent",
        factors,
        "Analyze growth sources, backlog, users, capacity and unit economics. "
        "Distinguish sustainable growth from cyclical rebounds and one-offs.",
    )


class ValuationAgent(SpecialistAgent):
    name = "valuation-agent"
    factors = ("valuation",)
    instructions = _instructions(
        "Valuation Agent",
        factors,
        "Choose valuation paths allowed by the framework and explain input "
        "choices. Never compute final valuation numbers yourself.",
    )


class GovernanceRiskAgent(SpecialistAgent):
    name = "governance-risk-agent"
    factors = ("governance", "policy_risk")
    instructions = _instructions(
        "Governance & Risk Agent",
        factors,
        "Analyze management integrity, audit quality, related-party "
        "transactions, capital allocation, and regulatory and policy risk.",
    )


class MarketAgent(SpecialistAgent):
    name = "market-agent"
    factors = ("trend_momentum", "liquidity", "volatility_downside", "catalyst_window")
    instructions = _instructions(
        "Market Agent",
        factors,
        "Interpret trend, liquidity, volatility, drawdown and catalyst windows. "
        "Market metrics are computed programmatically; you only explain "
        "anomalies and event context.",
    )
