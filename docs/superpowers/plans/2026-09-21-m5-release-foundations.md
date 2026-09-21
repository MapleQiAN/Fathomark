# M5 Release Foundations Implementation Plan

**Goal:** Close the release-facing M5 foundations without claiming live-provider
or production deployment readiness.

## Tasks

- [x] Add Apache 2.0, notice, disclaimer, contribution, conduct and security
  policy files.
- [x] Document data-provider redistribution boundaries, LLM provider contracts,
  API/SDK usage, and framework validation.
- [x] Add an optional PostgreSQL Compose override with a health-gated database
  and a locked `psycopg` image extra.
- [x] Extend CI with clean-install storage-wheel migration validation.
- [x] Export a locked CycloneDX SBOM and audit the pinned runtime dependency
  set with `pip-audit`.

## Validation boundary

Local validation covered Compose configuration, a live PostgreSQL Compose health
check, isolated storage-wheel `migrate_db`, SBOM generation, `pip-audit`, all
repository tests, Ruff and diff checks. It does not prove external provider
availability, production secrets management, or a public release process.
