"""Orchestrator: DAG-ready step execution with step records and resume.

Step graph is linear today (scope → collect → six specialist agents → compute)
but expressed as StepSpec(depends_on=...) and executed via topological
levels, so same-level steps may run concurrently later without a contract
change. Failure semantics per design §14: provider failures → failed with
error recorded; agent output failures (repairs exhausted) → needs_review;
never silent, never fabricated.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from fathomark_core import evaluate
from fathomark_core.framework import Framework
from fathomark_core.schemas import MetricObservation
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

from fathomark_agents.budget import LLMBudget, LLMBudgetUsage
from fathomark_agents.contracts import AgentError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.red_team_agent import RedTeamAgent
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
    run: Callable[[], dict | StepResult]  # returns step output for the record


@dataclass(frozen=True)
class StepResult:
    output: dict
    final_state: RunState | None = None


class _BudgetedLLM:
    """LLMProvider wrapper that enforces and records run-level budgets."""

    def __init__(
        self,
        inner: LLMProvider,
        max_calls: int | None = None,
        *,
        budget: LLMBudget | None = None,
    ):
        self._inner = inner
        if budget is None:
            budget = LLMBudget(max_calls=32 if max_calls is None else max_calls)
        elif max_calls is not None and max_calls != budget.max_calls:
            raise ValueError("max_calls conflicts with budget.max_calls")
        self.budget = budget
        self._calls = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._estimated_cost_usd = 0.0
        self._started_at = monotonic()
        self.name = inner.name
        self.version = inner.version

    @property
    def calls(self) -> int:
        """Backward-compatible count of attempted provider calls."""
        return self._calls

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._calls += 1
        if self._calls > self.budget.max_calls:
            raise ProviderError("llm call budget exceeded", retriable=False)
        self._check_runtime()
        response = self._inner.complete(request)
        if response.prompt_tokens < 0 or response.completion_tokens < 0:
            raise ProviderError(
                "provider returned negative token usage", retriable=False
            )
        self._prompt_tokens += response.prompt_tokens
        self._completion_tokens += response.completion_tokens
        self._estimated_cost_usd += (
            response.prompt_tokens * self.budget.prompt_cost_per_million
            + response.completion_tokens * self.budget.completion_cost_per_million
        ) / 1_000_000
        self._check_limits()
        return response

    def usage(self) -> LLMBudgetUsage:
        return LLMBudgetUsage(
            calls=self._calls,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            estimated_cost_usd=self._estimated_cost_usd,
            elapsed_seconds=monotonic() - self._started_at,
        )

    def _check_runtime(self) -> None:
        limit = self.budget.max_runtime_seconds
        if limit is not None and monotonic() - self._started_at > limit:
            raise ProviderError("llm runtime budget exceeded", retriable=False)

    def _check_limits(self) -> None:
        self._check_runtime()
        if (
            self.budget.max_prompt_tokens is not None
            and self._prompt_tokens > self.budget.max_prompt_tokens
        ):
            raise ProviderError("llm prompt-token budget exceeded", retriable=False)
        if (
            self.budget.max_completion_tokens is not None
            and self._completion_tokens > self.budget.max_completion_tokens
        ):
            raise ProviderError("llm completion-token budget exceeded", retriable=False)
        if (
            self.budget.max_cost_usd is not None
            and self._estimated_cost_usd > self.budget.max_cost_usd
        ):
            raise ProviderError("llm cost budget exceeded", retriable=False)


class Orchestrator:
    def __init__(
        self,
        repo: RunRepository,
        framework: Framework,
        *,
        llm: LLMProvider,
        evidence_providers: list[EvidenceProvider],
        max_llm_calls: int = 32,
        budget: LLMBudget | None = None,
    ):
        self.repo = repo
        self.framework = framework
        self.llm = _BudgetedLLM(
            llm,
            max_llm_calls if budget is None else None,
            budget=budget,
        )
        self.evidence_providers = list(evidence_providers)

    def execute(self, run_id: str) -> RunState:
        row = self.repo.get(run_id)
        state = RunState(row.state)
        if state in _NON_EXECUTABLE:
            raise OrchestratorError(f"run {run_id} in terminal state {state}")
        self._require_orchestrator_driven(run_id)
        if state == RunState.NEEDS_REVIEW and self.repo.has_blocking_review_issues(
            run_id
        ):
            self.repo.session.commit()
            return RunState.NEEDS_REVIEW
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
            result = step.run()
            if isinstance(result, StepResult):
                output = result.output
                if result.final_state is not None:
                    self._ensure_state(run_id, result.final_state)
            else:
                output = result
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
        if isinstance(result, StepResult) and result.final_state is not None:
            return result.final_state
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
        if step_name in _AGENT_STEP_NAMES or step_name == "red_team":
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
            payload = {
                "scope": scope,
                "evidence": self._evidence_index(run_id),
                "observations": self._metric_index(run_id),
            }
        elif step_name == "red_team":
            payload = {
                "scope": scope,
                "evidence": self._evidence_index(run_id),
                "observations": self._metric_index(run_id),
                "proposals": self._proposal_index(run_id),
            }
        elif step_name == "review_gate":
            payload = {
                "issues": [
                    issue.model_dump(mode="json")
                    for issue in self.repo.review_issues_of(run_id)
                ]
            }
        elif step_name == "compute":
            payload = {
                "scope": scope,
                "evidence": self._evidence_index(run_id),
                "observations": self._metric_index(run_id),
                "proposals": sorted(p.factor for p in self.repo.proposals_of(run_id)),
            }
        else:
            raise OrchestratorError(f"unknown step: {step_name}")
        return _hash_payload(payload)

    def _evidence_index(self, run_id: str) -> list[list[str]]:
        return sorted([e.id, e.content_hash] for e in self.repo.evidence_of(run_id))

    def _metric_index(self, run_id: str) -> list[dict]:
        return [
            {
                "metric": observation.metric,
                "value": observation.value,
                "unit": observation.unit,
                "currency": observation.currency,
                "basis": observation.basis,
                "formula": observation.formula,
                "data_date": observation.data_date.isoformat(),
                "evidence_id": observation.evidence_id,
            }
            for observation in self.repo.metric_observations_of(run_id)
        ]

    def _proposal_index(self, run_id: str) -> list[dict]:
        return [
            {
                "factor": proposal.factor,
                "proposed_score": proposal.proposed_score,
                "rationale": proposal.rationale,
                "evidence_ids": proposal.evidence_ids,
                "counter_evidence_ids": proposal.counter_evidence_ids,
                "confidence": proposal.confidence,
                "missing_data": proposal.missing_data,
                "as_of_date": proposal.as_of_date.isoformat(),
            }
            for proposal in sorted(
                self.repo.proposals_of(run_id), key=lambda proposal: proposal.factor
            )
        ]


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
        observations: list[MetricObservation] = []
        for provider in orch.evidence_providers:
            result = provider.fetch(scope)
            fetched.extend(result.evidence)
            observations.extend(result.observations)
        normalized = EvidenceNormalizer().normalize(
            fetched,
            data_cutoff=scope.data_cutoff,
            research_date=scope.research_date,
            freshness=orch.framework.freshness,
        )
        if not normalized.evidence:
            raise ProviderError(
                "no usable evidence after data_cutoff filter", retriable=False
            )
        canonical_observations = []
        for observation in observations:
            evidence_id = normalized.canonical_id_by_input_id.get(
                observation.evidence_id
            )
            if evidence_id is None:
                raise ProviderError(
                    f"metric observation references unusable evidence {observation.evidence_id}",
                    retriable=False,
                )
            canonical_observations.append(
                observation.model_copy(update={"evidence_id": evidence_id})
            )
        repo.add_evidence(run_id, list(normalized.evidence))
        repo.add_metric_observations(run_id, canonical_observations)
        return {
            "evidence_ids": [e.id for e in normalized.evidence],
            "dropped_after_cutoff": normalized.dropped_after_cutoff,
            "dropped_stale": normalized.dropped_stale,
            "stale_evidence_ids": list(normalized.stale_evidence_ids),
            "dropped_duplicates": normalized.dropped_duplicates,
            "metric_observation_count": len(canonical_observations),
        }

    def make_agent_step(agent_cls) -> Callable[[], dict]:
        def agent_step() -> dict:
            proposals = agent_cls(orch.llm).run(
                scope=repo.scope_of(run_id),
                framework=orch.framework,
                evidence=repo.evidence_of(run_id),
                observations=repo.metric_observations_of(run_id),
            )
            repo.add_proposals(run_id, proposals, origin="agent")
            return {
                "factors": sorted(p.factor for p in proposals),
                "llm_usage": orch.llm.usage().as_dict(),
            }

        return agent_step

    def red_team_step() -> dict:
        issues = RedTeamAgent(orch.llm).run(
            scope=repo.scope_of(run_id),
            framework=orch.framework,
            evidence=repo.evidence_of(run_id),
            observations=repo.metric_observations_of(run_id),
            proposals=repo.proposals_of(run_id),
        )
        repo.add_review_issues(run_id, issues)
        return {
            "review_issue_count": len(issues),
            "blocking_issue_count": sum(issue.blocking for issue in issues),
            "issue_count": len(issues),
            "llm_usage": orch.llm.usage().as_dict(),
        }

    def review_gate_step() -> dict | StepResult:
        blocking_count = sum(issue.blocking for issue in repo.review_issues_of(run_id))
        output = {"blocking_issue_count": blocking_count}
        if blocking_count:
            return StepResult(output, RunState.NEEDS_REVIEW)
        return output

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
            "red_team",
            tuple(name for name, _ in _AGENT_SPECS),
            RunState.ANALYZING,
            RunState.AUDITING,
            red_team_step,
        ),
        StepSpec(
            "review_gate",
            ("red_team",),
            RunState.AUDITING,
            None,
            review_gate_step,
        ),
        StepSpec(
            "compute",
            ("review_gate",),
            RunState.AUDITING,
            RunState.DRAFT,
            compute_step,
        ),
    ]
