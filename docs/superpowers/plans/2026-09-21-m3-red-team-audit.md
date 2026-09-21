# M3 Red-Team Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a recorded Red-Team audit stage that preserves evidence-backed objections and prevents a blocking objection from being silently turned into a draft.

**Architecture:** A frozen core `ReviewIssue` schema carries typed, evidence-linked objections without changing deterministic score calculation. Storage persists issues under a run; `RedTeamAgent` produces them through the existing bounded repair protocol. The orchestrator executes the audit after all factor specialists, records every issue, moves to `needs_review` for any blocking issue, and otherwise lets deterministic compute create a draft.

**Tech Stack:** Python 3.12+, Pydantic, SQLAlchemy, Alembic, SQLite/PostgreSQL, pytest, Ruff.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 5.8, 5.9, 6, 7, 9, and 14; `TODO.md` section 3.

## Global Constraints

- The scoring core remains network-, database-, and LLM-SDK-free.
- Red-Team issues are objections, not alternative scores; final Lens totals, ratings, Veto, and NR remain deterministic core behavior.
- Every referenced evidence item must exist and be published no later than the frozen run cutoff.
- A blocking issue must preserve its audit record and leave the run in `needs_review`; no resume path may auto-create a draft while it remains unresolved.
- Tests use only recorded/fake LLM responses and no network, credentials, or paid data.

## Review Focus

- An LLM cites an unknown or post-cutoff item: reject its output before any issue is stored.
- An audit detects a material problem: persist the objection, finish the audit step, and stop in `needs_review` rather than losing it in an exception path.
- Re-executing an unchanged run: do not duplicate issues or re-call the LLM after a succeeded audit record.
- Re-executing a run with a still-blocking issue: never bypass the review gate and generate a draft.
- An audit has non-blocking findings only: preserve them and continue through deterministic `compute` to `draft`.

---

### Task 1: Core review-issue contract and validation

**Files:**
- Modify: `packages/core/src/fathomark_core/schemas.py`
- Modify: `packages/core/src/fathomark_core/__init__.py`
- Modify: `packages/core/tests/test_schemas.py`

**Interfaces:**
- Produces: immutable `ReviewIssue`, `ReviewIssueCategory`, and `validate_review_issue(issue, framework, evidence, data_cutoff)`.
- Consumes: the existing `Framework`, evidence-id-to-published-date mapping, and frozen scope cutoff.

- [ ] **Step 1: Write failing contract tests.**

```python
issue = ReviewIssue(
    category="veto_candidate",
    factor="governance",
    evidence_ids=["ev_001"],
    rationale="The filing discloses an unresolved restatement.",
    blocking=True,
    as_of_date=date(2026, 9, 3),
)
validate_review_issue(
    issue, framework=FRAMEWORK, evidence={"ev_001": CUTOFF}, data_cutoff=CUTOFF
)

with pytest.raises(ReviewIssueError, match="unknown evidence"):
    validate_review_issue(
        issue.model_copy(update={"evidence_ids": ["ev_missing"]}),
        framework=FRAMEWORK,
        evidence={},
        data_cutoff=CUTOFF,
    )
```

- [ ] **Step 2: Run the focused test and verify it fails because `ReviewIssue` is absent.**

Run: `uv run pytest -q packages/core/tests/test_schemas.py -k review_issue`

Expected: FAIL with an import error for `ReviewIssue`.

- [ ] **Step 3: Add the minimal frozen schema and validator.**

```python
class ReviewIssue(BaseModel):
    model_config = {"frozen": True}
    category: Literal[
        "unsupported_claim",
        "evidence_conflict",
        "date_or_currency_conflict",
        "duplicate_counting",
        "valuation_cherry_picking",
        "missing_counter_evidence",
        "veto_candidate",
        "data_gap",
    ]
    factor: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    blocking: bool
    as_of_date: date


def validate_review_issue(issue, *, framework, evidence, data_cutoff): ...
```

Require a non-empty rationale; validate an optional factor against the framework; reject future issue dates, unknown evidence, and evidence published after cutoff. Export the public types from the package root.

- [ ] **Step 4: Re-run the focused core tests.**

Run: `uv run pytest -q packages/core/tests/test_schemas.py -k review_issue`

