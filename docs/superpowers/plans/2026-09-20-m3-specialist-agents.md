# M3 Specialist Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace FixtureReplayAgent with 5 real specialist scoring agents (Business/Growth/Valuation/GovernanceRisk/Market) sharing a common SpecialistAgent base, so all 11 framework factors are produced by real agents while the ADBE offline e2e keeps producing the identical golden draft snapshot.

**Architecture:** Extract FinancialAgent's prompt-build + validate + repair pattern into `SpecialistAgent` (parameterized by `factors` + `instructions` class attributes). Five thin subclasses. `llm_cassette.json` is rebuilt by a committed deterministic script (`scripts/build_cassette.py`) that groups golden proposals from `input.json` per agent — no per-agent response files (spec refined: single source of truth, no duplication). Orchestrator gains 5 new DAG steps at the same level as `financial`; `stub` step, `stub_path` param, `fixture_agent.py`, `stub_proposals.json`, `financial_response.json` are deleted.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, pytest, uv workspace.

**Spec:** `docs/superpowers/specs/2026-09-20-m3-specialist-agents-design.md`; design doc §5.2–§5.7.

## Global Constraints

- Python `>=3.12`; uv workspace, hatchling; `ruff check .` + `ruff format --check .` clean.
- Agents never write DB — return Pydantic models, orchestrator persists (design §3).
- Repair loop ≤ 2 repairs, then AgentError → `needs_review` (design §14).
- Provider failure → explicit `failed`/`needs_review`, never silent (design §14).
- No LLM decides final weighted score — agents only propose; `evaluate()` computes (TODO §7).
- All tests offline; ADBE fixture only; no real keys/network in CI (design §19).
- Financial Agent's `_INSTRUCTIONS` text stays byte-identical in Task 1 so the existing cassette remains valid until regenerated in Task 2.
- `expected_snapshot.json` must NOT change; e2e asserts `content_hash` equality.
- Existing uncommitted diff in `docs/design/2026-09-18-fathomark-design.md` must be preserved; do not revert or commit it.

## File Structure

```
packages/agents/src/fathomark_agents/specialist_agent.py   # NEW: SpecialistAgent base + build_prompt
packages/agents/src/fathomark_agents/specialists.py        # NEW: 5 subclasses
packages/agents/src/fathomark_agents/financial_agent.py    # REFACTOR: thin subclass, keep FINANCIAL_FACTORS + build_prompt wrapper
packages/agents/src/fathomark_agents/fixture_agent.py      # DELETE (Task 3)
packages/agents/src/fathomark_agents/orchestrator.py       # MODIFY: 6 agent steps, drop stub_path
packages/agents/src/fathomark_agents/__init__.py           # MODIFY exports
packages/agents/tests/test_specialist_agent.py             # NEW: parametrized replay + repair/reject tests
packages/agents/tests/test_financial_agent.py              # MODIFY: read good response from cassette
packages/agents/tests/test_fixture_agent.py                # DELETE (Task 3)
packages/agents/tests/test_orchestrator.py                 # MODIFY: 9-step graph, no stub_path
packages/api/tests/test_execute_adbe.py                    # MODIFY: factory drops stub_path
scripts/build_cassette.py                                  # NEW: deterministic cassette builder
examples/fixtures/adbe_2026-09-03/llm_cassette.json        # REGENERATED (6 entries)
examples/fixtures/adbe_2026-09-03/stub_proposals.json      # DELETE (Task 3)
examples/fixtures/adbe_2026-09-03/financial_response.json  # DELETE (Task 2)
TODO.md / README.md / README.zh-CN.md                      # status sync
```

---

### Task 1: SpecialistAgent base + FinancialAgent refactor

**Files:**
- Create: `packages/agents/src/fathomark_agents/specialist_agent.py`
- Modify: `packages/agents/src/fathomark_agents/financial_agent.py`
- Test: `packages/agents/tests/test_financial_agent.py` (existing — must stay green unchanged)

