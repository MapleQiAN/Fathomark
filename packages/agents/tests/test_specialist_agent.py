"""Cassette replay contract tests for all six specialist agents."""

import json
from pathlib import Path

import pytest
from fathomark_agents import AgentError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.specialist_agent import build_prompt
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)
from fathomark_providers import FakeLLMProvider, ReplayLLMProvider, prompt_key

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"

AGENTS = (
    FinancialAgent,
    BusinessAgent,
    GrowthAgent,
    ValuationAgent,
    GovernanceRiskAgent,
    MarketAgent,
)


@pytest.mark.parametrize("agent_cls", AGENTS, ids=lambda c: c.name)
def test_agent_replays_golden_proposals(scope, evidence, framework, agent_cls):
    llm = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    proposals = agent_cls(llm).run(scope=scope, framework=framework, evidence=evidence)
    golden = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))[
        "proposals"
    ]
    expected = {p["factor"]: p for p in golden if p["factor"] in agent_cls.factors}
    assert len(proposals) == len(agent_cls.factors) > 0
    for p in proposals:
        g = expected[p.factor]
        assert p.proposed_score == g["proposed_score"]
        assert p.evidence_ids == g["evidence_ids"]
        assert p.rationale == g["rationale"]


def test_all_eleven_factors_covered():
    covered = {f for cls in AGENTS for f in cls.factors}
    assert len(covered) == 11  # no overlap, no gap vs framework factors


def test_market_agent_rejects_foreign_factor(scope, evidence, framework):
    payload = json.dumps(
        {
            "proposals": [
                {
                    "factor": "business_moat",
                    "proposed_score": 9.0,
                    "rationale": "x",
                    "evidence_ids": ["ev_001"],
                    "counter_evidence_ids": [],
                    "confidence": "high",
                    "missing_data": [],
                    "as_of_date": "2026-09-03",
                }
            ]
        }
    )
    llm = FakeLLMProvider([payload, payload, payload])
    with pytest.raises(AgentError):
        MarketAgent(llm).run(scope=scope, framework=framework, evidence=evidence)


def test_business_agent_repairs_malformed_json(scope, evidence, framework):
    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text(encoding="utf-8"))
    good = cassette[
        prompt_key(build_prompt(scope, evidence, BusinessAgent.instructions))
    ]
    llm = FakeLLMProvider(["not json", good])
    proposals = BusinessAgent(llm).run(
        scope=scope, framework=framework, evidence=evidence
    )
    assert [p.factor for p in proposals] == ["business_moat"]
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt
