import json
from datetime import date
from pathlib import Path
from time import sleep

import pytest
from fathomark_agents import LLMBudget, Orchestrator, OrchestratorError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.orchestrator import _BudgetedLLM, build_default_steps
from fathomark_agents.specialist_agent import build_prompt
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)
from fathomark_core import load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ReviewIssue,
)
from fathomark_providers import (
    FakeLLMProvider,
    FixtureEvidenceProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    ProviderResult,
    ReplayLLMProvider,
    prompt_key,
)
from fathomark_storage.state_machine import RunState

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
EXPECTED = json.loads((FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8"))


def _orchestrator(repo, llm, **kwargs):
    return Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=llm,
        evidence_providers=[FixtureEvidenceProvider(FIXTURE / "provider_dump.json")],
        **kwargs,
    )


def _llm_script_with_audit(scope, evidence, audit_payload):
    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text(encoding="utf-8"))
    specialist_payloads = [
        cassette[prompt_key(build_prompt(scope, evidence, cls.instructions))]
        for cls in (
            FinancialAgent,
            BusinessAgent,
            GrowthAgent,
            ValuationAgent,
            GovernanceRiskAgent,
        )
    ]
    market_payload = cassette[
        prompt_key(build_prompt(scope, evidence, MarketAgent.instructions))
    ]
    return [*specialist_payloads, market_payload, json.dumps(audit_payload)]


def _audit_issue(blocking):
    return {
        "category": "data_gap",
        "factor": None,
        "evidence_ids": ["ev_001"],
        "rationale": "A material primary-source gap remains before publication.",
        "blocking": blocking,
        "as_of_date": "2026-09-03",
    }


def test_blocking_red_team_issue_stops_before_draft(seeded_run):
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((FIXTURE / "provider_dump.json").read_text())["evidence"]
    ]
    llm = FakeLLMProvider(
        _llm_script_with_audit(scope, evidence, {"issues": [_audit_issue(True)]})
    )
    orch = _orchestrator(repo, llm)

    assert orch.execute(run_id) == RunState.NEEDS_REVIEW
    assert repo.review_issues_of(run_id) == [
        ReviewIssue.model_validate(_audit_issue(True))
    ]
    assert repo.step_record(run_id, "red_team").status == "succeeded"
    assert repo.step_record(run_id, "compute") is None
    calls = orch.llm.calls

    assert orch.execute(run_id) == RunState.NEEDS_REVIEW
    assert orch.llm.calls == calls
    assert repo.latest_snapshot(run_id) is None


def test_non_blocking_red_team_issue_allows_draft(seeded_run):
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((FIXTURE / "provider_dump.json").read_text())["evidence"]
    ]
    llm = FakeLLMProvider(
        _llm_script_with_audit(scope, evidence, {"issues": [_audit_issue(False)]})
    )

    assert _orchestrator(repo, llm).execute(run_id) == RunState.DRAFT
    assert repo.review_issues_of(run_id)[0].blocking is False
    assert repo.step_record(run_id, "review_gate").status == "succeeded"
    assert repo.latest_snapshot(run_id) is not None


class _StaticEvidenceProvider:
    name = "secondary-fixture"
    version = "1.0.0"

    def __init__(self, evidence, observations=()):
        self._evidence = evidence
        self._observations = observations

    def fetch(self, scope):
        return ProviderResult(
            evidence=tuple(self._evidence), observations=tuple(self._observations)
        )


def test_full_run_reaches_draft_matching_golden(seeded_run):
    repo, run_id = seeded_run
    state = _orchestrator(
        repo, ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    ).execute(run_id)
    assert state == RunState.DRAFT
    snap = repo.latest_snapshot(run_id)
    assert snap.snapshot_json == EXPECTED
    steps = {s.step: s for s in repo.steps_of(run_id)}
    assert set(steps) == {
        "scope",
        "collect",
        "financial",
        "business",
        "growth",
        "valuation",
        "governance_risk",
        "market",
        "red_team",
        "review_gate",
        "compute",
    }
    assert all(s.status == "succeeded" for s in steps.values())
    assert steps["financial"].output_json["llm_usage"]["calls"] >= 1