**Interfaces:**
- Produces:
  - `build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem], instructions: str) -> str` — canonical JSON payload identical to current financial format.
  - `SpecialistAgent` — class attrs `name: str`, `version: str = "1.0.0"`, `factors: tuple[str, ...]`, `instructions: str`; `__init__(self, llm: LLMProvider, max_repairs: int = 2)`; `run(*, scope, framework, evidence) -> list[FactorProposal]`.
  - `FinancialAgent(SpecialistAgent)` with `factors = FINANCIAL_FACTORS`, `instructions = _INSTRUCTIONS` (byte-identical to current text).
  - `financial_agent.build_prompt(scope, evidence)` — 2-arg wrapper kept for import compatibility.

- [ ] **Step 1: Run existing financial tests as regression baseline**

Run: `pytest packages/agents/tests/test_financial_agent.py -v`
Expected: PASS (baseline before refactor)

- [ ] **Step 2: Implement `specialist_agent.py`**

```python
"""Specialist scoring agent base: shared prompt, validation, repair (§5, §14).

Each specialist owns an exclusive factor set and a domain instruction header.
One LLM call proposes all owned factors; output is schema-validated, checked
for foreign factors and unknown/post-cutoff evidence references, and repaired
at most twice before AgentError propagates to the orchestrator.
"""

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


def build_prompt(
    scope: ScopeSnapshot, evidence: list[EvidenceItem], instructions: str
) -> str:
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
    return instructions + json.dumps(payload, sort_keys=True, ensure_ascii=False)


class SpecialistAgent:
    """Base class for factor-proposing agents. Subclasses set class attrs."""

    name = "specialist-agent"
    version = "1.0.0"
    factors: tuple[str, ...] = ()
    instructions = ""

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
            # Every failure path must raise ValueError: complete_with_repairs
            # catches ValueError only (ruff BLE001), so structural errors that
            # would surface as KeyError/TypeError are normalized here.
            # json.JSONDecodeError, pydantic.ValidationError and ProposalError
            # are already ValueError subclasses.
            try:
                proposal_dicts = json.loads(text)["proposals"]
                proposals = [FactorProposal.model_validate(p) for p in proposal_dicts]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"malformed proposals payload: {exc}") from exc
            if not proposals:
                raise ValueError("no proposals returned")
            for p in proposals:
                if p.factor not in self.factors:
                    raise ValueError(f"{self.name} may not propose {p.factor}")
                validate_proposal(
                    p,
                    framework=framework,
                    evidence=evidence_index,
                    data_cutoff=scope.data_cutoff,
                )
            return proposals

        return complete_with_repairs(
            self.llm,
            build_prompt(scope, evidence, self.instructions),
            "factor_proposals",
            parse_validate,
            self.max_repairs,
        )
```

- [ ] **Step 3: Refactor `financial_agent.py` to a thin subclass**

Full replacement content:

```python
"""Financial Agent: financial_health + earnings_quality proposals (design §5.3)."""

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot

from fathomark_agents.specialist_agent import SpecialistAgent
from fathomark_agents.specialist_agent import build_prompt as _build_prompt

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


class FinancialAgent(SpecialistAgent):
    name = "financial-agent"
    factors = FINANCIAL_FACTORS
    instructions = _INSTRUCTIONS


def build_prompt(scope: ScopeSnapshot, evidence: list[EvidenceItem]) -> str:
    """2-arg compatibility wrapper (prompt identical to pre-refactor output)."""
    return _build_prompt(scope, evidence, _INSTRUCTIONS)
```

- [ ] **Step 4: Run financial tests, verify still green (prompt byte-identical, cassette still valid)**

Run: `pytest packages/agents/tests/test_financial_agent.py -v`
Expected: PASS — proves `build_prompt` output unchanged (replay test hits existing cassette)

- [ ] **Step 5: Commit**

```bash
git add packages/agents/src/fathomark_agents/specialist_agent.py packages/agents/src/fathomark_agents/financial_agent.py
git commit -m "refactor(agents): extract SpecialistAgent base from FinancialAgent"
```

---

