import json
from pathlib import Path

import pytest
from fathomark_agents import AgentError, FinancialAgent
from fathomark_agents.financial_agent import FINANCIAL_FACTORS
from fathomark_core import load_framework
from fathomark_providers import FakeLLMProvider, ReplayLLMProvider

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def test_financial_agent_replays_cassette(scope, evidence):
    framework = load_framework(ROOT / "frameworks" / "common-stock.yaml")
    llm = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    proposals = FinancialAgent(llm).run(
        scope=scope, framework=framework, evidence=evidence
    )
    by_factor = {p.factor: p for p in proposals}
    assert set(by_factor) == set(FINANCIAL_FACTORS)
    assert by_factor["financial_health"].proposed_score == 9.5
    assert by_factor["earnings_quality"].proposed_score == 10.0
    assert all(p.evidence_ids for p in proposals)


def test_unknown_evidence_reference_rejected_then_repaired(scope, evidence, framework):
    bad = json.dumps(
        {
            "proposals": [
                {
                    "factor": "financial_health",
                    "proposed_score": 9.5,
                    "rationale": "x",
                    "evidence_ids": ["ev_999"],
                    "counter_evidence_ids": [],
                    "confidence": "high",
                    "missing_data": [],
                    "as_of_date": "2026-09-03",
                }
            ]
        }
    )
    good = (FIXTURE / "financial_response.json").read_text(encoding="utf-8")
    llm = FakeLLMProvider([bad, good])
    proposals = FinancialAgent(llm).run(
        scope=scope, framework=framework, evidence=evidence
    )
    assert {p.factor for p in proposals} == set(FINANCIAL_FACTORS)


def test_post_cutoff_evidence_reference_rejected(scope, evidence, framework):
    # evidence item dated after cutoff is not even in the index → unknown id path;
    # additionally a proposal as_of_date beyond cutoff must be rejected
    late = json.dumps(
        {
            "proposals": [
                {
                    "factor": "financial_health",
                    "proposed_score": 9.5,
                    "rationale": "x",
                    "evidence_ids": ["ev_001"],
                    "counter_evidence_ids": [],
                    "confidence": "high",
                    "missing_data": [],
                    "as_of_date": "2026-09-10",
                }
            ]
        }
    )
    llm = FakeLLMProvider([late, late, late])
    with pytest.raises(AgentError):
        FinancialAgent(llm).run(scope=scope, framework=framework, evidence=evidence)


def test_agent_refuses_foreign_factors(scope, evidence, framework):
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
        FinancialAgent(llm).run(scope=scope, framework=framework, evidence=evidence)
