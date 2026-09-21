# M5 Release Readiness Implementation Plan

**Goal:** Make the recorded public fixture, SDK artifact boundary and release
notes/checklist usable without implying live-provider or production readiness.

- [x] Add fixture attribution and offline-replay instructions.
- [x] Add SDK upload/list/download helpers for persisted report artifacts.
- [x] Add `CHANGELOG.md`, a release checklist and explicit known boundaries.
- [x] Mark the evidence-backed M5 completion criteria in `TODO.md`.

Validation: the complete offline suite, Ruff and diff checks pass. Maintainer
signing, live-provider terms, target-image browser checks and deployment
secrets remain intentionally manual release gates.