### Task 2: Five specialist subclasses + deterministic cassette builder

**Files:**
- Create: `packages/agents/src/fathomark_agents/specialists.py`
- Create: `scripts/build_cassette.py`
- Modify: `packages/agents/src/fathomark_agents/__init__.py`
- Modify: `packages/agents/tests/test_financial_agent.py` (drop `financial_response.json` dependency)
- Delete: `examples/fixtures/adbe_2026-09-03/financial_response.json`
- Regenerate: `examples/fixtures/adbe_2026-09-03/llm_cassette.json`
- Test: `packages/agents/tests/test_specialist_agent.py`

**Interfaces:**
- Consumes: Task 1 `SpecialistAgent`, `build_prompt(scope, evidence, instructions)`.
- Produces: `BusinessAgent`, `GrowthAgent`, `ValuationAgent`, `GovernanceRiskAgent`, `MarketAgent` (each with `factors`/`instructions` class attrs); `scripts/build_cassette.py` `main()` writing 6-entry cassette keyed by `prompt_key(build_prompt(scope, evidence, agent.instructions))`.

Factor mapping (design §5.2–§5.7, mutually exclusive):
- BusinessAgent → `("business_moat",)`
- GrowthAgent → `("growth_sustainability",)`
- ValuationAgent → `("valuation",)`
- GovernanceRiskAgent → `("governance", "policy_risk")`
- MarketAgent → `("trend_momentum", "liquidity", "volatility_downside", "catalyst_window")`

- [ ] **Step 1: Write the failing parametrized replay test**

```python
# packages/agents/tests/test_specialist_agent.py
"""Cassette replay contract tests for all six specialist agents."""

import json

import pytest
from fathomark_providers import ReplayLLMProvider

from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)

from .conftest import FIXTURE

AGENTS = (
    FinancialAgent,
    BusinessAgent,
    GrowthAgent,
    ValuationAgent,
    GovernanceRiskAgent,
    MarketAgent,
)


@pytest.mark.parametrize("agent_cls", AGENTS, ids=lambda c: c.name)
def test_agent_replays_golden_proposals(scope, evidence, framework, agent_cls):
    llm = ReplayLLMProvider(FIXTURE / "llm_cassette.json")
    proposals = agent_cls(llm).run(scope=scope, framework=framework, evidence=evidence)
    golden = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))[
        "proposals"
    ]
    expected = {p["factor"]: p for p in golden if p["factor"] in agent_cls.factors}
    assert len(proposals) == len(agent_cls.factors) > 0
    for p in proposals:
        g = expected[p.factor]
        assert p.proposed_score == g["proposed_score"]
        assert p.evidence_ids == g["evidence_ids"]
        assert p.rationale == g["rationale"]


def test_all_eleven_factors_covered():
    covered = {f for cls in AGENTS for f in cls.factors}
    assert len(covered) == 11  # no overlap, no gap vs framework factors
```

