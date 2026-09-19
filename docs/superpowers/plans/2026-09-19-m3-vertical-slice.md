# M3 Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** First verifiable M3 slice — Provider protocol, fake/recording providers, step-level run records with idempotent resume, Scope Agent, Financial Agent, DAG-ready Orchestrator — driving a fixed ADBE fixture from run creation to `draft` fully offline.

**Architecture:** Two new packages: `fathomark-providers` (LLM/Evidence provider protocols, Fake/Replay/Recording LLM providers, fixture evidence provider) and `fathomark-agents` (agent contracts, repair loop, ScopeAgent, FinancialAgent, FixtureReplayAgent stub for the 9 unimplemented factors, Orchestrator). Storage gains a `step_runs` table (migration 0002) recording per-step input hash, provider identity, status and retries — the resume anchor. API gains `POST /v1/research-runs/{id}/execute` running the orchestrator synchronously. No LangGraph/CrewAI/AutoGen.

**Tech Stack:** Python 3.12, Pydantic 2, SQLAlchemy 2, Alembic, FastAPI, pytest, uv workspace + hatchling.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` (sections 5, 6, 7, 9, 13, 14, 16.2, 16.3); `TODO.md` section 3.

## Global Constraints

- Python `>=3.12`; uv workspace, hatchling backend; ruff lint+format clean.
- `core` 不依赖 LLM SDK、数据库、Web 框架或网络 (design §3) — new packages depend on `fathomark-core`, never vice versa.
- 首版使用项目自有的显式状态机，不引入 LangGraph、CrewAI、AutoGen (design §4).
- Agent 不能直接写数据库，只能返回经过 Schema 约束的数据 (design §3) — agents return Pydantic models; orchestrator persists.
- Agent 输出不符合 Schema 时最多执行两次结构修复，仍失败则进入 `needs_review` (design §14).
- Provider 失败必须显式进入 `failed` 或 `needs_review`，绝不伪造完整结果。
- 超过数据截止日的资料不进入当次评分 (design §14).
- CI 不使用真实密钥或实时网络 (design §20) — all tests offline, ADBE fixture only.
- 不允许 LLM 直接决定最终加权总分或评级映射 (TODO §7) — agents only propose factor scores; `evaluate()` computes.
- Portable column types only (SQLite + PostgreSQL), matching `models.py` docstring.
- Existing workspace modifications (`docs/design/...` diff) must be preserved; do not revert.

## Acceptance Criteria (slice complete when all pass)

1. `pytest` full suite green, `ruff check .` and `ruff format --check .` clean.
2. Offline e2e: create ADBE run via API → `POST execute` → state `draft`, and `GET result` snapshot deep-equals `examples/fixtures/adbe_2026-09-03/expected_snapshot.json` (same content_hash).
3. Crash recovery: kill a run mid-pipeline (provider error at `financial` step → state `failed` with error recorded); re-`execute` with fixed provider → `draft`; `scope`/`collect` steps NOT re-run (step records show attempt unchanged, no duplicate evidence/proposals).
4. Repair loop: Financial Agent receiving malformed JSON repairs at most twice; on third failure run goes `needs_review` and no proposal is written.
5. Strict validation: agent output referencing nonexistent evidence id, or evidence published after `data_cutoff`, is rejected (ProposalError → repair; fixture replay path → run `failed`).
6. Provider failure (cassette miss / ProviderError) → run `failed` with `error` populated, or `needs_review` for agent-output failures; never silent.
7. `step_runs` rows exist for every executed step with input_hash, provider name/version, status, attempts; alembic migration 0002 reproduces `create_all` schema.
8. TODO.md M3 checkboxes updated to reflect exactly what this slice delivers; README status synced.

## File Structure

```
packages/providers/                          # NEW package fathomark-providers
  pyproject.toml
  src/fathomark_providers/__init__.py        # re-exports
  src/fathomark_providers/llm.py             # LLMRequest/LLMResponse/LLMProvider/ProviderError/prompt_key
  src/fathomark_providers/fake.py            # FakeLLMProvider (queue), ReplayLLMProvider (cassette), RecordingLLMProvider
  src/fathomark_providers/evidence.py        # EvidenceProvider protocol, FixtureEvidenceProvider
  tests/test_llm_providers.py
  tests/test_fixture_evidence.py
packages/agents/                             # NEW package fathomark-agents
  pyproject.toml
  src/fathomark_agents/__init__.py           # re-exports
  src/fathomark_agents/contracts.py          # AgentError, AgentServices
  src/fathomark_agents/repair.py             # complete_with_repairs()
  src/fathomark_agents/scope_agent.py        # ScopeAgent
  src/fathomark_agents/financial_agent.py    # FinancialAgent, FINANCIAL_FACTORS, build_prompt
  src/fathomark_agents/fixture_agent.py      # FixtureReplayAgent
  src/fathomark_agents/orchestrator.py       # StepSpec, Orchestrator, build_default_steps
  tests/conftest.py                          # fixture dir paths, db session, seeded run helpers
  tests/test_scope_agent.py
  tests/test_financial_agent.py
  tests/test_fixture_agent.py
  tests/test_orchestrator.py