Expected: PASS.

- [ ] **Step 5: Commit the core contract.**

```bash
git add packages/core
git commit -m "feat(core): define red-team review issues"
```

### Task 2: Persist review issues with migration parity

**Files:**
- Modify: `packages/storage/src/fathomark_storage/models.py`
- Modify: `packages/storage/src/fathomark_storage/repository.py`
- Create: `packages/storage/alembic/versions/0004_review_issues.py`
- Modify: `packages/storage/tests/test_repository.py`
- Modify: `packages/storage/tests/test_alembic.py`

**Interfaces:**
- Consumes: `ReviewIssue` from Task 1.
- Produces: `RunRepository.add_review_issues(run_id, issues)`, `review_issues_of(run_id)`, and `has_blocking_review_issues(run_id)`.

- [ ] **Step 1: Write failing repository and migration-parity tests.**

```python
repo.add_evidence(run_id, [EVIDENCE])
repo.add_review_issues(run_id, [ISSUE])
assert repo.review_issues_of(run_id) == [ISSUE]
assert repo.has_blocking_review_issues(run_id) is True
```

Also add `review_issues` to the Alembic table-set assertion and assert that a duplicate `(run_id, category, factor, rationale)` is rejected before mutation.

- [ ] **Step 2: Run the focused storage tests and verify they fail because the repository/table does not exist.**

Run: `uv run pytest -q packages/storage/tests/test_repository.py packages/storage/tests/test_alembic.py -k review_issue`

Expected: FAIL with a missing repository method or absent table.

- [ ] **Step 3: Add `ReviewIssueRow` and Alembic revision `0004`.**

Use an autoincrement primary key; a run foreign key; nullable `factor`; JSON `evidence_ids`; `category`, `rationale`, `blocking`, and `as_of_date`; and a uniqueness constraint over `(run_id, category, factor, rationale)`. Upgrade from revision `0003` and create/drop exactly this table.

- [ ] **Step 4: Implement repository methods.**

Before inserting, load the run evidence IDs; reject every batch containing an unknown evidence reference or a duplicate against the database or within the batch. Return issues in primary-key order, reconstituted as immutable core models. Implement `has_blocking_review_issues` with an existence query.

- [ ] **Step 5: Run storage validation.**

Run: `uv run pytest -q packages/storage/tests && uv run ruff check packages/storage && uv run ruff format --check packages/storage`

Expected: PASS; PostgreSQL tests may skip only without `PG_TEST_URL`.

- [ ] **Step 6: Commit persistence support.**

```bash
git add packages/storage
git commit -m "feat(storage): persist red-team review issues"
```

### Task 3: Red-Team agent protocol

**Files:**
- Create: `packages/agents/src/fathomark_agents/red_team_agent.py`
- Modify: `packages/agents/src/fathomark_agents/__init__.py`
- Create: `packages/agents/tests/test_red_team_agent.py`

**Interfaces:**
- Consumes: `LLMProvider`, scope, framework, collected evidence, normalized observations, and specialist proposals.
- Produces: `RedTeamAgent.run(...) -> list[ReviewIssue]`, using `complete_with_repairs` with `schema_name="review_issues"`.

- [ ] **Step 1: Write failing agent tests.**

```python
issues = RedTeamAgent(
    FakeLLMProvider([json.dumps({"issues": [ISSUE.model_dump(mode="json")]})])
).run(
    scope=SCOPE,
    framework=FRAMEWORK,
    evidence=[EVIDENCE],
    observations=[],
    proposals=[PROPOSAL],
)
assert issues == [ISSUE]
```

Add one test where the LLM first returns an issue citing `ev_after_cutoff`, then a valid repaired payload; assert two provider calls and only the valid issue is returned.

- [ ] **Step 2: Run the focused agent tests and verify they fail because the module is missing.**

Run: `uv run pytest -q packages/agents/tests/test_red_team_agent.py`

Expected: FAIL with an import error for `fathomark_agents.red_team_agent`.

- [ ] **Step 3: Implement the narrow audit parser.**

