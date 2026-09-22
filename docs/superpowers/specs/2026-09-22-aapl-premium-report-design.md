# AAPL Premium Report Artifact Design

**Date:** 2026-09-22  
**Status:** Approved for artifact implementation  
**Scope:** One high fidelity AAPL HTML/PDF artifact; no Fathomark production renderer changes

## Goal

Create a polished, professional, young, and comfortable research report from:

- `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_长期核心仓研究_2026-07-18.md`
- `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_五年情景回报.png`
- `/Users/serendylin/Documents/PersonalInvestment/research/AAPL_长期核心仓因子评分.png`

The HTML and PDF must include the complete Markdown content. The HTML must add a professional reader and a separate interactive scenario laboratory. The PDF must remain a fixed, formal report containing only the source report's original figures and assumptions.

## Selected Direction

Use the approved **Modern Research Desk** direction:

- warm off white canvas;
- graphite text;
- one restrained teal accent;
- Chinese sans serif typography;
- generous line height and calm spacing;
- thin borders and limited shadows;
- data first hierarchy without a dense trading terminal appearance.

The interface should feel contemporary and useful while preserving the authority of an investment research document.

## Content Contract

The original Markdown is the narrative source of truth. The artifact must preserve:

- the title, preface, basic information, and all 20 numbered sections;
- every paragraph, blockquote, list, code block, heading, horizontal rule, and table;
- the two supplied chart images in their original semantic positions;
- the original score, rating, assumptions, thresholds, risks, monitoring items, and final conclusion;
- the report's humorous sentences and symbols because they are part of the supplied content.

Enhancement components may restate data for navigation or visualization, but they may not replace or silently alter the source text.

## Artifact Architecture

```text
Source Markdown + two local images
                |
                v
      deterministic document parser
                |
                v
     complete semantic HTML document
        |                       |
        v                       v
interactive reader       print stylesheet
and scenario lab          and Chromium PDF
```

The HTML must be a self contained file. Styles, scripts, icons, and both images are embedded. It must not require a network connection or external font download.

## HTML Experience

### Reader shell

- sticky desktop navigation rail with all top level sections;
- compact mobile section navigator;
- reading progress indicator;
- full text search with result count and highlighted matches;
- expand/collapse controls for long sections;
- light and dark themes with the light theme as default;
- print and PDF entry points;
- keyboard accessible controls, focus indicators, and reduced motion support.

### Report overview

The opening view surfaces the frozen report facts:

- AAPL / NASDAQ / research date;
- `79.60 / 100`, `B+`, long term core candidate;
- current reference price, current role cap, and target exploratory position;
- concise conclusion: `核心仓级资产，候选仓级价格`;
- original five year scenario values and factor summary.

### Data presentation

- visual factor bars with exact values and Chinese factor labels;
- scenario return chart with exact pessimistic, base, optimistic, and probability weighted values;
- valuation sensitivity matrix;
- responsive tables with sticky headers where useful;
- optional chart/table views without removing the original tables.

### Scenario laboratory

The laboratory is visually and semantically separate from the formal report. It provides editable inputs for:

- scenario probability;
- 2031 EPS;
- terminal P/E;
- cumulative dividend;
- current price.

It calculates scenario terminal value, total return, annualized return, and probability weighted results in the browser. Requirements:

- initial values exactly match the source report;
- a reset control restores source values;
- probability totals must be shown and invalid totals must produce an inline error;
- experimental results carry an explicit `模拟实验，不属于正式报告结论` label;
- experimental values never rewrite the report body, score, rating, or PDF.

Use these formulas for the five year laboratory:

```text
terminal value = 2031 EPS × terminal P/E + cumulative dividend
total return = terminal value ÷ current price - 1
annualized return = (terminal value ÷ current price)^(1/5) - 1
probability weighted terminal value = Σ(probability × scenario terminal value)
probability weighted annualized return =
  (probability weighted terminal value ÷ current price)^(1/5) - 1
```

Show currency to two decimals in editable/result detail and percentages to one decimal in summary views. Preserve the source report exactly where its table shows a `+5.1%` base annualized return while the supplied image labels the same scenario `5.0%`; the artifact must not silently normalize that source discrepancy. The simulator's formula result rounds to one decimal independently.

## PDF Experience

The PDF is rendered from the same complete HTML document under a dedicated print stylesheet. It includes:

- a professional A4 cover;
- report metadata and draft/source note;
- a complete table of contents;
- every source Markdown section and table;
- both supplied images;
- page numbers and restrained running headers/footers;
- repeated table headers across pages;
- controlled page breaks around headings, figures, blockquotes, and table rows;
- static source scenario values only.

Interactive controls, search UI, sticky navigation, dark theme controls, and the editable laboratory are omitted from print. A short appendix may explain that an interactive laboratory exists in the HTML, without printing temporary simulated values.

Print preparation must force every report section open before pagination, regardless of its interactive collapsed state, so the PDF cannot omit hidden source text.

## Integrity and Safety

- Copy source text without adding new market facts.
- Display the report date and data cutoff prominently.
- Keep research assumptions distinct from company guidance.
- Preserve the document's decision support framing.
- Embed the SHA-256 hashes of the source Markdown and two images in artifact metadata.
- Validate that every source heading and table is present in the HTML and extractable from the PDF.

## Verification

### Content

- compare parsed headings with the source Markdown;
- compare table counts, image counts, and distinctive closing text;
- verify exact score, rating, scenario values, and important thresholds;
- verify source hashes in embedded metadata.

### HTML

- inspect desktop and narrow layouts;
- confirm no document level horizontal overflow;
- exercise navigation, search, collapse, theme, print, reset, and simulator validation;
- confirm the file works with network disabled.

### PDF

- render every page to images and inspect cover, tables, figures, and page breaks;
- reject blank or nearly blank accidental pages;
- verify Chinese glyph rendering and extractable text;
- confirm page numbers, repeated headers, and absence of interactive controls;
- confirm all 20 sections and both images appear.

## Deliverables

- `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.html`
- `dist/aapl-premium-report-2026-07-18/AAPL_长期核心仓研究.pdf`
- preview images used only for visual verification

The deliverable is an artifact prototype. Any later change to the reusable Fathomark renderer requires a separate design based on the accepted prototype.
