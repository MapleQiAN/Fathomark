# M3 Freshness and Runtime Budgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce framework freshness windows during evidence collection and expose auditable LLM token, cost, call-count, and runtime budgets in orchestrator step records.

**Architecture:** Evidence normalization remains the provider boundary: it drops post-cutoff and stale evidence before persistence and reports deterministic counters. A standalone immutable `LLMBudget` config wraps the existing LLM protocol, accumulates usage from `LLMResponse`, and raises non-retriable `ProviderError` when a limit is exceeded; successful agent steps include the cumulative usage snapshot.

**Tech Stack:** Python 3.12+, dataclasses, `time.monotonic`, Pydantic models already in core/providers, pytest, Ruff.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 8 and 14; `TODO.md` section 3.

## Global Constraints

- Evidence after `data_cutoff` or outside a configured source-class freshness window must not enter scoring.
- Unknown source classes remain traceable rather than being silently guessed a freshness window.
- Budget exhaustion must fail explicitly; it must not fabricate an output or silently continue.
- Usage metrics must come only from provider responses and must never include secrets.
- Existing `Orchestrator(max_llm_calls=...)` callers remain compatible.

## Review Focus

- A stale or future-dated evidence item is dropped and counted deterministically.
- An evidence item with no configured freshness policy remains usable and auditable.
- Missing/negative provider usage does not create negative budget usage.
- Token, cost, call, and runtime limits all fail before the run can reach draft.
- Existing golden fixture remains unchanged because its filing dates are within policy.

### Task 1: Freshness-aware evidence normalization

**Files:**
- Modify: `packages/providers/src/fathomark_providers/evidence.py`
- Modify: `packages/providers/tests/test_fixture_evidence.py`
- Modify: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/agents/tests/test_orchestrator.py`

- [x] **Step 1: Write failing tests** for stale/future evidence dropping, unknown-class retention, and collect-step `dropped_stale` output.
- [x] **Step 2: Run focused tests and observe the missing field/keyword failures.**
- [x] **Step 3: Add optional `research_date`/`freshness` inputs, `dropped_stale`, and wire framework policy through the collect step.**
- [x] **Step 4: Run provider and agent tests plus Ruff.**
- [x] **Step 5: Commit `feat(agents): enforce evidence freshness windows`.**

### Task 2: Auditable LLM budgets

**Files:**
- Create: `packages/agents/src/fathomark_agents/budget.py`
- Modify: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/agents/src/fathomark_agents/__init__.py`
- Modify: `packages/agents/tests/test_orchestrator.py`

- [x] **Step 1: Write failing tests** for usage accounting, token/cost/call/runtime exhaustion, and successful-step usage output.
- [x] **Step 2: Implement immutable `LLMBudget`, `_BudgetedLLM` accounting, and optional `Orchestrator(budget=...)` without changing old call sites.**
- [x] **Step 3: Include usage in successful LLM step records and export `LLMBudget`.**
- [x] **Step 4: Run focused tests and Ruff.**
- [x] **Step 5: Commit `feat(agents): enforce token and cost budgets`.**

### Task 3: Roadmap bookkeeping and full validation

**Files:**
- Modify: `TODO.md`
- Modify: this plan

- [x] **Step 1: Mark freshness/NR and call/token/cost/runtime budget items according to the implemented boundary.**
- [x] **Step 2: Run `uv run pytest -q`, Ruff check/format, and `git diff --check`.**
- [x] **Step 3: Record that live providers and wall-clock production behavior remain environment-dependent.**
- [x] **Step 4: Commit `docs: record M3 freshness and budget coverage`.**
