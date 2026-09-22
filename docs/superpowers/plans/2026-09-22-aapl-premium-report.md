# AAPL Premium Report Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self contained, complete, polished AAPL research HTML reader with an isolated scenario laboratory and generate a professional A4 PDF from the same document.

**Architecture:** A one-off Python builder under the ignored artifact directory invokes Pandoc to convert the supplied GFM Markdown into semantic HTML, embeds the two source images as data URIs, and wraps the result in a custom HTML/CSS/JavaScript research-reader shell. Playwright renders the same HTML with print media into the final PDF. Source hashes, heading/table/image counts, browser interaction checks, and PDF text/image/page checks protect completeness.

**Tech Stack:** Python 3.12 standard library, Pandoc, semantic HTML5, CSS, vanilla JavaScript, Playwright Chromium, pypdf, Poppler.

---

## File Structure

- Create (ignored artifact source): `dist/aapl-premium-report-2026-07-18/build_report.py` — reads source Markdown, converts and enriches it, writes HTML/PDF, and performs source-to-artifact validation.
- Create (deliverable): `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.html` — self contained interactive report.
- Create (deliverable): `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.pdf` — fixed A4 report.
- Create (verification only): `dist/aapl-premium-report-2026-07-18/verification/` — browser screenshots, rendered PDF pages, contact sheets, and validation JSON.
- Do not modify `packages/reporting`, the API, the CLI, the framework, or other production code.

### Task 1: Establish source completeness and deterministic conversion

**Files:**
- Create: `dist/aapl-premium-report-2026-07-18/build_report.py`
- Read: `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_长期核心仓研究_2026-07-18.md`
- Read: `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_五年情景回报.png`
- Read: `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_长期核心仓因子评分.png`

- [ ] **Step 1: Record the source contract**

In the builder, compute SHA-256 hashes and record exact source counts: 58 headings, 12 Markdown tables, 2 images, and the distinctive final sentence.

- [ ] **Step 2: Add a deliberate failing preflight**

Run the builder before its Pandoc conversion function exists.

Run: `uv run python dist/aapl-premium-report-2026-07-18/build_report.py --validate-only`

Expected: FAIL because conversion/output validation is not implemented.

- [ ] **Step 3: Implement deterministic Pandoc conversion**

Invoke `/usr/local/bin/pandoc --from=gfm --to=html5 --wrap=none --section-divs`, rewrite both image URLs to embedded `data:image/png;base64,...` payloads, and preserve the generated heading IDs.

- [ ] **Step 4: Validate the fragment**

Assert the converted fragment contains all source heading texts, exactly 12 `<table>` elements, exactly two source `<img>` elements, and the final sentence.

Run: `uv run python dist/aapl-premium-report-2026-07-18/build_report.py --validate-only`

Expected: PASS with source hashes and completeness counts.

### Task 2: Build the Modern Research Desk reader

**Files:**
- Modify: `dist/aapl-premium-report-2026-07-18/build_report.py`
- Create: `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.html`

- [ ] **Step 1: Add output assertions before the template exists**

Require the final HTML to contain the complete converted article plus controls identified by `data-action` values for search, theme, collapse, print, and section navigation.

- [ ] **Step 2: Implement the semantic page shell**

Create a self contained document with:

- warm off white, graphite, and teal design tokens;
- asymmetric cover/hero with frozen AAPL metadata and `79.60 / B+`;
- desktop sticky navigation and mobile chapter selector;
- reading progress bar;
- complete Pandoc article body;
- enhanced factor bars, scenario chart, and valuation sensitivity matrix;
- source-integrity footer with the three SHA-256 hashes.

- [ ] **Step 3: Implement reader interactions**

Use vanilla JavaScript for full text search/highlighting, next/previous result navigation, chapter collapse/expand, light/dark theme, reading progress, active TOC state, mobile navigation, and print.

- [ ] **Step 4: Preserve accessibility and motion preferences**

Add semantic landmarks, labeled controls, keyboard focus, skip link, `aria-expanded`, responsive tables, and `prefers-reduced-motion` handling.

- [ ] **Step 5: Run static HTML checks**

Run the builder and assert:

- no external stylesheet, script, image, or font URL;
- all 20 numbered top-level sections exist;
- all 12 source tables and both source images remain present;
- the HTML includes source report and experimental-lab labels.

