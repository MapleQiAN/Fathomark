# README Scoring Explainer and Chinese Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accurate, visually distinctive English explanation of how Fathomark scores a stock and a complete Simplified Chinese README mirror.

**Architecture:** Keep executable scoring truth in `frameworks/common-stock.yaml` and core tests; documentation only summarizes it. A self-contained SVG renders the selected decision-console illustration in GitHub Markdown. `README.md` is the English source structure; `README.zh-CN.md` mirrors its headings, scope and planned-versus-implemented boundaries with reciprocal language navigation.

**Tech Stack:** GitHub-flavored Markdown, Mermaid, inline HTML, self-contained SVG, existing Python/uv test tooling.

---

## File structure

- Modify: `README.md` — primary English landing page, language link and compact scoring explanation.
- Create: `README.zh-CN.md` — complete Simplified Chinese mirror of the post-change README.
- Create: `docs/assets/scoring-snapshot.svg` — accessible static evidence/scoring snapshot; no script, external request or live-market implication.
- Reference only: `frameworks/common-stock.yaml`, `packages/core/tests/test_golden_fixture.py`, `packages/core/tests/test_veto.py`, `packages/core/tests/test_snapshot.py` — canonical truth for every score claim.

### Task 1: Lock documentation facts before authoring

**Files:**
- Reference: `frameworks/common-stock.yaml:7-119`
- Reference: `packages/core/tests/test_golden_fixture.py:23-35`
- Reference: `packages/core/tests/test_veto.py:19-50`
- Reference: `packages/core/tests/test_snapshot.py:115-149`

- [ ] **Step 1: Record the allowed claims in the implementation notes**

Use these exact constraints while writing; do not query market data or alter the fixture:

```text
11 factors; factor proposal scale 0.0–10.0 in 0.5 steps
three lenses: core, offensive, tactical
rating total: 0–100
ADBE offline fixture: core 85.75 / A+, confidence high, not vetoed
financial_health < 3.0 and governance < 3.0: Veto for all lenses
policy_risk < 3.0: Veto for core/offensive; flag only for tactical
insufficient confidence: NR and no total
same normalized structured input: same content hash/snapshot
```

- [ ] **Step 2: Run the fact-bearing tests before writing**

Run:

```bash
uv run pytest -q \
  packages/core/tests/test_golden_fixture.py \
  packages/core/tests/test_veto.py \
  packages/core/tests/test_snapshot.py
```

Expected: all selected tests pass. If an unrelated working-tree test is untracked or failing, do not stage, edit or attribute it to this documentation change.

### Task 2: Build the static score snapshot illustration

**Files:**
- Create: `docs/assets/scoring-snapshot.svg`

- [ ] **Step 1: Create an accessible, self-contained SVG**

Use a 1120-wide dark decision-console card. Include `<title>` and `<desc>`, an internal navy background (`#0B172A`), teal status surfaces, muted blue-grey labels and gold (`#C9973E`) accent rules. The visible contents must be exactly scoped as an example:

```text
FATHOMARK / OFFLINE GOLDEN FIXTURE
ADBE — reproducible score snapshot
Core lens        85.75 / A+
Evidence confidence    HIGH
11 evidence-backed factor proposals
Veto clear · planned human review required
Same structured input → same snapshot hash
```

Use actual text elements rather than raster content; do not show price, return, buy/sell language, a chart, a timestamp that resembles live data, or a product-control affordance. The words “offline golden fixture” and “planned human review required” must remain legible without the Markdown context.

- [ ] **Step 2: Validate SVG structure and local reference behavior**

Run:

```bash
rg -n '<title|<desc|OFFLINE GOLDEN FIXTURE|planned human review required|<script|https?://' docs/assets/scoring-snapshot.svg
```

Expected: title, description and all fixture/planned-review labels are present; no `<script>` and no `http`/`https` result is present.

- [ ] **Step 3: Commit the isolated visual asset**

```bash
git add docs/assets/scoring-snapshot.svg
git commit -m "docs: add scoring snapshot visual"
```

### Task 3: Add the English scoring explainer

**Files:**
- Modify: `README.md:1-62`

- [ ] **Step 1: Add language navigation beside the title**

Add a compact, centered `简体中文` link to `README.zh-CN.md`. It is navigation only; retain the project identity, badges and existing important status callout unchanged.

- [ ] **Step 2: Insert the visual scoring section after “What makes it different”**

Insert `## How a score earns its grade` between the three-card table and `## From question to report`. Render `docs/assets/scoring-snapshot.svg` with centered inline HTML, descriptive alt text and `width="100%"`.

Write four short, numbered paragraphs with these headings and exact semantic commitments:

