"""Orchestrator: DAG-ready step execution with step records and resume.

Step graph is linear today (scope → collect → six specialist agents → compute)
but expressed as StepSpec(depends_on=...) and executed via topological
levels, so same-level steps may run concurrently later without a contract
change. Failure semantics per design §14: provider failures → failed with
error recorded; agent output failures (repairs exhausted) → needs_review;
never silent, never fabricated.
"""

import hashlib
import json
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fathomark_core import evaluate
from fathomark_core.framework import Framework
from fathomark_providers import (
    EvidenceNormalizer,
    EvidenceProvider,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
)
from fathomark_storage.repository import RunRepository
from fathomark_storage.state_machine import TRANSITIONS, RunState

from fathomark_agents.contracts import AgentError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.scope_agent import ScopeAgent
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)


class OrchestratorError(RuntimeError):
    """Run cannot be executed from its current state (route maps to 409)."""


# Canonical pipeline order for the "already past this state" resume fallback.
_ORDER = [
    RunState.CREATED,
    RunState.SCOPED,
    RunState.COLLECTING,
    RunState.ANALYZING,
    RunState.AUDITING,
    RunState.NEEDS_REVIEW,
    RunState.DRAFT,
]

# States from which execute() must refuse. FAILED is not here: failed runs
# re-enter at COLLECTING and resume from their step records.
_NON_EXECUTABLE = frozenset(
    {RunState.APPROVED, RunState.CANCELLED, RunState.SUPERSEDED}
)

_AGENT_SPECS = (
    ("financial", FinancialAgent),
    ("business", BusinessAgent),
    ("growth", GrowthAgent),
    ("valuation", ValuationAgent),
    ("governance_risk", GovernanceRiskAgent),
    ("market", MarketAgent),
)
_AGENT_STEP_NAMES = frozenset(name for name, _ in _AGENT_SPECS)


def _hash_payload(payload) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    )


def _bfs_path(start: RunState, goal: RunState) -> list[RunState] | None:
    """Shortest path over TRANSITIONS from start to goal (excluding start)."""
    if start == goal:
        return []
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        for nxt in sorted(TRANSITIONS.get(node, ())):
            if nxt in visited:
                continue
            visited.add(nxt)
            if nxt == goal:
                return [*path, nxt]
            queue.append((nxt, [*path, nxt]))
    return None


@dataclass(frozen=True)
class StepSpec:
    name: str
    depends_on: tuple[str, ...]
    entry_state: RunState
    exit_state: RunState | None
    run: Callable[[], dict]  # returns step output for the record


class _BudgetedLLM:
    """LLMProvider wrapper that caps the number of complete() calls."""

    def __init__(self, inner: LLMProvider, max_calls: int):
        self._inner = inner
        self._max_calls = max_calls
        self.calls = 0
        self.name = inner.name
        self.version = inner.version

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls > self._max_calls:
            raise ProviderError("llm call budget exceeded", retriable=False)
        return self._inner.complete(request)