Expected: PASS.

### Task 3: Implement the isolated scenario laboratory

**Files:**
- Modify: `dist/aapl-premium-report-2026-07-18/build_report.py`
- Modify generated: `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.html`

- [ ] **Step 1: Add browser assertions for frozen defaults**

Check the initial probabilities `25/55/20`, EPS `11.5/15.0/19.0`, terminal P/E `22/28/32`, cumulative dividends `7/7/8`, and current price `333.74`.

- [ ] **Step 2: Implement calculator formulas**

Calculate terminal values, total return, five-year annualized return, probability-weighted terminal value, and annualized return using the approved formulas and display rules.

- [ ] **Step 3: Implement validation and reset**

Show an inline error when probabilities do not total 100, disable weighted conclusions while invalid, and provide a reset button that restores every source value.

- [ ] **Step 4: Enforce the experiment boundary**

Label the lab `模拟实验，不属于正式报告结论`; keep report text, `79.60`, `B+`, source charts, and print output immutable.

- [ ] **Step 5: Exercise the interaction cycle in Playwright**

Test valid recalculation, invalid probability totals, reset, theme, search, section collapse, and `beforeprint` expansion.

Expected: every interaction passes and no browser console error is emitted.

### Task 4: Create the professional print system and PDF

**Files:**
- Modify: `dist/aapl-premium-report-2026-07-18/build_report.py`
- Create: `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.pdf`

- [ ] **Step 1: Add print media requirements**

Require the print output to hide application controls and the experimental lab while showing the complete article, print table of contents, original tables, and both source images.

- [ ] **Step 2: Implement A4 print CSS**

Add a cover, table of contents, repeated table headers, page-break rules for headings/figures/rows, print-safe colors, and forced-open report sections.

- [ ] **Step 3: Render through Playwright**

Use A4, background graphics, browser header/footer templates, page numbers, and margins suitable for running text.

- [ ] **Step 4: Verify PDF structure**

Use `pypdf` to assert:

- every page has extractable text except an intentional image-dominant page;
- all 20 numbered section headings and the final sentence are extractable;
- `79.60`, `B+`, `333.74`, `4.9%`, and key thresholds survive;
- interactive control labels and temporary simulated values do not appear.

Expected: PASS.

### Task 5: Visual and responsive quality assurance

**Files:**
- Create: `dist/aapl-premium-report-2026-07-18/verification/html-desktop.png`
- Create: `dist/aapl-premium-report-2026-07-18/verification/html-mobile.png`
- Create: `dist/aapl-premium-report-2026-07-18/verification/pdf-pages/`
- Create: `dist/aapl-premium-report-2026-07-18/verification/validation.json`

- [ ] **Step 1: Capture desktop and mobile HTML**

Use Playwright at 1440×1000 and 390×844. Assert document-level scroll width does not exceed viewport width.

- [ ] **Step 2: Render every PDF page**

Use `pdftoppm -png -r 120` and produce contact sheets for fast review.

- [ ] **Step 3: Inspect the visual output**

Check cover hierarchy, Chinese glyphs, long-table readability, figure sizing, page breaks, headers/footers, final page balance, dark theme, mobile navigation, and simulator error state.

- [ ] **Step 4: Fix only observed defects and repeat targeted checks**

Do not broaden scope into the reusable renderer. Re-render affected views after each correction.

- [ ] **Step 5: Save validation evidence**

Write artifact sizes, SHA-256 hashes, source counts, HTML viewport metrics, PDF page count, text lengths, and completed interaction checks to `verification/validation.json`.

Expected: all checks pass with no unresolved content omission or layout defect.

### Task 6: Final delivery

**Files:**
- Verify: `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.html`
- Verify: `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.pdf`

- [ ] **Step 1: Re-run the builder and validation from a clean artifact directory state**

Expected: deterministic HTML bytes and a valid PDF. PDF metadata may vary by Chromium and is recorded separately.

- [ ] **Step 2: Confirm repository scope**

Run: `git status --short`

Expected: only the approved spec/plan commits are tracked; production code is unchanged and the artifact directory remains ignored.

- [ ] **Step 3: Open both deliverables in Codex and report limitations**

State that this is a high fidelity prototype built from the supplied report, not yet the reusable Fathomark production renderer.
