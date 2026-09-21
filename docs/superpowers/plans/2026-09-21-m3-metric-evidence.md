# M3 Metric Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist normalized, evidence-linked SEC XBRL financial facts so specialist agents can receive auditable structured inputs alongside filing excerpts.

**Architecture:** Add a frozen `ProviderResult` containing evidence and `MetricObservation` items, then switch all providers and the collect step together in one runnable integration commit. Evidence normalization returns a stable input-ID-to-canonical-ID map; the collect step applies it before persisting observations. Collection input hashes remain scope/provider-only to preserve resume idempotency, while downstream specialist/compute hashes include persisted metric identities. SEC EDGAR extends the existing filings path with `companyfacts`, selecting only explicitly mapped, USD, single-period 10-K/10-Q facts from selected accessions at or before the run cutoff.

**Tech Stack:** Python 3.12+, Pydantic, SQLAlchemy, Alembic, SQLite/PostgreSQL, standard-library HTTP transport, pytest, Ruff.

---

### Task 1: Provider result and metric normalization contract

**Files:**
- Modify: `packages/providers/src/fathomark_providers/evidence.py`
- Modify: `packages/providers/src/fathomark_providers/__init__.py`
- Modify: `packages/providers/tests/test_fixture_evidence.py`

- [ ] **Step 1: Write failing tests for `ProviderResult` and `MetricNormalizer`.**

```python
result = ProviderResult(evidence=(evidence,), observations=(observation,))
assert result.evidence == (evidence,)

normalized = MetricNormalizer().normalize(
    RawMetricObservation(
        metric="revenue",
        value=5.87,
        unit="USDm",
        data_date=date(2026, 5, 29),
        evidence_id="sec:...",
        basis="quarterly",
    )
)
assert normalized.value == 5_870_000
assert normalized.unit == "USD"
assert normalized.currency == "USD"

deduped = EvidenceNormalizer().normalize(
    [lower_grade, higher_grade], data_cutoff=cutoff
)
assert deduped.canonical_id_by_input_id[lower_grade.id] == higher_grade.id
```

- [ ] **Step 2: Run provider tests and verify they fail because the contract types are missing.**

Run: `uv run pytest -q packages/providers/tests/test_fixture_evidence.py -k 'provider_result or metric_normalizer'`

Expected: FAIL with missing `ProviderResult` or `MetricNormalizer`.

- [ ] **Step 3: Add frozen result/raw-observation types and a narrow, explicit USD unit map.**

```python
class ProviderResult:
    evidence: tuple[EvidenceItem, ...]
    observations: tuple[MetricObservation, ...]


class MetricNormalizer:
    def normalize(self, raw: RawMetricObservation) -> MetricObservation: ...
```

Only normalize `USD`, `USDm`, and `USD millions`; reject unrecognized units rather than guessing. Keep `core` unchanged and network-free. Add the alias map after the final duplicate winner is known, rather than recording a stale provisional winner.

- [ ] **Step 4: Export the new types without changing existing provider returns yet.**

Keep the current evidence-only `fetch()` protocol runnable until Task 4. Task 4 updates `FixtureEvidenceProvider`, `SecEdgarEvidenceProvider`, `_StaticEvidenceProvider`, fixture assertions that index `fetch()` results, and the API/orchestrator ADBE execution path together.

- [ ] **Step 5: Run provider tests and format checks.**

Run: `uv run pytest -q packages/providers/tests && uv run ruff check packages/providers && uv run ruff format --check packages/providers`

Expected: PASS.

- [ ] **Step 6: Commit the additive provider contract only.**

```bash
git add packages/providers
git commit -m "feat(providers): add normalized metric result contract"
```

### Task 2: Metric observation persistence and migration

**Files:**
- Modify: `packages/storage/src/fathomark_storage/models.py`
- Modify: `packages/storage/src/fathomark_storage/database.py`
- Modify: `packages/storage/src/fathomark_storage/repository.py`
- Create: `packages/storage/alembic/versions/0003_metric_observations.py`
- Modify: `packages/storage/tests/test_repository.py`
- Modify: `packages/storage/tests/test_alembic.py`

- [ ] **Step 1: Write failing repository tests for round-trip, duplicate rejection, and missing evidence references.**

```python
repo.add_evidence(run_id, [evidence])
repo.add_metric_observations(run_id, [observation])
assert repo.metric_observations_of(run_id) == [observation]

with pytest.raises(ValueError, match="unknown evidence id"):
    repo.add_metric_observations(run_id, [unknown_reference])
```

- [ ] **Step 2: Run the focused repository test and verify it fails because the repository methods/table do not exist.**

Run: `uv run pytest -q packages/storage/tests/test_repository.py -k metric_observation`

Expected: FAIL with missing repository API.

- [ ] **Step 3: Add `MetricObservationRow` and migration `0003`.**

Use portable scalar fields (`metric`, `value`, `unit`, nullable `currency`, `basis`, nullable `formula`, `data_date`, `evidence_id`), a foreign key to the run, and a composite foreign key `(run_id, evidence_id) -> evidence_items(run_id, evidence_id)`. Restrict the v1 `basis` values to `quarterly` and `annual`; include `basis` in the uniqueness constraint `(run_id, metric, data_date, evidence_id, basis)`. Enable `PRAGMA foreign_keys=ON` on every SQLite connection in `create_session_factory` so the SQLite backstop is real, not just declarative metadata.