class Orchestrator:
    def __init__(
        self,
        repo: RunRepository,
        framework: Framework,
        *,
        llm: LLMProvider,
        evidence_providers: list[EvidenceProvider],
        max_llm_calls: int = 32,
    ):
        self.repo = repo
        self.framework = framework
        self.llm = _BudgetedLLM(llm, max_llm_calls)
        self.evidence_providers = list(evidence_providers)

    def execute(self, run_id: str) -> RunState:
        row = self.repo.get(run_id)
        state = RunState(row.state)
        if state in _NON_EXECUTABLE:
            raise OrchestratorError(f"run {run_id} in terminal state {state}")
        self._require_orchestrator_driven(run_id)
        if state == RunState.FAILED:
            # Re-entry point for failed runs; step records decide what re-runs.
            self.repo.advance(run_id, RunState.COLLECTING)
            row.error = None
            self.repo.session.flush()
        for level in _topo_levels(build_default_steps(self, run_id)):
            for step in level:
                final = self._execute_step(run_id, step)
                if final is not None:
                    self.repo.session.commit()
                    return final
        self.repo.session.commit()
        return RunState(self.repo.get(run_id).state)

    def _require_orchestrator_driven(self, run_id: str) -> None:
        """Refuse runs driven via the ingest/compute endpoints: they carry DB
        evidence/proposals but no collect step record, so execute() would
        re-ingest and collide with manually persisted data."""
        collect_done = any(
            s.step == "collect" and s.status == "succeeded"
            for s in self.repo.steps_of(run_id)
        )
        if collect_done:
            return
        if self.repo.evidence_of(run_id) or self.repo.proposals_of(run_id):
            raise OrchestratorError(
                "run was not orchestrator-driven; use ingest/compute endpoints"
            )

    def _execute_step(self, run_id: str, step: StepSpec) -> RunState | None:
        """Run one step; return a terminal RunState if the run aborted."""
        input_hash = self._step_input_hash(run_id, step.name)
        rec = self.repo.step_record(run_id, step.name)
        if (
            rec is not None
            and rec.status == "succeeded"
            and rec.input_hash == input_hash
        ):
            return None  # idempotent resume: identical inputs, already done
        provider_name, provider_version = self._provider_info(step.name)
        try:
            self._ensure_state(run_id, step.entry_state)
        except OrchestratorError as exc:
            # No step record is running yet, so no fail_step — just fail the run.
            return self._fail_run(run_id, str(exc))
        self.repo.begin_step(
            run_id,
            step.name,
            input_hash,
            provider_name=provider_name,
            provider_version=provider_version,
        )
        try:
            output = step.run()
            if step.exit_state is not None:
                self._ensure_state(run_id, step.exit_state)
        except AgentError as exc:
            self.repo.fail_step(run_id, step.name, str(exc))
            self.repo.get(run_id).error = str(exc)
            self.repo.advance(run_id, RunState.NEEDS_REVIEW)
            return RunState.NEEDS_REVIEW
        except ProviderError as exc:
            self.repo.fail_step(run_id, step.name, str(exc))
            return self._fail_run(run_id, str(exc))
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all boundary:
            # any unexpected step failure must fail the run explicitly (§14),
            # never propagate silently past execute().
            self.repo.fail_step(run_id, step.name, str(exc))
            return self._fail_run(run_id, f"{type(exc).__name__}: {exc}")
        self.repo.finish_step(run_id, step.name, output)
        return None

    def _fail_run(self, run_id: str, error: str) -> RunState:
        row = self.repo.get(run_id)
        row.error = error
        self._ensure_state(run_id, RunState.FAILED)
        return RunState.FAILED

    def _ensure_state(self, run_id: str, required: RunState) -> None:
        current = RunState(self.repo.get(run_id).state)
        if current == required:
            return
        path = _bfs_path(current, required)
        if path is not None:
            for state in path:
                self.repo.advance(run_id, state)
            return
        if (
            current in _ORDER
            and required in _ORDER
            and _ORDER.index(current) > _ORDER.index(required)
        ):
            return  # resumed run already past the required state
        raise OrchestratorError(
            f"run {run_id} in state {current} cannot reach {required}"
        )

    def _provider_info(self, step_name: str) -> tuple[str | None, str | None]:
        if step_name == "scope":
            return ScopeAgent.name, ScopeAgent.version
        if step_name == "collect":
            return (
                ",".join(p.name for p in self.evidence_providers) or None,
                ",".join(p.version for p in self.evidence_providers) or None,
            )
        if step_name in _AGENT_STEP_NAMES:
            return self.llm.name, self.llm.version
        return None, None

    def _step_input_hash(self, run_id: str, step_name: str) -> str:
        scope = json.loads(self.repo.scope_of(run_id).model_dump_json())
        if step_name == "scope":
            payload = {"scope": scope}
        elif step_name == "collect":
            payload = {
                "scope": scope,
                "providers": [
                    {"name": p.name, "version": p.version}
                    for p in self.evidence_providers
                ],
            }
        elif step_name in _AGENT_STEP_NAMES:
            payload = {"scope": scope, "evidence": self._evidence_index(run_id)}
        elif step_name == "compute":
            payload = {
                "scope": scope,
                "evidence": self._evidence_index(run_id),
                "proposals": sorted(p.factor for p in self.repo.proposals_of(run_id)),
            }
        else:
            raise OrchestratorError(f"unknown step: {step_name}")
        return _hash_payload(payload)

    def _evidence_index(self, run_id: str) -> list[list[str]]:
        return sorted([e.id, e.content_hash] for e in self.repo.evidence_of(run_id))


