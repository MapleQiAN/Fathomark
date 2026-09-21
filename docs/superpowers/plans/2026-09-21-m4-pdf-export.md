# M4 PDF Export Implementation Plan

**Goal:** Add a print-theme PDF boundary that uses Playwright/Chromium when a
deployment opts into the browser extra, while keeping the default test suite
offline and browser-free.

- [x] Add a failing renderer contract test using an injected launcher.
- [x] Implement `render_pdf` with print HTML, lazy Playwright loading, A4
  print settings and an injectable launcher seam.
- [x] Add the `pdf` optional dependency and installation guidance.

Validation: full offline suite, Ruff and diff checks pass. CI verifies the
renderer contract with an injected launcher; it does not download or launch a
Chromium binary, so pagination/font/overflow checks remain deployment-level
follow-up work.
