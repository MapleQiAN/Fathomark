import json
from datetime import date

from fathomark_agents.red_team_agent import RedTeamAgent
from fathomark_core.schemas import FactorProposal
from fathomark_providers import FakeLLMProvider


def _proposal():
    return FactorProposal(
        factor="business_moat",
        proposed_score=9.0,
        rationale="The product ecosystem creates switching costs.",
        evidence_ids=["ev_001"],
        counter_evidence_ids=[],
        confidence="high",
        missing_data=[],
        as_of_date="2026-09-03",
    )


def _issue(**overrides):
    return {
        "category": "missing_counter_evidence",
        "factor": "business_moat",
        "evidence_ids": ["ev_001"],
        "rationale": "The proposal does not address the competitive counterexample.",
        "blocking": False,
        "as_of_date": "2026-09-03",
        **overrides,
    }


def test_red_team_agent_returns_valid_issues(scope, evidence, framework):
    issue = _issue()
    llm = FakeLLMProvider([json.dumps({"issues": [issue]})])

    issues = RedTeamAgent(llm).run(
        scope=scope,
        framework=framework,
        evidence=evidence,
        observations=[],
        proposals=[_proposal()],
    )

    assert len(issues) == 1
    assert issues[0].category == "missing_counter_evidence"
    assert issues[0].evidence_ids == ["ev_001"]
    assert llm.requests[0].schema_name == "review_issues"


def test_red_team_agent_repairs_post_cutoff_issue(scope, evidence, framework):
    future = evidence[0].model_copy(
        update={"id": "ev_future", "published_date": date(2026, 9, 4)}
    )
    invalid = json.dumps({"issues": [_issue(evidence_ids=["ev_future"])]})
    valid = json.dumps({"issues": [_issue(category="data_gap", factor=None)]})
    llm = FakeLLMProvider([invalid, valid])

    issues = RedTeamAgent(llm).run(
        scope=scope,
        framework=framework,
        evidence=[*evidence, future],
        observations=[],
        proposals=[_proposal()],
    )

    assert [item.category for item in issues] == ["data_gap"]
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt


def test_red_team_agent_repairs_non_list_issue_container(scope, evidence, framework):
    valid = json.dumps({"issues": [_issue(category="data_gap", factor=None)]})
    llm = FakeLLMProvider([json.dumps({"issues": {}}), valid])

    issues = RedTeamAgent(llm).run(
        scope=scope,
        framework=framework,
        evidence=evidence,
        observations=[],
        proposals=[_proposal()],
    )

    assert [item.category for item in issues] == ["data_gap"]
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt
