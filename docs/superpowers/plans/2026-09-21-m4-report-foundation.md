# M4 Report Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create one validated `ReportModel` and deterministic JSON, GFM Markdown, and single-file HTML renderers from an approved or draft score snapshot.

**Architecture:** The reporting package receives immutable core models and never recalculates scores. `ReportModel` is the only rendering input and carries status, scope, lens results, factor proposals, evidence, and review issues. JSON, Markdown, and HTML are independently rendered from the same model and share a content hash for cross-format consistency checks.

**Tech Stack:** Python 3.12+, Pydantic, standard-library JSON/HTML escaping, pytest, Ruff.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 7, 12, and 16.4; `TODO.md` section 4.

## Global Constraints

- Report renderers never independently calculate totals, ratings, Veto, or confidence.
- Draft output must carry an unmistakable draft marker; approved output must carry the immutable snapshot hash.
- Evidence identifiers and excerpts remain traceable in every textual format.
- Rendered output is deterministic for the same `ReportModel`; no current-time field is added implicitly.
- HTML escapes untrusted evidence and rationale text and is self-contained without network assets.

---

### Task 1: Reporting package and validated model

**Files:**
- Create: `packages/reporting/pyproject.toml`
- Create: `packages/reporting/src/fathomark_reporting/model.py`
- Create: `packages/reporting/src/fathomark_reporting/__init__.py`
- Modify: `pyproject.toml`
- Create: `packages/reporting/tests/test_model.py`

- [ ] **Step 1: Write failing model tests.**

```python
report = ReportModel.from_snapshot(
    snapshot=snapshot,
    evidence=evidence,
    proposals=proposals,
    review_issues=issues,
    status="draft",
)
assert report.status == "draft"
assert report.snapshot_hash == snapshot.content_hash
assert report.factors[0].evidence_ids
```

- [ ] **Step 2: Run the focused test and verify the package is missing.**

Run: `uv run pytest -q packages/reporting/tests/test_model.py`

Expected: FAIL with an import error for `fathomark_reporting`.

- [ ] **Step 3: Implement immutable Pydantic model types.**

Define `ReportFactor`, `ReportEvidence`, `ReportLens`, `ReportModel` and `ReportModel.from_snapshot`. Copy all values from the supplied `ScoreSnapshot`, proposals, evidence and review issues; sort factors by factor ID, evidence by ID, and issues by category/factor/rationale. Add `model_hash` as a SHA-256 over canonical model JSON and export public types. Add `fathomark-reporting` to the workspace root dependencies and members.

- [ ] **Step 4: Run model tests and package checks.**

Run: `uv run pytest -q packages/reporting/tests/test_model.py && uv run ruff check packages/reporting && uv run ruff format --check packages/reporting`

Expected: PASS.

- [ ] **Step 5: Commit the report model.**

```bash
git add pyproject.toml packages/reporting
git commit -m "feat(reporting): add validated report model"
```

### Task 2: JSON and Markdown renderers

**Files:**
- Create: `packages/reporting/src/fathomark_reporting/renderers.py`
- Modify: `packages/reporting/src/fathomark_reporting/__init__.py`
- Create: `packages/reporting/tests/test_renderers.py`

- [ ] **Step 1: Write failing renderer tests.**

Assert `render_json(report)` parses to the same `model_hash`; `render_markdown(report)` starts with YAML metadata containing `status`, `symbol`, `framework_ref`, and `report_model_hash`; draft output contains `DRAFT — NOT APPROVED`; every evidence ID is present; and the same model renders the same bytes twice.

- [ ] **Step 2: Run the focused renderer tests and verify missing functions fail.**

Run: `uv run pytest -q packages/reporting/tests/test_renderers.py`

Expected: FAIL because `render_json` and `render_markdown` are not defined.

- [ ] **Step 3: Implement deterministic renderers.**

Serialize JSON with sorted keys and stable indentation. Render GFM headings, a lens table, a factor table, evidence footnotes, and review issues from model values only. Use `json.dumps` for safe YAML scalar quoting and keep line endings `\n`.

- [ ] **Step 4: Run renderer tests and package checks.**

Run: `uv run pytest -q packages/reporting/tests && uv run ruff check packages/reporting && uv run ruff format --check packages/reporting`

Expected: PASS.

- [ ] **Step 5: Commit JSON/Markdown.**

```bash
git add packages/reporting
git commit -m "feat(reporting): render json and markdown reports"
```

### Task 3: Single-file HTML renderer and roadmap update

**Files:**
- Modify: `packages/reporting/src/fathomark_reporting/renderers.py`
- Modify: `packages/reporting/tests/test_renderers.py`
- Modify: `TODO.md`

- [ ] **Step 1: Write failing HTML tests.**

Assert `render_html(report)` contains no external `http://`/`https://` asset reference, includes an accessible document title and table headers, escapes `<script>` in rationale/excerpts, includes the draft marker, and repeats the exact report model hash.

- [ ] **Step 2: Run the focused HTML test and verify it fails.**

Run: `uv run pytest -q packages/reporting/tests/test_renderers.py -k html`

Expected: FAIL because `render_html` is not defined.

- [ ] **Step 3: Implement a self-contained escaped HTML template.**

Use only standard-library `html.escape`; include inline CSS, semantic headings/tables, a status banner, lens/factor sections, evidence list, and review issue list. Do not add charts or PDF generation in this slice.

- [ ] **Step 4: Mark only the completed M4 items and validate the full repository.**

Mark `ReportModel`, machine JSON, GFM Markdown, and single-file HTML as complete; keep PDF, artifact manifest, accessibility automation, and visual testing unchecked. Run:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Expected: PASS; PostgreSQL skips remain limited to the configured integration absence.

- [ ] **Step 5: Commit the HTML slice.**

```bash
git add TODO.md packages/reporting
git commit -m "feat(reporting): add self-contained html renderer"
```

