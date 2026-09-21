# M4 Report Visuals Implementation Plan

**Goal:** Add deterministic, dependency-free visual artifacts while preserving
one report model and an explicit PDF/browser boundary.

- [x] Add failing tests for factor charts, sensitivity matrices and score
  deltas.
- [x] Implement escaped, deterministic SVG helpers with light/dark/print
  palettes and shape validation.
- [x] Add explicit HTML `auto`, `light`, `dark` and `print` themes with print
  break rules.
- [x] Document the report/theme extension contract and remaining PDF boundary.

Validation: reporting tests and the full repository suite pass; no Chromium or
PDF claim is made by this slice.