def test_insufficient_agent_confidence_produces_nr_snapshot(seeded_run):
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((FIXTURE / "provider_dump.json").read_text())["evidence"]
    ]
    responses = []
    for response in _specialist_responses(scope, evidence):
        payload = json.loads(response)
        for proposal in payload["proposals"]:
            proposal["confidence"] = "insufficient"
            proposal["evidence_ids"] = []
            proposal["counter_evidence_ids"] = []
            proposal["missing_data"] = ["required evidence unavailable"]
        responses.append(json.dumps(payload))
    responses.append(json.dumps({"issues": []}))

    assert (
        _orchestrator(repo, FakeLLMProvider(responses)).execute(run_id)
        == RunState.DRAFT
    )
    snapshot = repo.latest_snapshot(run_id).snapshot_json
    assert all(result["rating"] == "NR" for result in snapshot["lens_results"].values())
    assert all(result["total"] is None for result in snapshot["lens_results"].values())


def test_collect_normalizes_duplicate_provider_evidence_before_persisting(seeded_run):
    repo, run_id = seeded_run
    primary = FixtureEvidenceProvider(FIXTURE / "provider_dump.json")
    duplicate = (
        primary.fetch(repo.scope_of(run_id))
        .evidence[0]
        .model_copy(update={"id": "ev_duplicate", "grade": "B"})
    )
    orch = Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=ReplayLLMProvider(FIXTURE / "llm_cassette.json"),
        evidence_providers=[primary, _StaticEvidenceProvider([duplicate])],
    )

    collect = next(
        step for step in build_default_steps(orch, run_id) if step.name == "collect"
    )
    collect.run()

    assert [item.id for item in repo.evidence_of(run_id)] == ["ev_001", "ev_002"]


def test_collect_reports_and_drops_stale_evidence(seeded_run):
    repo, run_id = seeded_run
    primary = FixtureEvidenceProvider(FIXTURE / "provider_dump.json")
    stale = (
        primary.fetch(repo.scope_of(run_id))
        .evidence[0]
        .model_copy(
            update={
                "id": "ev_stale",
                "published_date": date(2020, 1, 1),
                "content_hash": "sha256:stale",
            }
        )
    )
    orch = Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=ReplayLLMProvider(FIXTURE / "llm_cassette.json"),
        evidence_providers=[primary, _StaticEvidenceProvider([stale])],
    )

    collect = next(
        step for step in build_default_steps(orch, run_id) if step.name == "collect"
    )
    output = collect.run()

    assert output["dropped_stale"] == 1
    assert output["stale_evidence_ids"] == ["ev_stale"]
    assert [item.id for item in repo.evidence_of(run_id)] == ["ev_001", "ev_002"]


def test_collect_persists_metric_observations_with_canonical_evidence(seeded_run):
    repo, run_id = seeded_run
    primary = FixtureEvidenceProvider(FIXTURE / "provider_dump.json")
    observation = MetricObservation(
        metric="revenue",
        value=5_870_000_000,
        unit="USD",
        currency="USD",
        basis="quarterly",
        formula="SEC XBRL us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        data_date=repo.scope_of(run_id).data_cutoff,
        evidence_id="ev_001",
    )
    orch = Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=ReplayLLMProvider(FIXTURE / "llm_cassette.json"),
        evidence_providers=[primary, _StaticEvidenceProvider([], [observation])],
    )

    collect = next(
        step for step in build_default_steps(orch, run_id) if step.name == "collect"
    )
    output = collect.run()

    assert repo.metric_observations_of(run_id) == [observation]
    assert output["metric_observation_count"] == 1


def test_collect_without_usable_evidence_enters_needs_review(seeded_run):
    repo, run_id = seeded_run
    orch = Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=ReplayLLMProvider(FIXTURE / "llm_cassette.json"),
        evidence_providers=[_StaticEvidenceProvider([])],
    )

    assert orch.execute(run_id) == RunState.NEEDS_REVIEW
    assert "no usable evidence" in repo.get(run_id).error
    collect = repo.step_record(run_id, "collect")
    assert collect.status == "failed"
    assert repo.latest_snapshot(run_id) is None


def test_resume_after_provider_failure_skips_finished_steps(seeded_run):
    repo, run_id = seeded_run
    bad = FakeLLMProvider([ProviderError("llm down", retriable=False)])
    assert _orchestrator(repo, bad).execute(run_id) == RunState.FAILED
    assert repo.get(run_id).error
    first_attempts = {s.step: s.attempt for s in repo.steps_of(run_id)}
    good = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    assert _orchestrator(repo, good).execute(run_id) == RunState.DRAFT
    steps = {s.step: s for s in repo.steps_of(run_id)}
    assert steps["scope"].attempt == first_attempts["scope"]  # not re-run
    assert steps["collect"].attempt == first_attempts["collect"]
    assert steps["financial"].attempt == 2  # retried
    assert len(repo.evidence_of(run_id)) == 2  # no duplicates