(If `from .conftest import FIXTURE` fails under the repo's pytest import mode, duplicate the two lines `ROOT = Path(__file__).parents[3]; FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"` at the top instead — match what `test_orchestrator.py` does.)

- [ ] **Step 2: Run to verify fail**

Run: `pytest packages/agents/tests/test_specialist_agent.py -v`
Expected: FAIL (ImportError: no module `specialists`)

- [ ] **Step 3: Implement `specialists.py`**

```python
"""Specialist scoring agents (design §5.2-§5.7).

Each subclass is only a factor set plus a domain instruction header; all
behavior lives in SpecialistAgent. Factor ownership is mutually exclusive —
FinancialAgent owns financial_health/earnings_quality, these five own the
remaining nine framework factors.
"""

from fathomark_agents.specialist_agent import SpecialistAgent

_TEMPLATE = """You are the {title} for an equity research pipeline.
Return JSON {{"proposals": [...]}} proposing scores for exactly these factors:
{factors}.
{domain}
Each proposal: factor, proposed_score (0-10, 0.5 steps), rationale,
evidence_ids, counter_evidence_ids, confidence (high|medium|low|insufficient),
missing_data, as_of_date. Only cite evidence ids listed below. Never cite
evidence published after the data cutoff. Return JSON only.

INPUT:
"""


def _instructions(title: str, factors: tuple[str, ...], domain: str) -> str:
    return _TEMPLATE.format(title=title, factors=", ".join(factors), domain=domain)


class BusinessAgent(SpecialistAgent):
    name = "business-agent"
    factors = ("business_moat",)
    instructions = _instructions(
        "Business Agent",
        factors,
        "Analyze the business model, moat, competitive landscape, and customer "
        "and product concentration.",
    )


class GrowthAgent(SpecialistAgent):
    name = "growth-agent"
    factors = ("growth_sustainability",)
    instructions = _instructions(
        "Growth Agent",
        factors,
        "Analyze growth sources, backlog, users, capacity and unit economics. "
        "Distinguish sustainable growth from cyclical rebounds and one-offs.",
    )


class ValuationAgent(SpecialistAgent):
    name = "valuation-agent"
    factors = ("valuation",)
    instructions = _instructions(
        "Valuation Agent",
        factors,
        "Choose valuation paths allowed by the framework and explain input "
        "choices. Never compute final valuation numbers yourself.",
    )


class GovernanceRiskAgent(SpecialistAgent):
    name = "governance-risk-agent"
    factors = ("governance", "policy_risk")
    instructions = _instructions(
        "Governance & Risk Agent",
        factors,
        "Analyze management integrity, audit quality, related-party "
        "transactions, capital allocation, and regulatory and policy risk.",
    )


class MarketAgent(SpecialistAgent):
    name = "market-agent"
    factors = ("trend_momentum", "liquidity", "volatility_downside", "catalyst_window")
    instructions = _instructions(
        "Market Agent",
        factors,
        "Interpret trend, liquidity, volatility, drawdown and catalyst windows. "
        "Market metrics are computed programmatically; you only explain "
        "anomalies and event context.",
    )
```

Note: inside class bodies, `factors` referenced in the `_instructions(...)` call resolves to the class-body local just assigned — this works because the call happens after the `factors = ...` line within the same class body.

Update `__init__.py`: add imports/exports for `SpecialistAgent`, `BusinessAgent`, `GrowthAgent`, `ValuationAgent`, `GovernanceRiskAgent`, `MarketAgent` (keep `FixtureReplayAgent` export for now — deleted in Task 3).

- [ ] **Step 4: Write `scripts/build_cassette.py` and regenerate the cassette**

```python
"""Rebuild llm_cassette.json deterministically from the ADBE fixture.

Prompts are computed with the real build_prompt; responses are the golden
proposals from input.json grouped by specialist agent. No network, no LLM.
Re-run after changing agent instructions or the prompt builder, and commit
the result.
"""

import json
from pathlib import Path

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot
from fathomark_providers import prompt_key

from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.specialist_agent import build_prompt
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
AGENTS = (
    FinancialAgent,
    BusinessAgent,
    GrowthAgent,
    ValuationAgent,
    GovernanceRiskAgent,
    MarketAgent,
)


def main() -> None:
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    scope = ScopeSnapshot.model_validate(data["scope"])
    golden = data["proposals"]
    dump = json.loads((FIXTURE / "provider_dump.json").read_text(encoding="utf-8"))
    evidence = [EvidenceItem.model_validate(e) for e in dump["evidence"]]
    cassette = {}
    for agent_cls in AGENTS:
        proposals = [p for p in golden if p["factor"] in agent_cls.factors]
        if len(proposals) != len(agent_cls.factors):
            raise SystemExit(f"golden input missing factors for {agent_cls.name}")
        prompt = build_prompt(scope, evidence, agent_cls.instructions)
        cassette[prompt_key(prompt)] = json.dumps(
            {"proposals": proposals}, ensure_ascii=False
        )
    out = FIXTURE / "llm_cassette.json"
    out.write_text(
        json.dumps(cassette, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cassette)} cassette entries to {out}")


if __name__ == "__main__":
    main()
```

Run: `uv run python scripts/build_cassette.py`
Expected: `wrote 6 cassette entries to ...`

- [ ] **Step 5: Update `test_financial_agent.py` to drop `financial_response.json`; delete that file**

In `test_unknown_evidence_reference_rejected_then_repaired`, replace:

```python
    good = (FIXTURE / "financial_response.json").read_text(encoding="utf-8")
```

with:

```python
    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text(encoding="utf-8"))
    good = cassette[prompt_key(build_prompt(scope, evidence))]
```

Add `from fathomark_providers import prompt_key` to its imports (`build_prompt` is already imported there). Then `git rm examples/fixtures/adbe_2026-09-03/financial_response.json`.

- [ ] **Step 6: Add repair/rejection tests for a representative new agent**

Append to `test_specialist_agent.py`:

```python
def test_market_agent_rejects_foreign_factor(scope, evidence, framework):
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
    from fathomark_providers import FakeLLMProvider

    from fathomark_agents import AgentError

    llm = FakeLLMProvider([payload, payload, payload])
    with pytest.raises(AgentError):
        MarketAgent(llm).run(scope=scope, framework=framework, evidence=evidence)


def test_business_agent_repairs_malformed_json(scope, evidence, framework):
    from fathomark_providers import FakeLLMProvider, prompt_key

    from fathomark_agents.specialist_agent import build_prompt

    cassette = json.loads((FIXTURE / "llm_cassette.json").read_text(encoding="utf-8"))
    good = cassette[
        prompt_key(build_prompt(scope, evidence, BusinessAgent.instructions))
    ]
    llm = FakeLLMProvider(["not json", good])
    proposals = BusinessAgent(llm).run(
        scope=scope, framework=framework, evidence=evidence
    )
    assert [p.factor for p in proposals] == ["business_moat"]
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt
```

(Move the new imports to the top of the file per ruff/isort — shown inline here only for readability.)

- [ ] **Step 7: Run tests, verify pass; commit**

Run: `pytest packages/agents -v` → all PASS (including existing financial/orchestrator tests — orchestrator tests still pass because the financial cassette entry was regenerated byte-identically? No: cassette was regenerated with 6 entries; the financial prompt is unchanged so its key/response survive. The `stub` path is untouched in this task.)

```bash
git add packages/agents scripts/build_cassette.py examples/fixtures/adbe_2026-09-03
git commit -m "feat(agents): five specialist agents with deterministic cassette builder"
```

---

### Task 3: Orchestrator — six agent steps, delete fixture replay path

**Files:**
- Modify: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/agents/src/fathomark_agents/__init__.py` (drop FixtureReplayAgent)
- Delete: `packages/agents/src/fathomark_agents/fixture_agent.py`
- Delete: `packages/agents/tests/test_fixture_agent.py`
- Delete: `examples/fixtures/adbe_2026-09-03/stub_proposals.json`
- Test: `packages/agents/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: Task 2 agent classes.
- Produces: `Orchestrator(repo, framework, *, llm, evidence_providers, max_llm_calls=32)` — **no `stub_path`**; step graph `scope → collect → {financial, business, growth, valuation, governance_risk, market} → compute`.

- [ ] **Step 1: Update the failing tests first**

In `test_orchestrator.py`:

- `_orchestrator` helper and the budget test: delete the `stub_path=FIXTURE / "stub_proposals.json",` argument.
- `test_full_run_reaches_draft_matching_golden`: replace step-set assertion with:

```python
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
```

- Add proposals-origin assertion at the end of that test:

```python
    from fathomark_storage.models import ProposalRow  # only if needed; prefer repo API
```

(Skip the origin assertion if `proposals_of` returns Pydantic models without origin — check the repo API; do not add DB-level assertions just for this.)

- Add a resume test for a mid-level agent failure (append):

```python
def test_resume_retries_only_failed_agent(seeded_run):
    """Market agent (last in level) fails; re-execute reruns only market."""
    import json as _json

    from fathomark_providers import ProviderError, prompt_key

    from fathomark_agents.specialist_agent import build_prompt

    repo, run_id = seeded_run
    scope = repo.scope_of(run_id)
    evidence_dump = _json.loads((FIXTURE / "provider_dump.json").read_text())
    from fathomark_core.schemas import EvidenceItem

    evidence = [EvidenceItem.model_validate(e) for e in evidence_dump["evidence"]]
    cassette = _json.loads((FIXTURE / "llm_cassette.json").read_text())
    from fathomark_agents.specialists import (
        BusinessAgent,
        GovernanceRiskAgent,
        GrowthAgent,
        MarketAgent,
        ValuationAgent,
    )
    from fathomark_agents.financial_agent import FinancialAgent

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
```

(Move imports to top of file per ruff/isort.)

- [ ] **Step 2: Run to verify fail**

Run: `pytest packages/agents/tests/test_orchestrator.py -v`
Expected: FAIL (TypeError: unexpected keyword argument `stub_path` still accepted so tests fail on step-set assertion / ImportError of `specialists` usage — either way, red)

- [ ] **Step 3: Rewire `orchestrator.py`**

Edits:

1. Imports: remove `from fathomark_agents.fixture_agent import FixtureReplayAgent`; remove `FINANCIAL_FACTORS` from the financial import; add:

```python
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)
```

2. Module docstring line 3: change `(scope → collect → {financial, stub} → compute)` to `(scope → collect → six specialist agents → compute)`.

3. Add after `_NON_EXECUTABLE`:

```python
_AGENT_SPECS = (
    ("financial", FinancialAgent),
    ("business", BusinessAgent),
    ("growth", GrowthAgent),
    ("valuation", ValuationAgent),
    ("governance_risk", GovernanceRiskAgent),
    ("market", MarketAgent),
)
_AGENT_STEP_NAMES = frozenset(name for name, _ in _AGENT_SPECS)
```

4. `__init__`: delete the `stub_path: Path` parameter and `self.stub_path = Path(stub_path)`; remove the now-unused `from pathlib import Path` import.

5. `_provider_info`: replace the `financial` and `stub` branches with:

```python
        if step_name in _AGENT_STEP_NAMES:
            return self.llm.name, self.llm.version
```

6. `_step_input_hash`: replace `elif step_name in ("financial", "stub"):` with `elif step_name in _AGENT_STEP_NAMES:`.

7. `build_default_steps`: replace `financial_step` and `stub_step` with:

```python
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
```

and the return list becomes:

```python
return [
    StepSpec("scope", (), RunState.CREATED, RunState.SCOPED, scope_step),
    StepSpec("collect", ("scope",), RunState.SCOPED, RunState.COLLECTING, collect_step),
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
```

8. Delete `fixture_agent.py`, `test_fixture_agent.py`, `stub_proposals.json`; remove `FixtureReplayAgent` from `__init__.py` imports/`__all__`.

- [ ] **Step 4: Run tests, verify pass; commit**

Run: `pytest packages/agents -v` → all PASS. Existing tests `test_resume_after_provider_failure_skips_finished_steps` (financial attempt == 2), `test_agent_error_sends_run_to_needs_review_and_recovers`, `test_llm_budget_exceeded_fails_run` must pass unmodified — behavior at the financial step is unchanged.

```bash
git add -A packages/agents examples/fixtures/adbe_2026-09-03
git commit -m "feat(agents): orchestrate six specialist agents, drop fixture replay"
```

---

### Task 4: API e2e update

**Files:**
- Modify: `packages/api/tests/test_execute_adbe.py:22-31`

**Interfaces:**
- Consumes: Task 3 `Orchestrator` without `stub_path`.

- [ ] **Step 1: Update factory and run api tests**

Delete the line `stub_path=fixture / "stub_proposals.json",` from the `factory` in the `client` fixture.

Run: `pytest packages/api -v`
Expected: all PASS, including `test_create_execute_draft_offline` asserting the snapshot deep-equals `expected_snapshot.json` (proposals identical → content_hash identical).

- [ ] **Step 2: Commit**

```bash
git add packages/api/tests/test_execute_adbe.py
git commit -m "test(api): execute e2e without stub_path after specialist agents"
```

---

### Task 5: Docs sync + full verification

**Files:**
- Modify: `TODO.md` (§3 M3)
- Modify: `README.md`, `README.zh-CN.md`

- [ ] **Step 1: Edit TODO.md**

- `- [ ] 实现 Business Agent。` → `- [x] 实现 Business Agent。(BusinessAgent：business_moat，cassette 回放)`
- `- [ ] 实现 Growth Agent。` → `- [x] 实现 Growth Agent。(GrowthAgent：growth_sustainability)`
- `- [ ] 实现 Valuation Agent。` → `- [x] 实现 Valuation Agent。(ValuationAgent：valuation)`
- `- [ ] 实现 Governance & Risk Agent。` → `- [x] 实现 Governance & Risk Agent。(GovernanceRiskAgent：governance + policy_risk；Veto 候选随 Red-Team 后续)`
- `- [ ] 实现 Market Agent。` → `- [x] 实现 Market Agent。(MarketAgent：trend/liquidity/volatility/catalyst)`
- Replace the note line `- 注：其余 9 个因子暂由 FixtureReplayAgent 从录制夹具回放（origin="fixture"），待对应真实 Agent 落地后逐个替换。` with `- 注：全部 11 个因子由真实 Agent 覆盖（离线 cassette 回放）；FixtureReplayAgent 已删除。cassette 由 scripts/build_cassette.py 确定性重建。`
- M3 完成标准：`- [ ] 任一必需 Provider 失败时，系统显式失败或进入 needs_review。` → `[x]`（test_orchestrator 覆盖）；`- [ ] Agent 无法引用不存在或超出截止日的证据。` → `[x]`（validate_proposal 测试覆盖）。第一项（真实 EDGAR 数据生成草稿）保持未勾。

- [ ] **Step 2: Edit READMEs**

README.md (and mirror in README.zh-CN.md): grep for `M3` / `scope/financial agents` / `remaining agents` mentions and sync to: all 11 framework factors covered by real specialist agents (offline cassette replay); orchestrator runs scope → collect → 6 agents → compute. Specifically line ~257 table row `Protocols + scope/financial agents ✅ (M3 slice); remaining agents ◻ Planned` → `Protocols + all specialist agents ✅ (M3, offline replay)`. Keep claims limited to what tests prove.

- [ ] **Step 3: Full verification**

Run: `uv run pytest -v` (entire suite), `uv run ruff check .`, `uv run ruff format --check .` — all green.

- [ ] **Step 4: Commit**

```bash
git add TODO.md README.md README.zh-CN.md
git commit -m "docs: mark M3 specialist agents complete"
```

---

## Self-Review Notes

- Spec coverage: SpecialistAgent base ✓ (Task 1), 5 subclasses + factor map ✓ (Task 2), cassette builder replacing per-agent response files ✓ (Task 2, spec deviation documented in Architecture), orchestrator 9-step graph + stub deletion ✓ (Task 3), API e2e ✓ (Task 4), docs ✓ (Task 5). Red-Team/Veto explicitly out of scope.
- Deviation from spec: no `responses/<agent>.json` files — cassette built directly from `input.json` golden proposals (single source of truth). `financial_response.json` deleted; its one consumer updated to read from cassette.
- Cassette validity chain: Task 1 keeps financial prompt byte-identical (existing cassette valid) → Task 2 regenerates with 6 entries → Task 3/4 replay all 6. Every stage stays green.
- Step order within the agent level follows `_AGENT_SPECS` definition order (financial first), so existing failure tests (which fail at financial) behave identically.
- Type consistency checked: `build_prompt(scope, evidence, instructions)` 3-arg in base, 2-arg wrapper in financial_agent; `_AGENT_SPECS` names used in `_provider_info`/`_step_input_hash`/`build_default_steps`; test imports match module layout (`specialists.py`, `specialist_agent.py`).
