# M2: Storage, State Machine and Headless API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Fathomark persistent storage, a guarded run state machine, and a headless FastAPI surface so a fixed fixture (ADBE) can be created, scored, reviewed and approved as an immutable version — with no network, no LLM.

**Architecture:** Two new uv workspace packages. `fathomark-storage` owns SQLAlchemy 2.0 models, the run state machine and repositories; it depends on nothing web-related. `fathomark-api` owns the FastAPI app and service layer, and depends on `fathomark-core` (scoring) plus `fathomark-storage`. All mutations are idempotent via an `Idempotency-Key` header; human review uses optimistic locking on `research_runs.lock_version`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, SQLite (PostgreSQL-compatible types only), FastAPI, httpx TestClient, pytest, uv workspace, hatchling.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` (sections 7, 9, 10, 14) and `TODO.md` milestone M2.

## Global Constraints

- Python `>=3.12`; ruff-clean; `uv run pytest -q` green after every task.
- `fathomark-core` stays pure: no DB, no web, no network imports leak into it.
- No `datetime.now()` naïve values — always timezone-aware UTC (`datetime.now(UTC)`).
- Portable column types only (`String`, `Text`, `Date`, `DateTime`, `JSON`, `Integer`, `Float`, `Boolean`) so the same models run on SQLite and PostgreSQL.
- Approved versions are immutable: no UPDATE path on `research_versions` rows, ever.
- States from the spec: `created → scoped → collecting → analyzing → auditing → needs_review → draft → approved`; terminal `failed`, `cancelled`, `superseded`. M2 has no agents yet, so the service path is `created → collecting → analyzing → draft → approved`; `scoped`/`auditing` exist in the enum and transition table for M3 orchestration.
- Every mutation endpoint takes an `Idempotency-Key` header; replay returns the first result, never a duplicate row.
- Commits follow existing convention: `feat(storage): ...`, `feat(api): ...`, `test(api): ...`.

## File Structure

```text
packages/storage/
├── pyproject.toml                          # fathomark-storage, deps: sqlalchemy, fathomark-core
└── src/fathomark_storage/
│   ├── __init__.py                         # re-exports
│   ├── models.py                           # SQLAlchemy rows (Base, ResearchRunRow, ...)
│   ├── database.py                         # create_session_factory(url) -> sessionmaker
│   ├── state_machine.py                    # RunState, TRANSITIONS, transition(), InvalidTransition
│   └── repository.py                       # RunRepository (all DB access)
└── tests/
    ├── test_state_machine.py
    ├── test_models.py
    └── test_repository.py

packages/api/
├── pyproject.toml                          # fathomark-api, deps: fastapi, fathomark-core, fathomark-storage
└── src/fathomark_api/
│   ├── __init__.py                         # re-export create_app
│   ├── schemas.py                          # API DTOs (CreateRunRequest, DecisionRequest, ...)
│   ├── services.py                         # RunService: orchestrates repo + core evaluate
│   ├── app.py                              # create_app(database_url, framework_dir)
│   └── routes/
│       ├── __init__.py
│       └── runs.py                         # /v1/research-runs router
└── tests/
    ├── conftest.py                         # app/client fixtures on tmp SQLite
    ├── test_create_run.py
    ├── test_ingest_and_compute.py
    ├── test_review_and_approve.py
    └── test_e2e_adbe.py
```

Root `pyproject.toml`: add `fathomark-storage` and `fathomark-api` to workspace sources, add them as root deps, and add `httpx` to the dev group (TestClient).

## Data Model (locked)

- `research_runs`: `id` PK (`run_<uuid4hex>`), `idempotency_key` UNIQUE, scope columns (`symbol`, `exchange`, `research_role`, `horizon`, `research_date`, `data_cutoff`, `framework_ref`), `state`, `lock_version` int default 0, `supersedes_id` nullable, `error` nullable, `created_at`, `updated_at`. Scope lives on the run row: it is frozen at creation, which *is* the ScopeSnapshot.
- `evidence_items`: surrogate `pk`, `run_id` FK, `evidence_id` (`ev_...`), spec columns from `EvidenceItem`; UNIQUE(`run_id`, `evidence_id`).
- `factor_proposals`: surrogate `pk`, `run_id` FK, `factor`, `proposed_score`, `rationale`, `evidence_ids`/`counter_evidence_ids`/`missing_data` JSON, `confidence`, `as_of_date`, `origin` (`"agent"`|`"human"`); UNIQUE(`run_id`, `factor`).
- `human_decisions`: `id` PK, `run_id` FK, `action` (`accept|modify|return|approve`), `factor` nullable, `agent_score` nullable, `final_score` nullable, `reason`, `actor`, `created_at`.
- `score_snapshots`: `id` PK, `run_id` FK, `snapshot_json` (full `ScoreSnapshot.model_dump(mode="json")`), `content_hash`, `kind` (`"draft"`), `created_at`. Drafts are replaceable; versions are not.
- `research_versions`: `id` PK, `run_id` FK, `version_no` int, `snapshot_json`, `content_hash`, `idempotency_key` UNIQUE, `created_at`. No update path.

---

### Task 1: fathomark-storage scaffold, models and session factory

**Files:**
- Create: `packages/storage/pyproject.toml`
- Create: `packages/storage/src/fathomark_storage/__init__.py`
- Create: `packages/storage/src/fathomark_storage/models.py`
- Create: `packages/storage/src/fathomark_storage/database.py`
- Modify: `pyproject.toml` (workspace sources + root deps)
- Test: `packages/storage/tests/test_models.py`

**Interfaces:**
- Produces: `Base`, `ResearchRunRow`, `EvidenceItemRow`, `FactorProposalRow`, `HumanDecisionRow`, `ScoreSnapshotRow`, `ResearchVersionRow`; `create_session_factory(url: str) -> sessionmaker`; `init_db(session_factory) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# packages/storage/tests/test_models.py
from fathomark_storage import create_session_factory, init_db
from fathomark_storage.models import ResearchRunRow
from datetime import date, datetime, UTC


def test_run_row_roundtrip():
    sf = create_session_factory("sqlite:///:memory:")
    init_db(sf)
    with sf() as s:
        s.add(
            ResearchRunRow(
                id="run_1",
                idempotency_key="k1",
                symbol="ADBE",
                exchange="NASDAQ",
                research_role="core",
                horizon="3y",
                research_date=date(2026, 9, 3),
                data_cutoff=date(2026, 9, 3),
                framework_ref="common-stock@1.0.0",
                state="created",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()
        row = s.get(ResearchRunRow, "run_1")
        assert row.symbol == "ADBE" and row.state == "created" and row.lock_version == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/storage/tests/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fathomark_storage'`

- [ ] **Step 3: Scaffold package**

`packages/storage/pyproject.toml`:

```toml
[project]
name = "fathomark-storage"
version = "0.1.0"
description = "Storage layer for Fathomark"
requires-python = ">=3.12"
dependencies = ["sqlalchemy>=2.0", "fathomark-core"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fathomark_storage"]
```

Root `pyproject.toml` — add to `[tool.uv.sources]`:

```toml
fathomark-storage = { workspace = true }
fathomark-api = { workspace = true }
```

and root dependencies become `["fathomark-core", "fathomark-storage", "fathomark-api"]`; dev group gains `"httpx>=0.27"`. Then `uv sync`.

- [ ] **Step 4: Implement models.py**

```python
"""SQLAlchemy rows for M2. Portable types only (SQLite + PostgreSQL)."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchRunRow(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    symbol: Mapped[str] = mapped_column(String(16))
    exchange: Mapped[str] = mapped_column(String(16))
    research_role: Mapped[str] = mapped_column(String(16))
    horizon: Mapped[str] = mapped_column(String(32))
    research_date: Mapped[date]
    data_cutoff: Mapped[date]
    framework_ref: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="created")
    lock_version: Mapped[int] = mapped_column(Integer, default=0)
    supersedes_id: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class EvidenceItemRow(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("run_id", "evidence_id"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    evidence_id: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(200))
    source_class: Mapped[str] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[date]
    data_period_end: Mapped[date | None]
    accessed_at: Mapped[datetime]
    grade: Mapped[str] = mapped_column(String(1))
    content_hash: Mapped[str] = mapped_column(String(80))
    excerpt: Mapped[str | None] = mapped_column(Text)


class FactorProposalRow(Base):
    __tablename__ = "factor_proposals"
    __table_args__ = (UniqueConstraint("run_id", "factor"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    factor: Mapped[str] = mapped_column(String(64))
    proposed_score: Mapped[float]
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    counter_evidence_ids: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[str] = mapped_column(String(16))
    missing_data: Mapped[list] = mapped_column(JSON)
    as_of_date: Mapped[date]
    origin: Mapped[str] = mapped_column(String(8), default="agent")


class HumanDecisionRow(Base):
    __tablename__ = "human_decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    action: Mapped[str] = mapped_column(String(16))
    factor: Mapped[str | None] = mapped_column(String(64))
    agent_score: Mapped[float | None]
    final_score: Mapped[float | None]
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime]


class ScoreSnapshotRow(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(8), default="draft")
    created_at: Mapped[datetime]


class ResearchVersionRow(Base):
    __tablename__ = "research_versions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime]
```

`database.py`:

```python
"""Engine/session factory. sync SQLAlchemy; SQLite-first, PostgreSQL-safe."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fathomark_storage.models import Base


def create_session_factory(url: str) -> sessionmaker:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(session_factory: sessionmaker) -> None:
    Base.metadata.create_all(session_factory.kw["bind"])
```

`__init__.py` re-exports `create_session_factory`, `init_db`, `models`, `RunState`, `transition`, `InvalidTransition`, `RunRepository` (latter three land in Tasks 2–3; add exports as they appear).

- [ ] **Step 5: Run test, verify pass; commit**

Run: `uv run pytest packages/storage/tests -q`
Expected: PASS

```bash
git add packages/storage pyproject.toml uv.lock
git commit -m "feat(storage): scaffold package with run/evidence/proposal/version models"
```

---

### Task 2: Run state machine with transition guard

**Files:**
- Create: `packages/storage/src/fathomark_storage/state_machine.py`
- Test: `packages/storage/tests/test_state_machine.py`

**Interfaces:**
- Produces: `RunState(StrEnum)` with all 10 spec states; `transition(current: RunState, target: RunState) -> RunState` raising `InvalidTransition(current, target)`; `TERMINAL_STATES: frozenset[RunState]`.

- [ ] **Step 1: Write the failing test**

```python
# packages/storage/tests/test_state_machine.py
import pytest

from fathomark_storage.state_machine import InvalidTransition, RunState, transition


def test_happy_path_created_to_approved():
    s = RunState.CREATED
    for target in (
        RunState.COLLECTING,
        RunState.ANALYZING,
        RunState.DRAFT,
        RunState.APPROVED,
    ):
        s = transition(s, target)
    assert s == RunState.APPROVED


def test_approve_only_from_draft():
    with pytest.raises(InvalidTransition):
        transition(RunState.COLLECTING, RunState.APPROVED)


def test_approved_is_terminal_except_superseded():
    with pytest.raises(InvalidTransition):
        transition(RunState.APPROVED, RunState.DRAFT)
    assert transition(RunState.APPROVED, RunState.SUPERSEDED) == RunState.SUPERSEDED


def test_cancelled_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(RunState.CANCELLED, RunState.COLLECTING)


def test_needs_review_resolves_to_draft():
    assert transition(RunState.DRAFT, RunState.NEEDS_REVIEW) == RunState.NEEDS_REVIEW
    assert transition(RunState.NEEDS_REVIEW, RunState.DRAFT) == RunState.DRAFT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/storage/tests/test_state_machine.py -q`
Expected: FAIL — cannot import `state_machine`

- [ ] **Step 3: Implement state_machine.py**

```python
"""Research-run state machine. Spec: design doc section 9."""

from enum import StrEnum


class RunState(StrEnum):
    CREATED = "created"
    SCOPED = "scoped"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    AUDITING = "auditing"
    NEEDS_REVIEW = "needs_review"
    DRAFT = "draft"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


TERMINAL_STATES = frozenset(
    {RunState.APPROVED, RunState.FAILED, RunState.CANCELLED, RunState.SUPERSEDED}
)

TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset(
        {RunState.SCOPED, RunState.COLLECTING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.SCOPED: frozenset(
        {RunState.COLLECTING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.COLLECTING: frozenset(
        {RunState.ANALYZING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.ANALYZING: frozenset(
        {
            RunState.AUDITING,
            RunState.DRAFT,
            RunState.NEEDS_REVIEW,
            RunState.CANCELLED,
            RunState.FAILED,
        }
    ),
    RunState.AUDITING: frozenset(
        {RunState.DRAFT, RunState.NEEDS_REVIEW, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.NEEDS_REVIEW: frozenset(
        {RunState.DRAFT, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.DRAFT: frozenset(
        {RunState.APPROVED, RunState.NEEDS_REVIEW, RunState.CANCELLED}
    ),
    RunState.APPROVED: frozenset({RunState.SUPERSEDED}),
    RunState.FAILED: frozenset({RunState.COLLECTING, RunState.CANCELLED}),
    RunState.CANCELLED: frozenset(),
    RunState.SUPERSEDED: frozenset(),
}


class InvalidTransition(ValueError):
    def __init__(self, current: RunState, target: RunState):
        super().__init__(f"illegal transition {current} -> {target}")
        self.current = current
        self.target = target


def transition(current: RunState, target: RunState) -> RunState:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(current, target)
    return target
```

- [ ] **Step 4: Run test, verify pass; commit**

```bash
git add packages/storage
git commit -m "feat(storage): run state machine with transition guard"
```

---

### Task 3: RunRepository — all DB access, optimistic lock, idempotent creates

**Files:**
- Create: `packages/storage/src/fathomark_storage/repository.py`
- Test: `packages/storage/tests/test_repository.py`

**Interfaces:**
- Consumes: models and `transition` from Tasks 1–2.
- Produces: `RunRepository(session)` with:
  - `create_run(*, idem_key: str, scope: ScopeSnapshot) -> tuple[ResearchRunRow, bool]` — `(row, created)`; replay on same `idem_key` returns `(existing, False)`.
  - `get(run_id: str) -> ResearchRunRow` (raises `LookupError`)
  - `add_evidence(run_id, items: list[EvidenceItem]) -> int` (insert count; duplicates by evidence_id raise `ValueError`)
  - `add_proposals(run_id, proposals: list[FactorProposal], origin: str = "agent") -> None`
  - `replace_proposal_score(run_id, factor, score, rationale) -> None` (human modify)
  - `advance(run_id, target: RunState) -> None` (guard via `transition`, bumps `lock_version`, `updated_at`)
  - `save_draft_snapshot(run_id, snapshot: ScoreSnapshot) -> None`
  - `latest_snapshot(run_id) -> ScoreSnapshotRow | None`
  - `record_decision(run_id, action, factor, agent_score, final_score, reason, actor) -> None`
  - `create_version(run_id, idem_key: str, expected_lock: int) -> tuple[ResearchVersionRow, bool]` — optimistic lock on `lock_version`; raises `ConcurrencyError` on mismatch; replay returns `(existing, False)`.
  - `evidence_of(run_id) -> list[EvidenceItem]`, `proposals_of(run_id) -> list[FactorProposal]` (rebuild core schemas from rows)
  - `scope_of(run_id) -> ScopeSnapshot`
  - `ConcurrencyError(RuntimeError)` with `expected`/`actual`.

- [ ] **Step 1: Write the failing test**

```python
# packages/storage/tests/test_repository.py
from datetime import date, datetime, UTC

import pytest
from fathomark_core.schemas import ScopeSnapshot

from fathomark_storage import create_session_factory, init_db
from fathomark_storage.repository import ConcurrencyError, RunRepository
from fathomark_storage.state_machine import InvalidTransition, RunState

SCOPE = ScopeSnapshot(
    symbol="ADBE",
    exchange="NASDAQ",
    research_role="core",
    horizon="3y",
    research_date=date(2026, 9, 3),
    data_cutoff=date(2026, 9, 3),
    framework_ref="common-stock@1.0.0",
)


@pytest.fixture()
def repo():
    sf = create_session_factory("sqlite:///:memory:")
    init_db(sf)
    with sf() as s:
        yield RunRepository(s)


def test_create_run_idempotent(repo):
    row1, created1 = repo.create_run(idem_key="k1", scope=SCOPE)
    row2, created2 = repo.create_run(idem_key="k1", scope=SCOPE)
    assert created1 and not created2 and row1.id == row2.id


def test_advance_guards_illegal_transition(repo):
    row, _ = repo.create_run(idem_key="k2", scope=SCOPE)
    with pytest.raises(InvalidTransition):
        repo.advance(row.id, RunState.APPROVED)
    repo.advance(row.id, RunState.COLLECTING)
    assert repo.get(row.id).lock_version == 1


def test_scope_roundtrip(repo):
    row, _ = repo.create_run(idem_key="k3", scope=SCOPE)
    assert repo.scope_of(row.id) == SCOPE
```

- [ ] **Step 2: Run test to verify it fails** — module missing.

- [ ] **Step 3: Implement repository.py**

```python
"""All DB access for research runs. No web imports here."""

import uuid
from datetime import UTC, datetime

from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from fathomark_storage.models import (
    EvidenceItemRow,
    FactorProposalRow,
    HumanDecisionRow,
    ResearchRunRow,
    ResearchVersionRow,
    ScoreSnapshotRow,
)
from fathomark_core.snapshot import ScoreSnapshot
from fathomark_storage.state_machine import RunState, transition


class ConcurrencyError(RuntimeError):
    def __init__(self, expected: int, actual: int):
        super().__init__(f"lock_version conflict: expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class RunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_run(self, *, idem_key: str, scope: ScopeSnapshot):
        existing = self.session.scalar(
            select(ResearchRunRow).where(ResearchRunRow.idempotency_key == idem_key)
        )
        if existing is not None:
            return existing, False
        now = datetime.now(UTC)
        row = ResearchRunRow(
            id=_uid("run"),
            idempotency_key=idem_key,
            symbol=scope.symbol,
            exchange=scope.exchange,
            research_role=scope.research_role,
            horizon=scope.horizon,
            research_date=scope.research_date,
            data_cutoff=scope.data_cutoff,
            framework_ref=scope.framework_ref,
            state=RunState.CREATED.value,
            lock_version=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return row, True

    def get(self, run_id: str) -> ResearchRunRow:
        row = self.session.get(ResearchRunRow, run_id)
        if row is None:
            raise LookupError(f"run not found: {run_id}")
        return row

    def advance(self, run_id: str, target: RunState) -> None:
        row = self.get(run_id)
        row.state = transition(RunState(row.state), target).value
        row.lock_version += 1
        row.updated_at = datetime.now(UTC)
        self.session.flush()

    def scope_of(self, run_id: str) -> ScopeSnapshot:
        r = self.get(run_id)
        return ScopeSnapshot(
            symbol=r.symbol,
            exchange=r.exchange,
            research_role=r.research_role,
            horizon=r.horizon,
            research_date=r.research_date,
            data_cutoff=r.data_cutoff,
            framework_ref=r.framework_ref,
        )

    def add_evidence(self, run_id: str, items: list[EvidenceItem]) -> int:
        self.get(run_id)
        existing = {
            e.evidence_id
            for e in self.session.scalars(
                select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
            )
        }
        for it in items:
            if it.id in existing:
                raise ValueError(f"duplicate evidence id: {it.id}")
            self.session.add(
                EvidenceItemRow(
                    run_id=run_id,
                    evidence_id=it.id,
                    source_name=it.source_name,
                    source_class=it.source_class,
                    url=it.url,
                    published_date=it.published_date,
                    data_period_end=it.data_period_end,
                    accessed_at=it.accessed_at,
                    grade=it.grade,
                    content_hash=it.content_hash,
                    excerpt=it.excerpt,
                )
            )
        self.session.flush()
        return len(items)

    def add_proposals(
        self, run_id: str, proposals: list[FactorProposal], origin: str = "agent"
    ) -> None:
        self.get(run_id)
        existing = {
            p.factor
            for p in self.session.scalars(
                select(FactorProposalRow).where(FactorProposalRow.run_id == run_id)
            )
        }
        for p in proposals:
            if p.factor in existing:
                raise ValueError(f"duplicate proposal for factor {p.factor}")
            self.session.add(
                FactorProposalRow(
                    run_id=run_id,
                    factor=p.factor,
                    proposed_score=p.proposed_score,
                    rationale=p.rationale,
                    evidence_ids=p.evidence_ids,
                    counter_evidence_ids=p.counter_evidence_ids,
                    confidence=p.confidence,
                    missing_data=p.missing_data,
                    as_of_date=p.as_of_date,
                    origin=origin,
                )
            )
        self.session.flush()

    def replace_proposal_score(
        self, run_id: str, factor: str, score: float, rationale: str
    ) -> None:
        row = self.session.scalar(
            select(FactorProposalRow).where(
                FactorProposalRow.run_id == run_id, FactorProposalRow.factor == factor
            )
        )
        if row is None:
            raise LookupError(f"no proposal for factor {factor}")
        row.proposed_score = score
        row.rationale = rationale
        row.origin = "human"
        self.session.flush()

    def evidence_of(self, run_id: str) -> list[EvidenceItem]:
        rows = self.session.scalars(
            select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
        )
        return [
            EvidenceItem(
                id=r.evidence_id,
                source_name=r.source_name,
                source_class=r.source_class,
                url=r.url,
                published_date=r.published_date,
                data_period_end=r.data_period_end,
                accessed_at=r.accessed_at,
                grade=r.grade,
                content_hash=r.content_hash,
                excerpt=r.excerpt,
            )
            for r in rows
        ]

    def proposals_of(self, run_id: str) -> list[FactorProposal]:
        rows = self.session.scalars(
            select(FactorProposalRow).where(FactorProposalRow.run_id == run_id)
        )
        return [
            FactorProposal(
                factor=r.factor,
                proposed_score=r.proposed_score,
                rationale=r.rationale,
                evidence_ids=r.evidence_ids,
                counter_evidence_ids=r.counter_evidence_ids,
                confidence=r.confidence,
                missing_data=r.missing_data,
                as_of_date=r.as_of_date,
            )
            for r in rows
        ]

    def save_draft_snapshot(self, run_id: str, snapshot: ScoreSnapshot) -> None:
        self.session.add(
            ScoreSnapshotRow(
                id=_uid("snap"),
                run_id=run_id,
                snapshot_json=snapshot.model_dump(mode="json"),
                content_hash=snapshot.content_hash,
                kind="draft",
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def latest_snapshot(self, run_id: str) -> ScoreSnapshotRow | None:
        return self.session.scalar(
            select(ScoreSnapshotRow)
            .where(ScoreSnapshotRow.run_id == run_id)
            .order_by(ScoreSnapshotRow.created_at.desc())
            .limit(1)
        )

    def record_decision(
        self, run_id, action, factor, agent_score, final_score, reason, actor
    ) -> None:
        self.session.add(
            HumanDecisionRow(
                id=_uid("dec"),
                run_id=run_id,
                action=action,
                factor=factor,
                agent_score=agent_score,
                final_score=final_score,
                reason=reason,
                actor=actor,
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def create_version(self, run_id: str, idem_key: str, expected_lock: int):
        existing = self.session.scalar(
            select(ResearchVersionRow).where(
                ResearchVersionRow.idempotency_key == idem_key
            )
        )
        if existing is not None:
            return existing, False
        row = self.get(run_id)
        if row.lock_version != expected_lock:
            raise ConcurrencyError(expected_lock, row.lock_version)
        snap = self.latest_snapshot(run_id)
        if snap is None:
            raise LookupError("no draft snapshot to approve")
        count = len(
            self.session.scalars(
                select(ResearchVersionRow).where(ResearchVersionRow.run_id == run_id)
            ).all()
        )
        version = ResearchVersionRow(
            id=_uid("ver"),
            run_id=run_id,
            version_no=count + 1,
            snapshot_json=snap.snapshot_json,
            content_hash=snap.content_hash,
            idempotency_key=idem_key,
            created_at=datetime.now(UTC),
        )
        self.session.add(version)
        self.advance(run_id, RunState.APPROVED)
        return version, True
```

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
git add packages/storage
git commit -m "feat(storage): run repository with idempotency and optimistic lock"
```

---

### Task 4: fathomark-api scaffold — app factory, create/get run endpoints

**Files:**
- Create: `packages/api/pyproject.toml`
- Create: `packages/api/src/fathomark_api/__init__.py`, `schemas.py`, `app.py`, `routes/__init__.py`, `routes/runs.py`
- Create: `packages/api/tests/conftest.py`
- Test: `packages/api/tests/test_create_run.py`

**Interfaces:**
- Consumes: `RunRepository`, `create_session_factory`, `init_db`, core `ScopeSnapshot`.
- Produces:
  - `create_app(database_url: str, framework_dir: Path) -> FastAPI` (app state holds `session_factory` and `framework_dir`; `init_db` called at construction).
  - DTOs: `CreateRunRequest{symbol, exchange, research_role, horizon, research_date, data_cutoff, framework_ref}`, `RunResponse{id, state, lock_version, scope fields..., created_at, updated_at}`, `ErrorResponse{detail}`.
  - `POST /v1/research-runs` (header `Idempotency-Key` required → 400 if missing) → 201 `RunResponse`; replay → 200 same run.
  - `GET /v1/research-runs/{id}` → 200 `RunResponse`, 404 if unknown.

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/conftest.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fathomark_api import create_app

ROOT = Path(__file__).parents[3]


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
    )
    with TestClient(app) as c:
        yield c


CREATE_PAYLOAD = {
    "symbol": "ADBE",
    "exchange": "NASDAQ",
    "research_role": "core",
    "horizon": "3y",
    "research_date": "2026-09-03",
    "data_cutoff": "2026-09-03",
    "framework_ref": "common-stock@1.0.0",
}
```

```python
# packages/api/tests/test_create_run.py
from .conftest import CREATE_PAYLOAD


def test_create_run_returns_201(client):
    r = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-1"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "created" and body["symbol"] == "ADBE"
    assert body["lock_version"] == 0


def test_create_run_requires_idempotency_key(client):
    r = client.post("/v1/research-runs", json=CREATE_PAYLOAD)
    assert r.status_code == 400


def test_create_run_replay_returns_same_run(client):
    r1 = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-2"},
    )
    r2 = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-2"},
    )
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_get_unknown_run_404(client):
    assert client.get("/v1/research-runs/run_nope").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails** — `fathomark_api` missing.

- [ ] **Step 3: Implement package**

`packages/api/pyproject.toml`:

```toml
[project]
name = "fathomark-api"
version = "0.1.0"
description = "Headless REST API for Fathomark"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "fathomark-core",
    "fathomark-storage",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fathomark_api"]
```

`schemas.py`:

```python
"""API request/response DTOs."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    symbol: str
    exchange: str
    research_role: Literal["core", "offensive", "tactical"]
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str


class RunResponse(BaseModel):
    id: str
    state: str
    lock_version: int
    symbol: str
    exchange: str
    research_role: str
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str
    created_at: datetime
    updated_at: datetime


class IngestEvidenceRequest(BaseModel):
    evidence: list[dict]  # validated into core EvidenceItem in service


class IngestProposalsRequest(BaseModel):
    proposals: list[dict]


class DecisionRequest(BaseModel):
    action: Literal["accept", "modify", "return"]
    factor: str | None = None
    final_score: float | None = None
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    expected_lock_version: int


class ApproveRequest(BaseModel):
    expected_lock_version: int


class ResultResponse(BaseModel):
    run_id: str
    state: str
    snapshot: dict | None
    version: dict | None
```

`app.py`:

```python
"""FastAPI app factory."""

from pathlib import Path

from fastapi import FastAPI

from fathomark_storage import create_session_factory, init_db

from fathomark_api.routes.runs import router as runs_router


def create_app(database_url: str, framework_dir: Path) -> FastAPI:
    app = FastAPI(title="Fathomark API", version="0.1.0")
    session_factory = create_session_factory(database_url)
    init_db(session_factory)
    app.state.session_factory = session_factory
    app.state.framework_dir = framework_dir
    app.include_router(runs_router, prefix="/v1")
    return app
```

`routes/runs.py` (Task 4 portion — later tasks append routes to this file):

```python
"""Research-run endpoints."""

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage.repository import RunRepository

from fathomark_api.schemas import CreateRunRequest, RunResponse

router = APIRouter()


def _repo(request: Request) -> RunRepository:
    return RunRepository(request.app.state.session_factory())


def _run_response(row) -> RunResponse:
    return RunResponse(
        id=row.id,
        state=row.state,
        lock_version=row.lock_version,
        symbol=row.symbol,
        exchange=row.exchange,
        research_role=row.research_role,
        horizon=row.horizon,
        research_date=row.research_date,
        data_cutoff=row.data_cutoff,
        framework_ref=row.framework_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/research-runs", status_code=201)
def create_run(
    payload: CreateRunRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None),
):
    if not idempotency_key:
        return JSONResponse(
            {"detail": "Idempotency-Key header required"}, status_code=400
        )
    repo = _repo(request)
    row, created = repo.create_run(
        idem_key=idempotency_key, scope=ScopeSnapshot(**payload.model_dump())
    )
    repo.session.commit()
    response.status_code = 201 if created else 200
    return _run_response(row)


@router.get("/research-runs/{run_id}")
def get_run(run_id: str, request: Request):
    repo = _repo(request)
    try:
        return _run_response(repo.get(run_id))
    except LookupError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=404)
```

- [ ] **Step 4: Run tests, verify pass; commit**

Run: `uv run pytest packages/api/tests -q`

```bash
git add packages/api pyproject.toml uv.lock
git commit -m "feat(api): app factory with idempotent create and get run endpoints"
```

---

### Task 5: Evidence and proposal ingestion endpoints

**Files:**
- Modify: `packages/api/src/fathomark_api/routes/runs.py`
- Create: `packages/api/src/fathomark_api/services.py`
- Test: `packages/api/tests/test_ingest_and_compute.py` (ingest half)

**Interfaces:**
- Consumes: `RunRepository.add_evidence/add_proposals/advance`, core schemas.
- Produces: `RunService(session, framework_dir)` with `ingest_evidence(run_id, items) -> RunResponse`, `ingest_proposals(run_id, proposals) -> RunResponse`.
- Endpoints: `POST /v1/research-runs/{id}/evidence` (state must be `created`; on success advances to `collecting` then, when proposals land, `analyzing`); `POST /v1/research-runs/{id}/factor-proposals` (state must be `collecting`; advances to `analyzing`). 409 on wrong state, 422 on schema violation (`ProposalError`, duplicate ids).

`services.py`:

```python
"""Service layer: orchestrates repository + deterministic core."""

from pathlib import Path

from fathomark_core import EvidenceItem, FactorProposal, evaluate, load_framework
from fathomark_core.schemas import ProposalError
from fathomark_storage.repository import RunRepository
from fathomark_storage.state_machine import RunState


class StateConflict(RuntimeError):
    pass


class RunService:
    def __init__(self, repo: RunRepository, framework_dir: Path):
        self.repo = repo
        self.framework_dir = framework_dir

    def _require_state(self, run_id: str, *states: RunState):
        row = self.repo.get(run_id)
        if RunState(row.state) not in states:
            raise StateConflict(f"run {run_id} in state {row.state}")
        return row

    def ingest_evidence(self, run_id: str, items: list[EvidenceItem]) -> None:
        self._require_state(run_id, RunState.CREATED)
        self.repo.add_evidence(run_id, items)
        self.repo.advance(run_id, RunState.COLLECTING)

    def ingest_proposals(self, run_id: str, proposals: list[FactorProposal]) -> None:
        self._require_state(run_id, RunState.COLLECTING)
        self.repo.add_proposals(run_id, proposals)
        self.repo.advance(run_id, RunState.ANALYZING)
```

Route handlers validate `EvidenceItem.model_validate` / `FactorProposal.model_validate` per dict, map `StateConflict`→409, `ValueError`/`ProposalError`→422, `LookupError`→404, commit on success.

- [ ] **Steps:** failing test (POST evidence → state `collecting`; POST proposals → `analyzing`; wrong-state → 409; proposal referencing unknown evidence rejected at compute, not ingest) → implement → green → commit `feat(api): evidence and proposal ingestion endpoints`.

---

### Task 6: Compute endpoint — deterministic score → draft snapshot

**Files:**
- Modify: `packages/api/src/fathomark_api/services.py`, `routes/runs.py`
- Test: `packages/api/tests/test_ingest_and_compute.py` (compute half)

**Interfaces:**
- Produces: `RunService.compute(run_id) -> ScoreSnapshot`; `POST /v1/research-runs/{id}/compute` (state `analyzing` only) → loads `framework_dir / "common-stock.yaml"` matched against run `framework_ref`, calls `evaluate`, saves draft snapshot, advances to `draft`, returns snapshot JSON. `GET /v1/research-runs/{id}/result` → `ResultResponse` (latest draft snapshot + approved version if any).

```python
    def compute(self, run_id: str):
        row = self._require_state(run_id, RunState.ANALYZING)
        framework = load_framework(self.framework_dir / "common-stock.yaml")
        snapshot = evaluate(
            framework=framework,
            scope=self.repo.scope_of(run_id),
            evidence=self.repo.evidence_of(run_id),
            proposals=self.repo.proposals_of(run_id),
        )
        self.repo.save_draft_snapshot(run_id, snapshot)
        self.repo.advance(run_id, RunState.DRAFT)
        return snapshot
```

- [ ] **Steps:** failing test (full ADBE fixture through ingest+compute → `core.total == 85.75`, state `draft`) → implement → green → commit `feat(api): deterministic compute endpoint producing draft snapshots`.

---

### Task 7: Review decisions with optimistic lock and mandatory reasons

**Files:**
- Modify: `packages/api/src/fathomark_api/services.py`, `routes/runs.py`
- Test: `packages/api/tests/test_review_and_approve.py` (review half)

**Interfaces:**
- Produces: `RunService.review(run_id, req: DecisionRequest) -> None`; `POST /v1/research-runs/{id}/review-decisions`.
- Rules (spec §11): state must be `draft`; `expected_lock_version` must equal `lock_version` else 409; action `modify` requires `factor` + `final_score` and records agent score, final score, reason, actor; after `modify`, recompute happens by client calling `compute` again — so `modify` regresses state `draft → analyzing` via... **no**: illegal per machine. Instead `modify` updates the proposal in place and immediately re-runs `evaluate` internally, storing a new draft snapshot (state stays `draft`, `lock_version` bumps). `accept` is a no-op record. `return` moves `draft → needs_review`.

```python
def review(self, run_id: str, req) -> None:
    row = self._require_state(run_id, RunState.DRAFT)
    if row.lock_version != req.expected_lock_version:
        raise ConcurrencyError(req.expected_lock_version, row.lock_version)
    if req.action == "modify":
        if req.factor is None or req.final_score is None:
            raise ProposalError("modify requires factor and final_score")
        current = {p.factor: p for p in self.repo.proposals_of(run_id)}[req.factor]
        self.repo.record_decision(
            run_id,
            "modify",
            req.factor,
            current.proposed_score,
            req.final_score,
            req.reason,
            req.actor,
        )
        self.repo.replace_proposal_score(
            run_id, req.factor, req.final_score, req.reason
        )
        framework = load_framework(self.framework_dir / "common-stock.yaml")
        snapshot = evaluate(
            framework=framework,
            scope=self.repo.scope_of(run_id),
            evidence=self.repo.evidence_of(run_id),
            proposals=self.repo.proposals_of(run_id),
        )
        self.repo.save_draft_snapshot(run_id, snapshot)
    elif req.action == "accept":
        self.repo.record_decision(
            run_id, "accept", req.factor, None, None, req.reason, req.actor
        )
    elif req.action == "return":
        self.repo.record_decision(
            run_id, "return", None, None, None, req.reason, req.actor
        )
        self.repo.advance(run_id, RunState.NEEDS_REVIEW)
    if req.action != "return":
        self.repo.advance(run_id, RunState.DRAFT)  # bumps lock_version
```

Note: `advance(DRAFT→DRAFT)` is illegal in the machine — add repository method `touch(run_id)` that only bumps `lock_version`/`updated_at` without a transition, and use it in review's non-return path. Add `touch` test to `test_repository.py`.

- [ ] **Steps:** failing tests (modify changes snapshot and bumps lock; stale `expected_lock_version` → 409; modify without reason → 422 via DTO; return → `needs_review`; review on non-draft → 409) → implement → green → commit `feat(api): review decisions with optimistic lock and mandatory reasons`.

---

### Task 8: Approve endpoint — immutable version, idempotent

**Files:**
- Modify: `packages/api/src/fathomark_api/services.py`, `routes/runs.py`
- Test: `packages/api/tests/test_review_and_approve.py` (approve half)

**Interfaces:**
- Produces: `RunService.approve(run_id, expected_lock: int, idem_key: str, actor: str) -> tuple[ResearchVersionRow, bool]`; `POST /v1/research-runs/{id}/approve` with `Idempotency-Key` header + `ApproveRequest{expected_lock_version}`.
- Rules: state must be `draft` (replay of a consumed key short-circuits before the state check so double-approve returns 200 with the same version); records a `HumanDecision(action="approve")`; version row immutable; state → `approved`. 409 on lock mismatch or wrong state.

```python
def approve(self, run_id: str, expected_lock: int, idem_key: str, actor: str):
    replay = self.repo.find_version_by_idem(idem_key)  # add small lookup method
    if replay is not None:
        return replay, False
    self._require_state(run_id, RunState.DRAFT)
    version, _ = self.repo.create_version(run_id, idem_key, expected_lock)
    self.repo.record_decision(
        run_id, "approve", None, None, None, f"approved by {actor}", actor
    )
    return version, True
```

(Add `find_version_by_idem(idem_key) -> ResearchVersionRow | None` to repository + test.)

- [ ] **Steps:** failing tests (approve → 201 version with `content_hash`; state `approved`; replay same key → 200 same version id, no second row; stale lock → 409; approve in `analyzing` → 409; `GET /result` now returns version block) → implement → green → commit `feat(api): idempotent approve producing immutable versions`.

---

### Task 9: E2E golden test — ADBE fixture through the API

**Files:**
- Test: `packages/api/tests/test_e2e_adbe.py`

```python
import json
from pathlib import Path

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def test_adbe_fixture_create_to_approve(client):
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8")
    )

    r = client.post(
        "/v1/research-runs",
        json={**data["scope"]},
        headers={"Idempotency-Key": "e2e-create"},
    )
    assert r.status_code == 201
    run_id = r.json()["id"]

    assert (
        client.post(
            f"/v1/research-runs/{run_id}/evidence", json={"evidence": data["evidence"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/research-runs/{run_id}/factor-proposals",
            json={"proposals": data["proposals"]},
        ).status_code
        == 200
    )

    r = client.post(f"/v1/research-runs/{run_id}/compute")
    assert r.status_code == 200
    assert r.json() == expected  # same snapshot as offline core

    lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "e2e-approve"},
    )
    assert r.status_code == 201

    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    assert result["state"] == "approved"
    assert result["version"]["snapshot_json"] == expected

    # duplicate approve: same version, no new row
    r2 = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "e2e-approve"},
    )
    assert r2.status_code == 200 and r2.json()["id"] == r.json()["id"]
```

- [ ] **Steps:** run red (should pass immediately if Tasks 4–8 are exact — treat as regression gate), fix drift, commit `test(api): ADBE fixture e2e from create to approved version`.

---

### Task 10: Cancel, retry, and needs_review resolution endpoints

**Files:** Modify `services.py`, `routes/runs.py`. Test: `packages/api/tests/test_cancel_retry.py`.
- `POST /{id}/cancel` (any non-terminal state → `cancelled`; terminal → 409).
- `POST /{id}/retry` (only from `failed`, with `Idempotency-Key`; → `collecting`).
- `POST /{id}/resolve-review` (`needs_review → draft`, records decision with reason).
Commit: `feat(api): cancel, retry and review-resolution endpoints`.

### Task 11: Alembic migrations replace create_all

**Files:** Create `packages/storage/alembic/`, `alembic.ini`; modify `database.py`.
- `alembic init`, autogenerate baseline migration from `Base.metadata`, `init_db` becomes `upgrade head` when `FATHOMARK_MIGRATE=1`, tests keep `create_all`.
- Test: migration upgrades an empty SQLite file to the same schema as `create_all` (compare `PRAGMA table_info`).
Commit: `feat(storage): alembic baseline migration`.

### Task 12: PostgreSQL compatibility check

**Files:** Test: `packages/storage/tests/test_postgres.py` (marked `skipif` when no `PG_TEST_URL` env).
- Same repository suite against PostgreSQL when available; CI runs SQLite only.
- Fix any non-portable SQL surfaced (expect none — types already portable).
Commit: `test(storage): optional PostgreSQL integration path`.

### Task 13: Versioned OpenAPI snapshot + Python SDK

**Files:** Create `packages/sdk/` (`fathomark-sdk`: `FathomarkClient` wrapping httpx for the 8 endpoints), `docs/api/openapi-v1.json`.
- Script dumps `app.openapi()` to `docs/api/openapi-v1.json`; test asserts committed file matches generated spec (drift = CI failure).
- SDK methods mirror endpoints; contract test runs SDK against TestClient transport.
Commit: `feat(sdk): python client and pinned OpenAPI document`.

### Task 14: HMAC webhooks with replay protection

**Files:** Create `packages/api/src/fathomark_api/webhooks.py`. Test: `packages/api/tests/test_webhooks.py`.
- `WebhookDispatcher(secret, sender)`; signs `timestamp.body` with HMAC-SHA256; receiver-side `verify(signature, timestamp, body, tolerance=300s)`; events fired on `needs_review`, `approved`, `failed`.
- Test: signature round-trip, expired timestamp rejected, tampered body rejected.
Commit: `feat(api): HMAC-signed webhooks with replay protection`.

### Task 15: TODO.md M2 checkboxes + README status

- Mark M2 items done in `TODO.md`, update README milestone table.
Commit: `docs: mark M2 complete in TODO and README`.

---

## Self-Review Notes

- **Spec coverage:** §7 models → Tasks 1/3 (ProviderRun/MetricObservation/ReviewIssue/Artifact tables deferred: they carry no data until M3/M4; noted in TODO). §9 state machine → Task 2. §10 endpoints → Tasks 4–10 (artifact download + frameworks list land with M4/Task 13). §14 idempotency/retry → Tasks 3/8/10. Optimistic lock §10 → Tasks 3/7/8. OpenAPI+SDK → Task 13. Webhooks → Task 14. Dual DB → Tasks 11–12.
- **Type consistency:** `RunService` methods consume/produce exactly the repository signatures from Task 3. `touch()` and `find_version_by_idem()` are defined in Tasks 7/8 with matching repository additions.
- **Deviation (documented):** scope stored as columns on `research_runs` (frozen at creation = ScopeSnapshot); `scoped`/`auditing` states reserved for M3 orchestration; Alembic lands after SQLite-first slice (Task 11).