def test_agent_error_sends_run_to_needs_review_and_recovers(seeded_run):
    repo, run_id = seeded_run
    bad = FakeLLMProvider(["garbage", "garbage", "garbage"])
    assert _orchestrator(repo, bad).execute(run_id) == RunState.NEEDS_REVIEW
    assert repo.proposals_of(run_id) == []  # nothing fake persisted
    assert repo.get(run_id).error  # reason recorded like failed runs
    good = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    assert _orchestrator(repo, good).execute(run_id) == RunState.DRAFT


def test_llm_budget_exceeded_fails_run(seeded_run):
    repo, run_id = seeded_run
    llm = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    orch = _orchestrator(repo, llm, max_llm_calls=0)
    assert orch.execute(run_id) == RunState.FAILED
    assert "budget" in repo.get(run_id).error


class _MeteredLLM:
    name = "metered"
    version = "1.0"

    def __init__(self, *, prompt_tokens=5, completion_tokens=3, delay=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.delay = delay

    def complete(self, request):
        if self.delay:
            sleep(self.delay)
        return LLMResponse(
            text="{}",
            model="metered-model",
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        )


def test_budget_wrapper_records_token_cost_and_elapsed_usage():
    wrapper = _BudgetedLLM(
        _MeteredLLM(),
        budget=LLMBudget(
            max_calls=2,
            prompt_cost_per_million=2.0,
            completion_cost_per_million=4.0,
        ),
    )

    wrapper.complete(LLMRequest(prompt="p", schema_name="s"))
    usage = wrapper.usage()

    assert usage.calls == 1
    assert usage.prompt_tokens == 5
    assert usage.completion_tokens == 3
    assert usage.estimated_cost_usd == pytest.approx(0.000022)
    assert usage.elapsed_seconds >= 0


@pytest.mark.parametrize(
    "budget, message",
    [
        (LLMBudget(max_prompt_tokens=4), "prompt-token"),
        (LLMBudget(max_completion_tokens=2), "completion-token"),
        (LLMBudget(max_cost_usd=0.000009, prompt_cost_per_million=2.0), "cost"),
    ],
)
def test_budget_wrapper_fails_when_usage_limit_is_exceeded(budget, message):
    wrapper = _BudgetedLLM(_MeteredLLM(), budget=budget)

    with pytest.raises(ProviderError, match=message):
        wrapper.complete(LLMRequest(prompt="p", schema_name="s"))


def test_budget_wrapper_fails_when_runtime_limit_is_exceeded():
    wrapper = _BudgetedLLM(
        _MeteredLLM(delay=0.002),
        budget=LLMBudget(max_runtime_seconds=0.000001),
    )

    with pytest.raises(ProviderError, match="runtime budget"):
        wrapper.complete(LLMRequest(prompt="p", schema_name="s"))


def test_execute_on_terminal_run_raises(seeded_run):
    repo, run_id = seeded_run
    repo.advance(run_id, RunState.CANCELLED)
    orch = _orchestrator(repo, ReplayLLMProvider(FIXTURE / "llm_cassette.json"))
    with pytest.raises(OrchestratorError):
        orch.execute(run_id)


def test_execute_refuses_manually_driven_run(seeded_run):
    """A run driven via the M2 ingest/compute endpoints has DB evidence and
    proposals but no step records; execute() must refuse it explicitly rather
    than re-ingesting and poisoning its state."""
    repo, run_id = seeded_run
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    evidence = [EvidenceItem.model_validate(e) for e in data["evidence"]]
    proposals = [FactorProposal.model_validate(p) for p in data["proposals"]]
    repo.add_evidence(run_id, evidence)
    repo.advance(run_id, RunState.COLLECTING)
    repo.add_proposals(run_id, proposals)
    repo.advance(run_id, RunState.ANALYZING)
    repo.advance(run_id, RunState.DRAFT)
    repo.session.commit()
    orch = _orchestrator(repo, ReplayLLMProvider(FIXTURE / "llm_cassette.json"))
    with pytest.raises(OrchestratorError, match="not orchestrator-driven"):
        orch.execute(run_id)
    # Run state untouched: still draft, no step records created.
    assert RunState(repo.get(run_id).state) == RunState.DRAFT
    assert repo.steps_of(run_id) == []


def test_resume_retries_only_failed_agent(seeded_run):
    """Market agent (last in level) fails; re-execute reruns only market."""
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence_dump = json.loads((FIXTURE / "provider_dump.json").read_text())
    evidence = [EvidenceItem.model_validate(e) for e in evidence_dump["evidence"]]
    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text())

    # Script responses for the 5 agents before market (1 call each), then fail.
    scripted = [
        cassette[prompt_key(build_prompt(scope, evidence, cls.instructions))]
        for cls in (
            FinancialAgent,
            BusinessAgent,
            GrowthAgent,
            ValuationAgent,
            GovernanceRiskAgent,
        )
    ]
    bad = FakeLLMProvider([*scripted, ProviderError("market llm down")])
    assert _orchestrator(repo, bad).execute(run_id) == RunState.FAILED
    steps = {s.step: s for s in repo.steps_of(run_id)}
    assert steps["market"].status == "failed"
    assert steps["financial"].status == "succeeded"

    good = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    assert _orchestrator(repo, good).execute(run_id) == RunState.DRAFT
    steps = {s.step: s for s in repo.steps_of(run_id)}
    assert steps["market"].attempt == 2
    assert steps["financial"].attempt == 1  # not re-run
    assert len(repo.proposals_of(run_id)) == 11  # no duplicates


