import json
from pathlib import Path

import pytest
from fathomark_agents import FixtureReplayAgent
from fathomark_agents.financial_agent import FINANCIAL_FACTORS

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def test_fixture_replay_returns_validated_proposals(scope, evidence, framework):
    agent = FixtureReplayAgent(
        FIXTURE / "stub_proposals.json",
        factors=(
            "business_moat",
            "governance",
            "policy_risk",
            "growth_sustainability",
            "valuation",
            "trend_momentum",
            "liquidity",
            "volatility_downside",
            "catalyst_window",
        ),
    )
    proposals = agent.run(scope=scope, framework=framework, evidence=evidence)
    assert len(proposals) == 9
    assert all(p.factor not in FINANCIAL_FACTORS for p in proposals)


def test_fixture_replay_rejects_post_cutoff_reference(scope, framework, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
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
                        "as_of_date": "2027-01-01",
                    }
                ]
            }
        )
    )
    agent = FixtureReplayAgent(bad, factors=("business_moat",))
    with pytest.raises(ValueError):
        agent.run(scope=scope, framework=framework, evidence=[])
