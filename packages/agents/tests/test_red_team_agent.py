import json
from datetime import date

from fathomark_agents import RedTeamAgent
from fathomark_core.schemas import FactorProposal, ReviewIssue
from fathomark_providers import FakeLLMProvider


def _proposal() -> FactorProposal:
    return FactorProposal(
        factor="financial_health",
        proposed_score=9.5,
        rationale="Cash generation covers the observed obligations.",
        evidence_ids=["ev_001"],
        counter_evidence_ids=[],
        confidence="high",
        missing_data=[],
        as_of_date=date(2026, 9, 3),
    )


def _issue(**overrides) -> ReviewIssue:
    values = {
        "category": "veto_candidate",
        "factor": "governance",
        "evidence_ids": ["ev_001"],
        "rationale": "The filing discloses an unresolved restatement.",
        "blocking": True,
        "as_of_date": date(2026, 9, 3),
    }
    return ReviewIssue(**(values | overrides))


def test_red_team_agent_returns_valid_review_issues(scope, evidence, framework):
    issue = _issue()
    llm = FakeLLMProvider([json.dumps({"issues": [issue.model_dump(mode="json")]})])

    issues = RedTeamAgent(llm).run(
        scope=scope,
        framework=framework,
        evidence=evidence,
        observations=[],
        proposals=[_proposal()],
    )

    assert issues == [issue]
    assert llm.requests[0].schema_name == "review_issues"
    assert "cannot propose scores" in llm.requests[0].prompt


def test_red_team_agent_repairs_post_cutoff_evidence_reference(
    scope, evidence, framework
):
    late = evidence[0].model_copy(
        update={"id": "ev_after_cutoff", "published_date": date(2026, 9, 4)}
    )
    bad = _issue(evidence_ids=[late.id])
    good = _issue()
    llm = FakeLLMProvider(
        [
            json.dumps({"issues": [bad.model_dump(mode="json")]}),
            json.dumps({"issues": [good.model_dump(mode="json")]}),
        ]
    )

    issues = RedTeamAgent(llm).run(
        scope=scope,
        framework=framework,
        evidence=[*evidence, late],
        observations=[],
        proposals=[_proposal()],
    )

    assert issues == [good]
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt
