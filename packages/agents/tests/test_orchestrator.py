import json
from pathlib import Path

import pytest
from fathomark_agents import Orchestrator, OrchestratorError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.specialist_agent import build_prompt
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    ValuationAgent,
)
from fathomark_core import load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal
from fathomark_providers import (
    FakeLLMProvider,
    FixtureEvidenceProvider,
    ProviderError,
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
        "compute",
    }
    assert all(s.status == "succeeded" for s in steps.values())


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