def _specialist_responses(scope, evidence):
    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text(encoding="utf-8"))
    return [
        cassette[prompt_key(build_prompt(scope, evidence, cls.instructions))]
        for cls in (
            FinancialAgent,
            BusinessAgent,
            GrowthAgent,
            ValuationAgent,
            GovernanceRiskAgent,
            MarketAgent,
        )
    ]


def _review_issue(*, blocking: bool) -> ReviewIssue:
    return ReviewIssue(
        category="veto_candidate",
        factor="governance",
        evidence_ids=["ev_001"],
        rationale="The filing discloses an unresolved restatement.",
        blocking=blocking,
        as_of_date="2026-09-03",
    )


def test_blocking_red_team_issue_stops_before_compute_and_is_idempotent(seeded_run):
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((FIXTURE / "provider_dump.json").read_text())["evidence"]
    ]
    issue = _review_issue(blocking=True)
    llm = FakeLLMProvider(
        _llm_script_with_audit(
            scope,
            evidence,
            {"issues": [issue.model_dump(mode="json")]},
        )
    )
    orch = _orchestrator(repo, llm)

    assert orch.execute(run_id) == RunState.NEEDS_REVIEW
    assert repo.review_issues_of(run_id) == [issue]
    steps = {s.step: s for s in repo.steps_of(run_id)}
    assert steps["red_team"].status == "succeeded"
    assert steps["review_gate"].status == "succeeded"
    assert repo.step_record(run_id, "compute") is None
    assert repo.latest_snapshot(run_id) is None

    calls = len(llm.requests)
    assert orch.execute(run_id) == RunState.NEEDS_REVIEW
    assert len(llm.requests) == calls
    assert repo.latest_snapshot(run_id) is None


def test_non_blocking_red_team_issue_reaches_draft_and_persists_finding(seeded_run):
    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((FIXTURE / "provider_dump.json").read_text())["evidence"]
    ]
    issue = _review_issue(blocking=False)
    llm = FakeLLMProvider(
        _llm_script_with_audit(
            scope,
            evidence,
            {"issues": [issue.model_dump(mode="json")]},
        )
    )
    orch = _orchestrator(repo, llm)

    assert orch.execute(run_id) == RunState.DRAFT
    assert repo.review_issues_of(run_id) == [issue]
    red_team_output = repo.step_record(run_id, "red_team").output_json
    assert red_team_output["review_issue_count"] == 1
    assert red_team_output["blocking_issue_count"] == 0
    assert red_team_output["llm_usage"]["calls"] >= 7
    assert repo.step_record(run_id, "review_gate").output_json == {
        "blocking_issue_count": 0,
    }
    assert repo.step_record(run_id, "compute").status == "succeeded"