- [ ] **Step 4: Implement `add_metric_observations` and `metric_observations_of`.**

Preflight all referenced evidence IDs against the current run and both existing and in-batch uniqueness keys before inserting; reject the complete batch without mutating the database. Test that the SQLite connection has foreign keys enabled, test both the application error and database composite-FK backstop, then verify the session remains usable after the rejected batch.

- [ ] **Step 5: Update Alembic parity/version tests and run storage validation.**

Run: `uv run pytest -q packages/storage/tests && uv run pytest -q packages/storage/tests/test_postgres.py && uv run ruff check packages/storage && uv run ruff format --check packages/storage`

Expected: PASS; SQLite migration parity includes `metric_observations` and head revision `0003`. PostgreSQL tests may skip only when `PG_TEST_URL` is absent; when configured, cover the composite foreign key and round-trip.

- [ ] **Step 6: Commit persistence support.**

```bash
git add packages/storage
git commit -m "feat(storage): persist metric observations"
```

### Task 3: SEC companyfacts extraction

**Files:**
- Modify: `packages/providers/src/fathomark_providers/evidence.py`
- Modify: `packages/providers/tests/test_fixture_evidence.py`

- [ ] **Step 1: Write a failing recorded-response test for `companyfacts`.**

The test supplies selected filing accessions plus XBRL `us-gaap` USD facts and asserts that only facts matching the selected 10-K/10-Q accessions and cutoff become observations. It must cover revenue, net income, and operating cash flow, with each observation referencing its filing evidence ID. It must prove a 10-Q year-to-date fact is excluded while a 80–100 day single-quarter fact is retained, that a 53-week 10-K fact is retained, and that revenue uses its primary tag when both revenue tags are present but falls back when it is absent.

- [ ] **Step 2: Run the focused test and verify it fails because the SEC provider does not request/companyfacts or return observations.**

Run: `uv run pytest -q packages/providers/tests/test_fixture_evidence.py -k companyfacts`

Expected: FAIL with zero observations or missing request.

- [ ] **Step 3: Implement fixed-host `companyfacts` retrieval and deterministic fact selection.**

Use `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`; select these tags in exact priority order: `RevenueFromContractWithCustomerExcludingAssessedTax`, then `SalesRevenueNet` for `revenue`; `NetIncomeLoss` for `net_income`; and `NetCashProvidedByUsedInOperatingActivities` for `operating_cash_flow`. For each `(metric, evidence_id, basis, data_date)`, take facts from the first tag with an eligible fact and ignore lower-priority tags. Select USD units, exact selected accession numbers, `10-Q` facts with 80–100-day durations, `10-K` facts with 330–380-day durations, and `filed`/`end` dates at or before cutoff. Emit `quarterly` or `annual` basis only; normalize through `MetricNormalizer`; never emit a metric without an existing evidence ID.

- [ ] **Step 4: Run focused provider regression tests.**

Run: `uv run pytest -q packages/providers/tests`

Expected: PASS without live network access.

- [ ] **Step 5: Keep SEC XBRL changes uncommitted until Task 4 switches all callers.**

The new result type is not compatible with the existing collect step, so do not create a broken intermediate commit.

### Task 4: Collect-step integration and resumability

**Files:**
- Modify: `packages/agents/src/fathomark_agents/orchestrator.py`
- Modify: `packages/agents/tests/test_orchestrator.py`

- [ ] **Step 1: Write a failing orchestration test with a provider result containing evidence and a normalized observation.**

```python
state = orch.execute(run_id)
assert state == RunState.DRAFT
assert repo.metric_observations_of(run_id) == [observation]
assert steps["collect"].output_json["metric_observation_count"] == 1
```

- [ ] **Step 2: Run it and verify it fails because collection expects a list of evidence.**

Run: `uv run pytest -q packages/agents/tests/test_orchestrator.py -k metric_observation`

Expected: FAIL with a type/attribute error or absent persisted observations.

- [ ] **Step 3: Make collect aggregate `ProviderResult` values.**

Normalize evidence before observations. Use `canonical_id_by_input_id` to rewrite an observation reference when its evidence was deduplicated; if no retained evidence exists, fail the provider step explicitly. Persist observations only after their references validate. Update specialist prompt/run contracts and deterministic cassette fixtures so specialists receive sorted, structured observations beside evidence.

- [ ] **Step 4: Include metric identities only in downstream input hashes.**

Leave the collect input hash as scope/provider configuration so a successful recorded collect step remains idempotent; record a response fingerprint in its output instead. Include stable metric identity fields (metric, value, unit, currency, basis, data date, evidence ID) in specialist and compute hashes, forcing downstream recomputation when persisted facts change without causing collection to self-invalidate.

- [ ] **Step 5: Run orchestrator and full repository checks.**

Run: `uv run pytest -q packages/agents/tests/test_orchestrator.py && uv run ruff check . && uv run ruff format --check . && uv run pytest -q && git diff --check`

Expected: PASS; any PostgreSQL skips must report `PG_TEST_URL` as their sole reason.

- [ ] **Step 6: Commit the integrated vertical slice and update the roadmap precisely.**

```bash
git add TODO.md packages/agents packages/providers packages/storage
git commit -m "feat(agents): persist provider metric observations"
```