Build a deterministic JSON prompt containing sorted scope, evidence, observations, and proposals. Require JSON `{"issues": [...]}` only; parse each element as `ReviewIssue`; call `validate_review_issue`; invoke `complete_with_repairs` with at most two repairs. The prompt must state that the agent cannot propose scores and can only report the eight declared categories.

- [ ] **Step 4: Re-run focused agent tests.**

Run: `uv run pytest -q packages/agents/tests/test_red_team_agent.py`

Expected: PASS.

- [ ] **Step 5: Commit the agent.**

```bash
git add packages/agents
git commit -m "feat(agents): add red-team audit agent"
```

### Task 4: Orchestrator audit gate

**Files:**
- Modify: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/agents/tests/test_orchestrator.py`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: `RedTeamAgent` from Task 3 and repository review-issue methods from Task 2.
- Produces: a `red_team` step after all specialists, a deterministic `review_gate` step, persisted output counts, and `needs_review` routing for blocking issues.

- [ ] **Step 1: Write failing orchestration tests.**

```python
state = Orchestrator(
    ..., llm=FakeLLMProvider([*SPECIALIST_RESPONSES, BLOCKING_AUDIT])
).execute(run_id)
assert state is RunState.NEEDS_REVIEW
assert repo.review_issues_of(run_id) == [BLOCKING_ISSUE]
assert repo.step_record(run_id, "red_team").status == "succeeded"
assert repo.step_record(run_id, "compute") is None
```

Add the non-blocking variant: the run is `draft`, audit findings persist, and the compute step succeeds. Re-execute the blocking variant and assert no draft snapshot is created and the LLM call count does not increase.

- [ ] **Step 2: Run the focused orchestration tests and verify they fail because `red_team` is absent.**

Run: `uv run pytest -q packages/agents/tests/test_orchestrator.py -k 'red_team or review_gate'`

Expected: FAIL because no review issues or audit step exists.

- [ ] **Step 3: Add the audit and gate without changing score arithmetic.**

Extend `StepSpec.run` to return either an output dictionary or `StepResult(output, final_state=None)`. Insert `red_team` with all specialist steps as dependencies and state transition `analyzing -> auditing`; it stores issues and returns the count. Insert `review_gate` after it; when any stored issue is blocking, return `StepResult({"blocking_issue_count": count}, RunState.NEEDS_REVIEW)`, otherwise return a count with no final state. `compute` depends on `review_gate` and enters from `auditing`.

Make `execute()` immediately return `needs_review` when an unresolved blocking issue exists, before steps are traversed. This is deliberately stricter than generic recoverable agent-output errors: only a future human-resolution API may clear a blocking audit gate. Include audit issue identity in the gate hash and map `red_team` to the LLM provider metadata.

- [ ] **Step 4: Re-run focused orchestration tests.**

Run: `uv run pytest -q packages/agents/tests/test_orchestrator.py -k 'red_team or review_gate'`

Expected: PASS.

- [ ] **Step 5: Update the M3 roadmap and run repository validation.**

Mark `Red-Team Agent` complete in `TODO.md`; leave real public-sample completion and universal conflict/freshness/NR handling unchecked. Run:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Expected: all repository checks PASS; PostgreSQL remains skipped only if `PG_TEST_URL` is not set.

- [ ] **Step 6: Commit the integrated vertical slice.**

```bash
git add TODO.md packages/agents
git commit -m "feat(agents): gate drafts on red-team audit"
```

## Self-Review

- **Spec coverage:** Task 1 implements the typed `ReviewIssue` data model; Task 2 makes it auditable and durable; Task 3 implements §5.8 without score voting; Task 4 implements §5.9/§6 audit ordering and §9 state routing. Human resolution, report rendering, live providers, universal freshness policy, and NR policy remain intentionally outside this vertical slice and stay unchecked in `TODO.md`.
- **Placeholder scan:** No task relies on an undefined type or an unspecified validation path; every added public interface is named in its producing task.
- **Type consistency:** `ReviewIssue` is produced in Task 1, consumed by Task 2 and 3, and stored/retrieved by Task 2 before Task 4 uses it. `StepResult` is local to Task 4 and does not change agent or provider contracts.
- **Review focus coverage:** Task 3 covers invalid evidence references; Task 4 covers blocking persistence, idempotent re-execution, no auto-draft after review routing, and non-blocking progression.