packages/storage/src/fathomark_storage/models.py       # + StepRunRow
packages/storage/src/fathomark_storage/repository.py   # + step record methods
packages/storage/alembic/versions/0002_step_runs.py    # NEW
packages/storage/tests/test_step_runs.py               # NEW
packages/storage/tests/test_alembic.py                 # EXPECTED_TABLES += step_runs
packages/api/src/fathomark_api/app.py                  # + orchestrator_factory param
packages/api/src/fathomark_api/routes/runs.py          # + POST /execute
packages/api/tests/test_execute_adbe.py                # NEW offline e2e
docs/api/openapi-v1.json                               # regenerated (script scripts/dump_openapi.py)
examples/fixtures/adbe_2026-09-03/provider_dump.json   # NEW evidence w/ excerpts
examples/fixtures/adbe_2026-09-03/stub_proposals.json  # NEW 9 non-financial factors
examples/fixtures/adbe_2026-09-03/llm_cassette.json    # NEW recorded financial response
pyproject.toml                                         # workspace deps += providers, agents
TODO.md / README.md / README.zh-CN.md                  # status sync
```

---

### Task 1: fathomark-providers package — LLM protocol, errors, prompt hashing

**Files:**
- Create: `packages/providers/pyproject.toml`
- Create: `packages/providers/src/fathomark_providers/__init__.py`
- Create: `packages/providers/src/fathomark_providers/llm.py`
- Test: `packages/providers/tests/test_llm_providers.py`
- Modify: `pyproject.toml` (root — add workspace deps)

**Interfaces:**
- Produces: `LLMRequest(prompt: str, schema_name: str, max_tokens: int = 2048)`, `LLMResponse(text: str, model: str, prompt_tokens: int = 0, completion_tokens: int = 0)`, `ProviderError(message, *, retriable: bool = False)`, `LLMProvider` Protocol (`name: str`, `version: str`, `complete(request) -> LLMResponse`), `prompt_key(prompt: str) -> str` returning `"sha256:<hex>"`.

- [ ] **Step 1: Create package skeleton**

`packages/providers/pyproject.toml`:

```toml
[project]
name = "fathomark-providers"
version = "0.1.0"
description = "LLM and data provider protocols and test doubles for Fathomark"
requires-python = ">=3.12"
dependencies = ["fathomark-core"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fathomark_providers"]

[tool.uv.sources]
fathomark-core = { workspace = true }
```

Root `pyproject.toml`: add `"fathomark-providers"` and `"fathomark-agents"` to `dependencies` and `[tool.uv.sources]` (both `{ workspace = true }`). `packages/*` glob already covers workspace members. Then `uv sync`.

- [ ] **Step 2: Write the failing test**

```python
# packages/providers/tests/test_llm_providers.py
import pytest

from fathomark_providers import LLMRequest, ProviderError, prompt_key


def test_prompt_key_is_stable_and_content_addressed():
    k1 = prompt_key("hello")
    k2 = prompt_key("hello")
    assert k1 == k2
    assert k1.startswith("sha256:")
    assert prompt_key("other") != k1


def test_provider_error_carries_retriable_flag():
    err = ProviderError("boom", retriable=True)
    assert err.retriable is True
    assert ProviderError("x").retriable is False


def test_llm_request_defaults():
    req = LLMRequest(prompt="p", schema_name="factor_proposals")
    assert req.max_tokens == 2048
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest packages/providers/tests/test_llm_providers.py -v`
Expected: FAIL (ModuleNotFoundError: fathomark_providers)

- [ ] **Step 4: Implement `llm.py` and `__init__.py`**

```python
# packages/providers/src/fathomark_providers/llm.py
"""Generic LLM provider protocol. No SDK imports — adapters live elsewhere."""

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Provider call failed. retriable=True means the host may retry the step."""

    def __init__(self, message: str, *, retriable: bool = False):
        super().__init__(message)
        self.retriable = retriable


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    schema_name: str
    max_tokens: int = 2048


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    version: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


def prompt_key(prompt: str) -> str:
    """Content-addressed cassette key for a prompt."""
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
```

```python
# packages/providers/src/fathomark_providers/__init__.py
"""Provider protocols and offline test doubles."""

from fathomark_providers.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    prompt_key,
)

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderError",
    "prompt_key",
]
```

- [ ] **Step 5: Run tests, verify pass; commit**

Run: `pytest packages/providers/tests/test_llm_providers.py -v` → PASS

```bash
git add packages/providers pyproject.toml uv.lock
git commit -m "feat(providers): LLM provider protocol and content-addressed prompt keys"
```

---

### Task 2: Fake, Replay and Recording LLM providers

**Files:**
- Create: `packages/providers/src/fathomark_providers/fake.py`
- Test: `packages/providers/tests/test_llm_providers.py` (extend)

**Interfaces:**
- Consumes: Task 1 `LLMRequest/LLMResponse/ProviderError/prompt_key`.
- Produces: `FakeLLMProvider(responses: Iterable[str | Exception], *, name="fake", version="0")` — pops one per `complete`, records requests in `.requests: list[LLMRequest]`; `ReplayLLMProvider(cassette_path: Path, *, name="replay", version="0")` — lookup by `prompt_key`, miss raises `ProviderError("cassette miss: <key>", retriable=False)`; `RecordingLLMProvider(inner: LLMProvider, cassette_path: Path)` — forwards, writes `{key: text}` JSON.

- [ ] **Step 1: Extend the failing tests**

```python
import json

from fathomark_providers import (
    FakeLLMProvider,
    LLMRequest,
    ProviderError,
    RecordingLLMProvider,
    ReplayLLMProvider,
)

REQ = LLMRequest(prompt="p1", schema_name="s")


def test_fake_provider_pops_queue_and_records_requests():
    fake = FakeLLMProvider(["one", "two"])
    assert fake.complete(REQ).text == "one"
    assert fake.complete(LLMRequest(prompt="p2", schema_name="s")).text == "two"
    assert [r.prompt for r in fake.requests] == ["p1", "p2"]


def test_fake_provider_raises_scripted_error():
    fake = FakeLLMProvider([ProviderError("down", retriable=True)])
    with pytest.raises(ProviderError):
        fake.complete(REQ)


def test_fake_provider_exhausted_queue_raises():
    fake = FakeLLMProvider([])
    with pytest.raises(ProviderError, match="exhausted"):
        fake.complete(REQ)


def test_replay_provider_hit_and_miss(tmp_path):
    cassette = tmp_path / "c.json"
    cassette.write_text(json.dumps({prompt_key("p1"): "canned"}), encoding="utf-8")
    replay = ReplayLLMProvider(cassette)
    assert replay.complete(REQ).text == "canned"
    with pytest.raises(ProviderError, match="cassette miss"):
        replay.complete(LLMRequest(prompt="unknown", schema_name="s"))


def test_recording_provider_roundtrip(tmp_path):
    cassette = tmp_path / "c.json"
    recorder = RecordingLLMProvider(FakeLLMProvider(["fresh"]), cassette)
    assert recorder.complete(REQ).text == "fresh"
    replay = ReplayLLMProvider(cassette)
    assert replay.complete(REQ).text == "fresh"
    assert replay.name == recorder.name
    assert replay.version == recorder.version
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest packages/providers/tests/test_llm_providers.py -v`
Expected: FAIL (ImportError: cannot import name 'FakeLLMProvider')

- [ ] **Step 3: Implement `fake.py`**

```python
# packages/providers/src/fathomark_providers/fake.py
"""Offline LLM doubles: scripted fake, hash cassette replay, recorder."""

import json
from collections.abc import Iterable
from pathlib import Path

from fathomark_providers.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    prompt_key,
)


class FakeLLMProvider:
    """Queue-scripted provider for unit tests. Never touches network."""

    def __init__(
        self,
        responses: Iterable[str | Exception],
        *,
        name: str = "fake",
        version: str = "0",
    ):
        self._responses = list(responses)
        self.name = name
        self.version = version
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise ProviderError("fake provider queue exhausted", retriable=False)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(text=item, model=f"{self.name}-{self.version}")


class ReplayLLMProvider:
    """Replays recorded responses keyed by prompt content hash."""

    def __init__(
        self, cassette_path: Path, *, name: str = "replay", version: str = "0"
    ):
        self.name = name
        self.version = version
        self._cassette: dict[str, str] = json.loads(
            Path(cassette_path).read_text(encoding="utf-8")
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        key = prompt_key(request.prompt)
        try:
            text = self._cassette[key]
        except KeyError:
            raise ProviderError(f"cassette miss: {key}", retriable=False) from None
        return LLMResponse(text=text, model=f"{self.name}-{self.version}")


class RecordingLLMProvider:
    """Wraps a live provider and records responses into a cassette file."""

    def __init__(self, inner: LLMProvider, cassette_path: Path):
        self._inner = inner
        self._path = Path(cassette_path)
        self.name = inner.name
        self.version = inner.version

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self._inner.complete(request)
        cassette = {}
        if self._path.exists():
            cassette = json.loads(self._path.read_text(encoding="utf-8"))
        cassette[prompt_key(request.prompt)] = response.text
        self._path.write_text(
            json.dumps(cassette, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        return response
```

Update `__init__.py` to also export the three classes.

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
git add packages/providers
git commit -m "feat(providers): fake, replay and recording LLM providers"
```

---

### Task 3: EvidenceProvider protocol + FixtureEvidenceProvider

**Files:**
- Create: `packages/providers/src/fathomark_providers/evidence.py`
- Create: `examples/fixtures/adbe_2026-09-03/provider_dump.json`
- Test: `packages/providers/tests/test_fixture_evidence.py`

**Interfaces:**
- Produces: `EvidenceProvider` Protocol (`name`, `version`, `fetch(scope: ScopeSnapshot) -> list[EvidenceItem]`); `FixtureEvidenceProvider(dump_path: Path, *, name="fixture-edgar", version="1.0.0")` reading `{"evidence": [...]}`.
- Note: cutoff filtering is the orchestrator's job (Task 7), not the provider's — provider returns raw fixture rows verbatim.

- [ ] **Step 1: Write the failing test**

```python
# packages/providers/tests/test_fixture_evidence.py
from datetime import date
from pathlib import Path

from fathomark_core.schemas import ScopeSnapshot

from fathomark_providers import FixtureEvidenceProvider

ROOT = Path(__file__).parents[3]

SCOPE = ScopeSnapshot(
    symbol="ADBE",
    exchange="NASDAQ",
    research_role="core",
    horizon="5-10y",
    research_date=date(2026, 9, 3),
    data_cutoff=date(2026, 9, 3),
    framework_ref="common-stock@1.0.0",
)


def test_fixture_provider_returns_typed_evidence():
    provider = FixtureEvidenceProvider(
        ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "provider_dump.json"
    )
    items = provider.fetch(SCOPE)
    assert {e.id for e in items} == {"ev_001", "ev_002"}
    assert all(e.excerpt for e in items)  # dump carries excerpts unlike input.json
    assert provider.name == "fixture-edgar"
```

- [ ] **Step 2: Run test to verify it fails** → ImportError.

- [ ] **Step 3: Implement `evidence.py` + fixture dump**

```python
# packages/providers/src/fathomark_providers/evidence.py
"""Data-provider protocol and fixture-backed evidence provider."""

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot


@runtime_checkable
class EvidenceProvider(Protocol):
    name: str
    version: str

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]: ...


class FixtureEvidenceProvider:
    """Reads recorded evidence from a JSON dump. Offline; for CI and demos."""

    def __init__(
        self, dump_path: Path, *, name: str = "fixture-edgar", version: str = "1.0.0"
    ):
        self.name = name
        self.version = version
        self._dump_path = Path(dump_path)

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]:
        raw = json.loads(self._dump_path.read_text(encoding="utf-8"))
        return [EvidenceItem.model_validate(e) for e in raw["evidence"]]
```

`provider_dump.json` = the two `input.json` evidence rows with real-ish excerpts added (excerpt ≤ 300 chars each, e.g. 10-Q revenue/FCF figures for ev_002, press-release highlights for ev_001). Same ids, dates, grades, hashes as `input.json` so golden proposals still validate.

Export both from `__init__.py`.

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
git add packages/providers examples/fixtures/adbe_2026-09-03/provider_dump.json
git commit -m "feat(providers): evidence provider protocol with ADBE fixture dump"
```

---

### Task 4: step_runs table, migration 0002, repository methods

**Files:**
- Modify: `packages/storage/src/fathomark_storage/models.py` (append `StepRunRow`)
- Modify: `packages/storage/src/fathomark_storage/repository.py` (append methods)
- Create: `packages/storage/alembic/versions/0002_step_runs.py`
- Modify: `packages/storage/tests/test_alembic.py` (`EXPECTED_TABLES` += `"step_runs"`)
- Test: `packages/storage/tests/test_step_runs.py`

**Interfaces:**
- Produces (used by orchestrator):
  - `repo.step_record(run_id: str, step: str) -> StepRunRow | None`
  - `repo.begin_step(run_id, step, input_hash, provider_name=None, provider_version=None) -> StepRunRow` — new row (attempt=1, status `running`) or reset existing (attempt+=1, status `running`, error cleared)
  - `repo.finish_step(run_id, step, output: dict) -> None` — status `succeeded`, sets finished_at/output_json
  - `repo.fail_step(run_id, step, error: str) -> None` — status `failed`, sets finished_at/error
  - `repo.steps_of(run_id) -> list[StepRunRow]`
- Row: `StepRunRow(run_id FK, step String(40), status String(16), attempt Integer, provider_name String(80)|None, provider_version String(40)|None, input_hash String(80), output_json JSON|None, error Text|None, started_at, finished_at|None)`, `UniqueConstraint("run_id", "step")`.

- [ ] **Step 1: Write the failing test**

```python
# packages/storage/tests/test_step_runs.py
from datetime import date

from fathomark_core.schemas import ScopeSnapshot

from fathomark_storage.database import create_session_factory, init_db
from fathomark_storage.repository import RunRepository


def _repo(tmp_path):
    factory = create_session_factory(f"sqlite:///{tmp_path}/t.db")
    init_db(factory)
    repo = RunRepository(factory())
    scope = ScopeSnapshot(
        symbol="ADBE",
        exchange="NASDAQ",
        research_role="core",
        horizon="5-10y",
        research_date=date(2026, 9, 3),
        data_cutoff=date(2026, 9, 3),
        framework_ref="common-stock@1.0.0",
    )
    row, _ = repo.create_run(idem_key="k1", scope=scope)
    return repo, row.id


def test_step_lifecycle(tmp_path):
    repo, run_id = _repo(tmp_path)
    assert repo.step_record(run_id, "scope") is None
    rec = repo.begin_step(
        run_id, "scope", "sha256:abc", provider_name="scope-agent", provider_version="1"
    )
    assert rec.status == "running" and rec.attempt == 1
    repo.finish_step(run_id, "scope", {"frozen": True})
    rec = repo.step_record(run_id, "scope")
    assert rec.status == "succeeded" and rec.output_json == {"frozen": True}
    assert rec.finished_at is not None


def test_begin_step_retries_increment_attempt(tmp_path):
    repo, run_id = _repo(tmp_path)
    repo.begin_step(run_id, "collect", "sha256:abc")
    repo.fail_step(run_id, "collect", "provider down")
    rec = repo.begin_step(run_id, "collect", "sha256:abc")
    assert rec.attempt == 2 and rec.status == "running" and rec.error is None
    assert len(repo.steps_of(run_id)) == 1  # upsert, not duplicate
```

- [ ] **Step 2: Run test to verify it fails** → AttributeError / missing table.

- [ ] **Step 3: Implement model + repository + migration**

Model (append to models.py):

```python
class StepRunRow(Base):
    __tablename__ = "step_runs"
    __table_args__ = (UniqueConstraint("run_id", "step"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    step: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))  # running | succeeded | failed
    attempt: Mapped[int] = mapped_column(Integer)
    provider_name: Mapped[str | None] = mapped_column(String(80))
    provider_version: Mapped[str | None] = mapped_column(String(40))
    input_hash: Mapped[str] = mapped_column(String(80))
    output_json: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
```

Repository (append to RunRepository):

```python
def step_record(self, run_id: str, step: str) -> StepRunRow | None:
    return self.session.scalar(
        select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.step == step)
    )


def begin_step(
    self, run_id, step, input_hash, provider_name=None, provider_version=None
) -> StepRunRow:
    self.get(run_id)
    rec = self.step_record(run_id, step)
    now = datetime.now(UTC)
    if rec is None:
        rec = StepRunRow(
            run_id=run_id,
            step=step,
            status="running",
            attempt=1,
            provider_name=provider_name,
            provider_version=provider_version,
            input_hash=input_hash,
            output_json=None,
            error=None,
            started_at=now,
            finished_at=None,
        )
        self.session.add(rec)
    else:
        rec.status = "running"
        rec.attempt += 1
        rec.provider_name = provider_name
        rec.provider_version = provider_version
        rec.input_hash = input_hash
        rec.output_json = None
        rec.error = None
        rec.started_at = now
        rec.finished_at = None
    self.session.flush()
    return rec


def finish_step(self, run_id: str, step: str, output: dict) -> None:
    rec = self.step_record(run_id, step)
    assert rec is not None and rec.status == "running"
    rec.status = "succeeded"
    rec.output_json = output
    rec.finished_at = datetime.now(UTC)
    self.session.flush()


def fail_step(self, run_id: str, step: str, error: str) -> None:
    rec = self.step_record(run_id, step)
    assert rec is not None and rec.status == "running"
    rec.status = "failed"
    rec.error = error
    rec.finished_at = datetime.now(UTC)
    self.session.flush()


def steps_of(self, run_id: str) -> list[StepRunRow]:
    return list(
        self.session.scalars(select(StepRunRow).where(StepRunRow.run_id == run_id))
    )
```

Migration: generate via `alembic revision --autogenerate` against a baseline-upgraded SQLite db, verify it creates exactly `step_runs`, save as `0002_step_runs.py` (revision "0002", down_revision "0001"). Update `test_alembic.py` EXPECTED_TABLES to include `"step_runs"`.

- [ ] **Step 4: Run storage tests (incl. alembic parity), verify pass; commit**

Run: `pytest packages/storage -v` → all PASS.

```bash
git add packages/storage
git commit -m "feat(storage): step_runs table for step-level records and resume"
```

---

### Task 5: fathomark-agents package — contracts, repair loop, ScopeAgent

**Files:**
- Create: `packages/agents/pyproject.toml`
- Create: `packages/agents/src/fathomark_agents/__init__.py`
- Create: `packages/agents/src/fathomark_agents/contracts.py`
- Create: `packages/agents/src/fathomark_agents/repair.py`
- Create: `packages/agents/src/fathomark_agents/scope_agent.py`
- Test: `packages/agents/tests/test_scope_agent.py`, `packages/agents/tests/conftest.py`

**Interfaces:**
- Produces:
  - `AgentError(RuntimeError)` — output invalid after all repairs.
  - `complete_with_repairs(llm: LLMProvider, prompt: str, schema_name: str, parse_validate: Callable[[str], T], max_repairs: int = 2) -> T` — on exception from parse_validate, re-prompts with `\n\nERROR: <err>\nFix and return corrected JSON only.` appended; raises AgentError after `1 + max_repairs` attempts.
  - `ScopeAgent(name="scope-agent", version="1.0.0")` with `run(repo: RunRepository, run_id: str) -> ScopeSnapshot` — reads run row, returns frozen ScopeSnapshot (deterministic, no LLM).

pyproject deps: `fathomark-core`, `fathomark-storage`, `fathomark-providers`.

- [ ] **Step 1: Write failing tests**

```python
# packages/agents/tests/test_scope_agent.py
import pytest
from fathomark_core.schemas import ScopeSnapshot
from fathomark_providers import FakeLLMProvider, LLMResponse, ProviderError

from fathomark_agents import AgentError, ScopeAgent, complete_with_repairs


def test_scope_agent_freezes_contract(seeded_run):
    repo, run_id = seeded_run
    scope = ScopeAgent().run(repo, run_id)
    assert isinstance(scope, ScopeSnapshot)
    assert scope.symbol == "ADBE" and scope.framework_ref == "common-stock@1.0.0"


def test_repair_loop_succeeds_on_second_attempt():
    llm = FakeLLMProvider(["not json", '{"ok": true}'])
    result = complete_with_repairs(llm, "prompt", "test", lambda text: _parse(text))
    assert result == {"ok": True}
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt


def test_repair_loop_exhausted_raises_agent_error():
    llm = FakeLLMProvider(["bad", "bad", "bad"])
    with pytest.raises(AgentError):
        complete_with_repairs(llm, "p", "test", _parse)
    assert len(llm.requests) == 3  # initial + 2 repairs, no more


def _parse(text):
    import json

    return json.loads(text)
```

conftest `seeded_run` fixture: sqlite tmp session + one created ADBE run (same pattern as storage test).

- [ ] **Step 2: Run to verify fail** → ImportError.

- [ ] **Step 3: Implement**

```python
# packages/agents/src/fathomark_agents/contracts.py
"""Shared agent contracts."""


class AgentError(RuntimeError):
    """Agent output failed validation after all repair attempts."""
```

```python
# packages/agents/src/fathomark_agents/repair.py
"""Structured-output repair loop. Max two repairs per design §14."""

from collections.abc import Callable
from typing import TypeVar

from fathomark_providers import LLMProvider, LLMRequest

from fathomark_agents.contracts import AgentError

T = TypeVar("T")


def complete_with_repairs(
    llm: LLMProvider,
    prompt: str,
    schema_name: str,
    parse_validate: Callable[[str], T],
    max_repairs: int = 2,
) -> T:
    attempt_prompt = prompt
    last_error: Exception | None = None
    for _ in range(1 + max_repairs):
        response = llm.complete(
            LLMRequest(prompt=attempt_prompt, schema_name=schema_name)
        )
        try:
            return parse_validate(response.text)
        except Exception as exc:  # parse or contract failure → repair
            last_error = exc
            attempt_prompt = (
                f"{prompt}\n\nERROR: {exc}\nFix and return corrected JSON only."
            )
    raise AgentError(f"output invalid after {max_repairs} repairs: {last_error}")
```

```python
# packages/agents/src/fathomark_agents/scope_agent.py
"""Scope Agent: freezes the research contract (design §5.1). Deterministic."""

from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage.repository import RunRepository


class ScopeAgent:
    name = "scope-agent"
    version = "1.0.0"

    def run(self, repo: RunRepository, run_id: str) -> ScopeSnapshot:
        return repo.scope_of(run_id)
```

`__init__.py` exports: AgentError, ScopeAgent, complete_with_repairs.

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
git add packages/agents pyproject.toml uv.lock
git commit -m "feat(agents): contracts, repair loop, scope agent"
```

---

### Task 6: FinancialAgent + cassette + strict validation

**Files:**
- Create: `packages/agents/src/fathomark_agents/financial_agent.py`
- Create: `examples/fixtures/adbe_2026-09-03/llm_cassette.json`
- Test: `packages/agents/tests/test_financial_agent.py`

**Interfaces:**
- Produces:
  - `FINANCIAL_FACTORS = ("financial_health", "earnings_quality")`
  - `build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem]) -> str` — deterministic: instruction header + canonical `json.dumps(..., sort_keys=True, ensure_ascii=False)` of scope and evidence (id, source_name, dates, grade, excerpt).
  - `FinancialAgent(llm: LLMProvider, max_repairs: int = 2)` with `name="financial-agent"`, `version="1.0.0"`, `run(*, scope, framework, evidence) -> list[FactorProposal]`.
  - Response contract: `{"proposals": [ <FactorProposal fields> ]}`; each validated by `validate_proposal(framework=framework, evidence={id: published_date}, data_cutoff=scope.data_cutoff)` plus factor membership in FINANCIAL_FACTORS (agent must not speak for other factors).

- [ ] **Step 1: Write failing tests**

```python
# packages/agents/tests/test_financial_agent.py
import json
from pathlib import Path

import pytest
from fathomark_core import load_framework
from fathomark_providers import FakeLLMProvider, ReplayLLMProvider

from fathomark_agents import AgentError, FinancialAgent
from fathomark_agents.financial_agent import FINANCIAL_FACTORS, build_prompt

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
    good = (FIXTURE / "financial_response.json").read_text()  # see step 3
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
```

`scope`/`evidence`/`framework` fixtures in agents conftest: scope from `input.json`, evidence from `provider_dump.json`, framework loaded once.

- [ ] **Step 2: Run to verify fail** → ImportError.

- [ ] **Step 3: Implement `financial_agent.py`**

```python
"""Financial Agent: financial_health + earnings_quality proposals (design §5.3)."""

import json

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)
from fathomark_providers import LLMProvider

from fathomark_agents.repair import complete_with_repairs

FINANCIAL_FACTORS = ("financial_health", "earnings_quality")

_INSTRUCTIONS = """You are the Financial Agent for an equity research pipeline.
Return JSON {"proposals": [...]} proposing scores for exactly these factors:
financial_health, earnings_quality.
Each proposal: factor, proposed_score (0-10, 0.5 steps), rationale,
evidence_ids, counter_evidence_ids, confidence (high|medium|low|insufficient),
missing_data, as_of_date. Only cite evidence ids listed below. Never cite
evidence published after the data cutoff. Return JSON only.

INPUT:
"""


def build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem]) -> str:
    payload = {
        "scope": json.loads(scope.model_dump_json()),
        "evidence": [
            {
                "id": e.id,
                "source_name": e.source_name,
                "source_class": e.source_class,
                "published_date": e.published_date.isoformat(),
                "data_period_end": e.data_period_end.isoformat()
                if e.data_period_end
                else None,
                "grade": e.grade,
                "excerpt": e.excerpt,
            }
            for e in sorted(evidence, key=lambda e: e.id)
        ],
    }
    return _INSTRUCTIONS + json.dumps(payload, sort_keys=True, ensure_ascii=False)


class FinancialAgent:
    name = "financial-agent"
    version = "1.0.0"

    def __init__(self, llm: LLMProvider, max_repairs: int = 2):
        self.llm = llm
        self.max_repairs = max_repairs

    def run(
        self,
        *,
        scope: ScopeSnapshot,
        framework: Framework,
        evidence: list[EvidenceItem],
    ) -> list[FactorProposal]:
        evidence_index = {e.id: e.published_date for e in evidence}

        def parse_validate(text: str) -> list[FactorProposal]:
            raw = json.loads(text)
            proposals = [FactorProposal.model_validate(p) for p in raw["proposals"]]
            if not proposals:
                raise ValueError("no proposals returned")
            for p in proposals:
                if p.factor not in FINANCIAL_FACTORS:
                    raise ValueError(f"financial agent may not propose {p.factor}")
                validate_proposal(
                    p,
                    framework=framework,
                    evidence=evidence_index,
                    data_cutoff=scope.data_cutoff,
                )
            return proposals

        return complete_with_repairs(
            self.llm,
            build_prompt(scope, evidence),
            "factor_proposals",
            parse_validate,
            self.max_repairs,
        )
```

- [ ] **Step 4: Generate the cassette (recorded, committed)**

Write `examples/fixtures/adbe_2026-09-03/financial_response.json` — `{"proposals": [...]}` with the two golden financial proposals verbatim from `input.json`. Then a throwaway script (not committed) records:

```python
from pathlib import Path
from fathomark_providers import FakeLLMProvider, RecordingLLMProvider
from fathomark_agents.financial_agent import build_prompt
# scope/evidence loaded from fixtures; prompt = build_prompt(scope, evidence)
# RecordingLLMProvider(FakeLLMProvider([response_text]), FIXTURE/"llm_cassette.json").complete(LLMRequest(prompt=prompt, schema_name="factor_proposals"))
```

Commit `llm_cassette.json` + `financial_response.json`. Cassette key must match `build_prompt` output exactly — if prompt builder changes, re-record (test 1 fails loudly on drift, by design).

- [ ] **Step 5: Run tests, verify pass; commit**

```bash
git add packages/agents examples/fixtures/adbe_2026-09-03
git commit -m "feat(agents): financial agent with cassette replay and strict validation"
```

---

### Task 7: FixtureReplayAgent (stub for 9 unimplemented specialist agents)

**Files:**
- Create: `packages/agents/src/fathomark_agents/fixture_agent.py`
- Create: `examples/fixtures/adbe_2026-09-03/stub_proposals.json`
- Test: `packages/agents/tests/test_fixture_agent.py`

**Interfaces:**
- Produces: `FixtureReplayAgent(stub_path: Path, factors: tuple[str, ...], *, name="fixture-replay-agent", version="1.0.0")` with `run(*, scope, framework, evidence) -> list[FactorProposal]`. Reads `{"proposals": [...]}`, keeps only its `factors`, applies the SAME `validate_proposal` contract (no fixture bypass). Validation failure raises `ValueError` (orchestrator treats as run failure — recorded fixture must be valid).

Rationale (document in module docstring): pipeline must reach `draft` with all 11 framework factors; only Scope+Financial agents exist in this slice, so remaining 9 factors replay golden proposals, persisted with `origin="fixture"` and visibly distinct from real agent output.

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run to verify fail** → ImportError.

- [ ] **Step 3: Implement + write `stub_proposals.json`** (9 non-financial proposals copied verbatim from `input.json`).

```python
"""Fixture replay stub for specialist agents not yet implemented (slice M3.1).

The pipeline needs proposals for all 11 framework factors to reach draft.
Scope and Financial agents are real; the other 9 factors are replayed from a
recorded fixture here and persisted with origin="fixture" so draft consumers
can distinguish them from genuine agent output. Remove factors from this stub
as real agents land.
"""

import json
from pathlib import Path

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)


class FixtureReplayAgent:
    name = "fixture-replay-agent"
    version = "1.0.0"

    def __init__(self, stub_path: Path, factors: tuple[str, ...]):
        self._stub_path = Path(stub_path)
        self._factors = set(factors)

    def run(
        self,
        *,
        scope: ScopeSnapshot,
        framework: Framework,
        evidence: list[EvidenceItem],
    ) -> list[FactorProposal]:
        raw = json.loads(self._stub_path.read_text(encoding="utf-8"))
        evidence_index = {e.id: e.published_date for e in evidence}
        proposals = []
        for p in raw["proposals"]:
            proposal = FactorProposal.model_validate(p)
            if proposal.factor not in self._factors:
                continue
            validate_proposal(
                proposal,
                framework=framework,
                evidence=evidence_index,
                data_cutoff=scope.data_cutoff,
            )
            proposals.append(proposal)
        missing = self._factors - {p.factor for p in proposals}
        if missing:
            raise ValueError(f"stub missing proposals for {sorted(missing)}")
        return proposals
```

Export from `__init__.py`.

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
git add packages/agents examples/fixtures/adbe_2026-09-03/stub_proposals.json
git commit -m "feat(agents): fixture replay stub for unimplemented specialist factors"
```

---

### Task 8: Orchestrator — DAG-ready steps, idempotent resume, failure semantics

**Files:**
- Create: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/storage/src/fathomark_storage/state_machine.py` (add `NEEDS_REVIEW → ANALYZING` for re-execution after blocked review)
- Test: `packages/agents/tests/test_orchestrator.py`
- Modify: `packages/storage/tests/test_state_machine.py` (if it asserts exact transition sets — check and update)

**Interfaces:**
- Consumes: all prior tasks.
- Produces:
  - `@dataclass(frozen=True) StepSpec`: `name: str`, `depends_on: tuple[str, ...]`, `entry_state: RunState`, `exit_state: RunState | None`, `run: Callable[[], dict]` (returns step output for the record).
  - `Orchestrator(repo: RunRepository, framework: Framework, *, llm: LLMProvider, evidence_providers: list[EvidenceProvider], stub_path: Path, max_llm_calls: int = 32)`.
  - `orch.execute(run_id: str) -> RunState` — final state: `DRAFT`, `FAILED`, or `NEEDS_REVIEW`.
  - `build_default_steps(orch, run_id) -> list[StepSpec]` — exported for tests/inspection.
  - Budget: `llm` wrapped so each `complete` increments a counter; exceeding `max_llm_calls` raises `ProviderError("llm call budget exceeded")`.

Step graph (linear today; `depends_on` + topological levels make it parallel-safe later — orchestrator executes level by level and MAY run same-level steps concurrently in future without contract change):

```
scope (entry CREATED → exit SCOPED)
collect (entry SCOPED → exit COLLECTING)   depends_on scope
financial (entry ANALYZING)                depends_on collect
stub (entry ANALYZING)                     depends_on collect
compute (entry ANALYZING → exit DRAFT)     depends_on financial, stub
```

Semantics:
- Before each step: skip if `step_record.status == "succeeded"` and `input_hash` matches current computed hash. Input hash per step: `sha256` of canonical JSON of step inputs (scope dump for `scope`; scope+provider list for `collect`; scope+evidence ids/hashes for agents; scope+evidence hashes+proposal ids for `compute`).
- `_ensure_state(entry_state)`: if current == entry → ok; else BFS shortest path over `TRANSITIONS`; if none but current is later in canonical order `[created, scoped, collecting, analyzing, auditing, needs_review, draft]` → ok (resumed run already past); else `StateConflict`-style error → run failed.
- `ProviderError` or empty-evidence in any step → `fail_step`, set run `error`, advance to `FAILED`, return. (Required-provider failure is explicit; design §14.)
- `AgentError` (repairs exhausted) → `fail_step`, advance `ANALYZING → NEEDS_REVIEW`, return. `execute` may be called again after fixing the provider; `NEEDS_REVIEW → ANALYZING` transition enables re-run of the failed step.
- Other `Exception` → `fail_step`, run `FAILED` with error text.
- collect step: fetch from all evidence providers, drop items with `published_date > scope.data_cutoff` (design §14), persist rest via `repo.add_evidence`; zero remaining → failure ("no usable evidence").
- agent steps: persist proposals via `repo.add_proposals` (stub with `origin="fixture"`).
- compute step: `evaluate(...)` → `repo.save_draft_snapshot` → advance `DRAFT`.
- Terminal/approved runs: `execute` raises `StateConflict` (imported from a shared place — define `class OrchestratorError(RuntimeError)` in orchestrator.py; route maps it to 409).

- [ ] **Step 1: Write failing tests**

```python
# packages/agents/tests/test_orchestrator.py
import json
from pathlib import Path

import pytest
from fathomark_core import load_framework
from fathomark_providers import (
    FakeLLMProvider,
    FixtureEvidenceProvider,
    ReplayLLMProvider,
)
from fathomark_storage.state_machine import RunState

from fathomark_agents import Orchestrator

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
EXPECTED = json.loads((FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8"))


def _orchestrator(repo, llm):
    return Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=llm,
        evidence_providers=[FixtureEvidenceProvider(FIXTURE / "provider_dump.json")],
        stub_path=FIXTURE / "stub_proposals.json",
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
    assert set(steps) == {"scope", "collect", "financial", "stub", "compute"}
    assert all(s.status == "succeeded" for s in steps.values())


def test_resume_after_provider_failure_skips_finished_steps(seeded_run):
    repo, run_id = seeded_run
    from fathomark_providers import ProviderError

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
    good = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    assert _orchestrator(repo, good).execute(run_id) == RunState.DRAFT


def test_llm_budget_exceeded_fails_run(seeded_run):
    repo, run_id = seeded_run
    llm = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    orch = Orchestrator(
        repo,
        load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        llm=llm,
        evidence_providers=[FixtureEvidenceProvider(FIXTURE / "provider_dump.json")],
        stub_path=FIXTURE / "stub_proposals.json",
        max_llm_calls=0,
    )
    assert orch.execute(run_id) == RunState.FAILED


def test_execute_on_terminal_run_raises(seeded_run):
    repo, run_id = seeded_run
    orch = _orchestrator(repo, ReplayLLMProvider(FIXTURE / "llm_cassette.json"))
    assert orch.execute(run_id) == RunState.DRAFT
    repo.advance(
        run_id, RunState.APPROVED
    ) if False else None  # approve via service path in api tests
    repo.session.close() if False else None
```

(terminal-run test: cancel the run first, then execute → OrchestratorError; simplest: fresh seeded run, `repo.advance(run_id, RunState.CANCELLED)`, expect raise.)

- [ ] **Step 2: Run to verify fail** → ImportError.

- [ ] **Step 3: Add `NEEDS_REVIEW → ANALYZING` transition** with test in `test_state_machine.py` (re-execution of a blocked step).

- [ ] **Step 4: Implement `orchestrator.py`** per semantics above. Key helpers:

```python
_ORDER = [
    RunState.CREATED,
    RunState.SCOPED,
    RunState.COLLECTING,
    RunState.ANALYZING,
    RunState.AUDITING,
    RunState.NEEDS_REVIEW,
    RunState.DRAFT,
]


def _hash_payload(payload) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    )
```

`_ensure_state`: BFS over TRANSITIONS; fallback to `_ORDER` comparison. Budget wrapper class `_BudgetedLLM` implementing LLMProvider. Topological execution: Kahn levels from `depends_on`, run steps within a level sequentially (parallel later).

- [ ] **Step 5: Run tests, verify pass; commit**

```bash
git add packages/agents packages/storage
git commit -m "feat(agents): DAG-ready orchestrator with step records, resume, budgets"
```

---

### Task 9: API `POST /execute` + OpenAPI pin + offline e2e

**Files:**
- Modify: `packages/api/src/fathomark_api/app.py` — `create_app(..., orchestrator_factory=None)`; set `app.state.orchestrator_factory`.
- Modify: `packages/api/src/fathomark_api/routes/runs.py` — new endpoint.
- Modify: `packages/api/pyproject.toml` — deps += `fathomark-agents`, `fathomark-providers`.
- Modify: `docs/api/openapi-v1.json` — regenerate via `python scripts/dump_openapi.py`.
- Test: `packages/api/tests/test_execute_adbe.py`

**Interfaces:**
- `orchestrator_factory: Callable[[RunRepository], Orchestrator] | None` — route builds repo from session, calls factory, executes. `None` → 503 `{detail: "orchestrator not configured"}`.
- Endpoint: `POST /v1/research-runs/{run_id}/execute` → 200 `RunResponse` (state draft/failed/needs_review). Errors: 404 unknown run; 409 OrchestratorError/StateConflict (terminal runs).

- [ ] **Step 1: Write the failing e2e test**

```python
# packages/api/tests/test_execute_adbe.py
"""Offline e2e: create run -> execute -> draft matching golden snapshot."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fathomark_agents import Orchestrator
from fathomark_core import load_framework
from fathomark_providers import FixtureEvidenceProvider, ReplayLLMProvider

from fathomark_api import create_app

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


@pytest.fixture()
def client(tmp_path):
    fixture = FIXTURE

    def factory(repo):
        return Orchestrator(
            repo,
            load_framework(ROOT / "frameworks" / "common-stock.yaml"),
            llm=ReplayLLMProvider(fixture / "llm_cassette.json"),
            evidence_providers=[
                FixtureEvidenceProvider(fixture / "provider_dump.json")
            ],
            stub_path=fixture / "stub_proposals.json",
        )

    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
        orchestrator_factory=factory,
    )
    with TestClient(app) as c:
        yield c


def test_create_execute_draft_offline(client):
    scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))["scope"]
    r = client.post(
        "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-1"}
    )
    assert r.status_code == 201
    run_id = r.json()["id"]

    r = client.post(f"/v1/research-runs/{run_id}/execute")
    assert r.status_code == 200
    assert r.json()["state"] == "draft"

    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    expected = json.loads(
        (FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8")
    )
    assert result["snapshot"] == expected
    assert result["snapshot"]["content_hash"] == expected["content_hash"]


def test_execute_twice_is_idempotent(client):
    scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))["scope"]
    run_id = client.post(
        "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-2"}
    ).json()["id"]
    assert client.post(f"/v1/research-runs/{run_id}/execute").json()["state"] == "draft"
    assert client.post(f"/v1/research-runs/{run_id}/execute").json()["state"] == "draft"
    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    assert (
        result["snapshot"]["content_hash"]
        == json.loads((FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8"))[
            "content_hash"
        ]
    )


def test_execute_without_orchestrator_configured(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/t.db", framework_dir=ROOT / "frameworks"
    )
    with TestClient(app) as c:
        scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))[
            "scope"
        ]
        run_id = c.post(
            "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-3"}
        ).json()["id"]
        assert c.post(f"/v1/research-runs/{run_id}/execute").status_code == 503
```

Note: second `execute` on a `draft` run must be a no-op returning current state (all steps succeeded, hashes match → skip; compute skipped too since draft exists... careful: compute step skip requires hash match — scope/evidence/proposals unchanged → skip. `execute` on DRAFT is allowed (non-terminal); on APPROVED it 409s.)

- [ ] **Step 2: Run to verify fail** → 404 on `/execute`.

- [ ] **Step 3: Implement endpoint + app wiring + api pyproject deps.**

```python
@router.post("/research-runs/{run_id}/execute")
def execute(run_id: str, request: Request):
    factory = getattr(request.app.state, "orchestrator_factory", None)
    if factory is None:
        return JSONResponse({"detail": "orchestrator not configured"}, status_code=503)
    service = _service(request)
    from fathomark_agents.orchestrator import OrchestratorError

    def op():
        try:
            factory(service.repo).execute(run_id)
        except OrchestratorError as exc:
            raise StateConflict(str(exc)) from exc
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)
```

(`LookupError` already maps to 404 in `_handle`.)

- [ ] **Step 4: Regenerate OpenAPI pin**

Run: `python scripts/dump_openapi.py` then `pytest packages/api/tests/test_openapi_pinned.py -v` → PASS.

- [ ] **Step 5: Run full api + agents + providers + storage tests; commit**

```bash
git add packages/api docs/api/openapi-v1.json
git commit -m "feat(api): execute endpoint driving orchestrator to draft offline"
```

---

### Task 10: Docs sync + full verification

**Files:**
- Modify: `TODO.md` — M3 section: check off 通用协议、录制/假 Provider（录制契约测试）、Scope Agent、Financial Agent、Agent 修复重试（≤2）、数据截止日校验（本切片范围内）; add note that 9 factors run via `FixtureReplayAgent` pending real agents; mark M2 "Worker 中断后只恢复未完成步骤" complete (slice proves step-level resume via execute re-entry). Leave EDGAR/IR/行情 Provider、其余 Agent、预算完整实现、Normalizer 等 unchecked.
- Modify: `README.md`, `README.zh-CN.md` — status section: M3 first vertical slice landed (providers protocol, scope+financial agents, orchestrator, offline ADBE e2e to draft).

- [ ] **Step 1: Edit TODO.md / README.md / README.zh-CN.md** — only claims verified in Tasks 1–9.

- [ ] **Step 2: Full verification**

Run: `pytest -v` (entire suite), `ruff check .`, `ruff format --check .` — all green.

- [ ] **Step 3: Commit**

```bash
git add TODO.md README.md README.zh-CN.md
git commit -m "docs: mark M3 first vertical slice complete"
```

---

## Self-Review Notes

- Spec coverage: design §5.1/§5.3 agents ✓ (Tasks 5–6), §6 proposal contract + rejection rules ✓ (Task 6 validation), §7/§14 step records + resume ✓ (Tasks 4, 8), §13 provider protocols ✓ (Tasks 1–3), §14 repair ≤2 / cutoff / failure semantics ✓ (Tasks 5–8), §16.2/16.3 contract + recovery tests ✓. Deferred explicitly: real EDGAR/IR/market providers, remaining 6 agents, Red-Team, Normalizer dedup, MetricObservation/ReviewIssue/Artifact tables, full budget dimensions (tokens/cost/time — only call-count budget in slice), async worker app.
- Known sharp edge: cassette key is bound to `build_prompt` output; prompt changes require re-recording (test fails loudly — intended).
- `needs_review → analyzing` transition added for step re-execution; existing M2 flows (resolve_review → draft) unchanged.
- Type consistency checked across tasks: `complete_with_repairs`, `build_prompt`, `FINANCIAL_FACTORS`, `StepSpec`, `Orchestrator.execute`, repo step methods — names match at every use site.