```markdown
1. Set the frame — one ordinary listed operating company, cutoff date, `common-stock@1.0.0` framework version.
2. Ground every factor — dated, source-linked evidence and counter-evidence support one 0–10 proposal for each of 11 factors; declared gaps are not smoothed away.
3. Calculate, then constrain — a selected lens deterministically weights proposals to 100 points and maps a grade; Veto and NR override the total.
4. Review before release (planned workflow) — human approval/immutable release is a design commitment, not a running service claim.
```

Follow with one sentence that `core`, `offensive` and `tactical` reweight the same evidence for different research lenses, plus a source link to `frameworks/common-stock.yaml` for the complete anchors, weights, thresholds and grade spectrum. The image `alt` text and adjacent fixture note must name the recorded `adbe_2026-09-03` fixture. State that its ADBE score is a checked, offline reproducibility fixture—not a current rating, forecast, recommendation or trade instruction.

- [ ] **Step 3: Check rendered-document invariants in source**

Run:

```bash
rg -n -i \
  'README.zh-CN|How a score earns its grade|scoring-snapshot|offline|11 factors|Veto|NR|planned workflow|common-stock.yaml' \
  README.md
test -f docs/assets/scoring-snapshot.svg
```

Expected: every navigation, illustration and core safeguard is present, and the asset exists.

- [ ] **Step 4: Commit the English documentation change**

```bash
git add README.md
git commit -m "docs: explain deterministic stock scoring"
```

### Task 4: Create the complete Simplified Chinese README mirror

**Files:**
- Create: `README.zh-CN.md`
- Reference: `README.md`

- [ ] **Step 1: Translate the post-change document in the same heading order**

Translate all prose, tables, callout text, Markdown link labels, image alt text and human-readable Mermaid labels. Preserve literal contract names, grades, `Veto`, `NR`, API paths, filenames, commands, YAML keys and framework versions. Use the same assets and keep the existing design/progress boundaries accurate instead of translating planned work as delivered product capability.

Use the Chinese scoring heading `## 一只股票如何获得它的评级`. Translate the four steps so their meaning remains identical, including `规划中的工作流` for approval/release. Make the fixture disclaimer unambiguous: `ADBE` is an offline reproducibility example, neither a current judgment nor investment advice.

- [ ] **Step 2: Add reciprocal language navigation**

At the Chinese title area, link `English` to `README.md`. At the English title area, `简体中文` must point to `README.zh-CN.md`. Do not use absolute GitHub URLs; links must work in a cloned repository and rendered GitHub view.

- [ ] **Step 3: Verify translation parity and links**

Run:

```bash
rg -n '## ' README.md README.zh-CN.md
rg -n 'README\.md|README\.zh-CN\.md|scoring-snapshot\.svg|report-ribbon\.svg|common-stock\.yaml' README.md README.zh-CN.md
for path in docs/assets/scoring-snapshot.svg docs/assets/report-ribbon.svg frameworks/common-stock.yaml TODO.md docs/design/2026-09-18-fathomark-design.md; do test -e "$path"; done
```

Expected: both files have equivalent heading count/order; each listed local target exists. Manually read the Chinese scoring section and the two Mermaid diagrams to confirm reader-facing labels are Chinese while identifiers remain intact.

- [ ] **Step 4: Commit the Chinese mirror**

```bash
git add README.zh-CN.md
git commit -m "docs: add Chinese README"
```

### Task 5: Perform documentation and regression validation

**Files:**
- Modify only if validation exposes a defect: `README.md`, `README.zh-CN.md`, `docs/assets/scoring-snapshot.svg`

- [ ] **Step 1: Run focused scoring regression tests**

Run:

```bash
uv run pytest -q \
  packages/core/tests/test_golden_fixture.py \
  packages/core/tests/test_veto.py \
  packages/core/tests/test_snapshot.py
```

Expected: all pass; documentation did not alter the deterministic scoring contract.

- [ ] **Step 2: Run repository lint relevant to the documentation change**

Run:

```bash
uv run ruff check .
uv run ruff format --check .
git diff --check HEAD~3..HEAD
git status --short
```

Expected: Ruff commands pass when the repository baseline permits; `git diff --check` is clean; only this plan’s committed documentation files appear in recent commits. Report unrelated pre-existing or untracked files separately, without modifying them.

- [ ] **Step 3: Inspect the GitHub-facing render source**

Run:

```bash
git show --check --stat HEAD~3..HEAD
```

Expected: the diff contains only `README.md`, `README.zh-CN.md` and `docs/assets/scoring-snapshot.svg` (plus this already-approved plan/spec when viewing the broader branch); no `.superpowers/` artifact is staged or committed.

- [ ] **Step 4: Commit only a correction, if one was required**

```bash
git add README.md README.zh-CN.md docs/assets/scoring-snapshot.svg
git commit -m "docs: refine scoring explainer validation"
```

Skip this step if validation required no correction.
