# M4 Report Contract Tests Implementation Plan

**Goal:** Lock deterministic report output and basic offline accessibility
contracts without presenting string/hash tests as browser visual validation.

- [x] Add golden hashes for JSON, Markdown and print-theme HTML generated from
  the canonical ADBE report model.
- [x] Add Markdown whitespace/heading checks and cross-format evidence/hash
  identity assertions.
- [x] Add offline HTML `lang`, viewport, table-header-scope and no-external-
  resource checks.

Validation: reporting tests and the full offline suite pass. Real browser
visual regression, PDF pagination, fonts and overflow remain deployment-level
checks.