def _topo_levels(steps: list[StepSpec]) -> list[list[StepSpec]]:
    """Kahn levels over depends_on; definition order kept within a level."""
    names = {s.name for s in steps}
    for s in steps:
        unknown = set(s.depends_on) - names
        if unknown:
            raise OrchestratorError(
                f"step {s.name} depends on unknown steps: {sorted(unknown)}"
            )
    done: set[str] = set()
    levels: list[list[StepSpec]] = []
    pending = list(steps)
    while pending:
        level = [s for s in pending if all(d in done for d in s.depends_on)]
        if not level:
            raise OrchestratorError("step graph has a cycle")
        levels.append(level)
        done.update(s.name for s in level)
        pending = [s for s in pending if s.name not in done]
    return levels


def build_default_steps(orch: Orchestrator, run_id: str) -> list[StepSpec]:
    repo = orch.repo

    def scope_step() -> dict:
        snapshot = ScopeAgent().run(repo, run_id)
        return {"scope": json.loads(snapshot.model_dump_json())}

    def collect_step() -> dict:
        scope = repo.scope_of(run_id)
        fetched = []
        for provider in orch.evidence_providers:
            fetched.extend(provider.fetch(scope))
        normalized = EvidenceNormalizer().normalize(
            fetched, data_cutoff=scope.data_cutoff
        )
        if not normalized.evidence:
            raise ProviderError(
                "no usable evidence after data_cutoff filter", retriable=False
            )
        repo.add_evidence(run_id, list(normalized.evidence))
        return {
            "evidence_ids": [e.id for e in normalized.evidence],
            "dropped_after_cutoff": normalized.dropped_after_cutoff,
            "dropped_duplicates": normalized.dropped_duplicates,
        }

    def make_agent_step(agent_cls) -> Callable[[], dict]:
        def agent_step() -> dict:
            proposals = agent_cls(orch.llm).run(
                scope=repo.scope_of(run_id),
                framework=orch.framework,
                evidence=repo.evidence_of(run_id),
            )
            repo.add_proposals(run_id, proposals, origin="agent")
            return {"factors": sorted(p.factor for p in proposals)}

        return agent_step

    def compute_step() -> dict:
        snapshot = evaluate(
            framework=orch.framework,
            scope=repo.scope_of(run_id),
            evidence=repo.evidence_of(run_id),
            proposals=repo.proposals_of(run_id),
        )
        repo.save_draft_snapshot(run_id, snapshot)
        return {"content_hash": snapshot.content_hash}

    return [
        StepSpec("scope", (), RunState.CREATED, RunState.SCOPED, scope_step),
        StepSpec(
            "collect", ("scope",), RunState.SCOPED, RunState.COLLECTING, collect_step
        ),
        *(
            StepSpec(name, ("collect",), RunState.ANALYZING, None, make_agent_step(cls))
            for name, cls in _AGENT_SPECS
        ),
        StepSpec(
            "compute",
            tuple(name for name, _ in _AGENT_SPECS),
            RunState.ANALYZING,
            RunState.DRAFT,
            compute_step,
        ),
    ]
