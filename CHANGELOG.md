# Changelog

All notable changes to Fathomark are recorded here. Until the first tagged
release, entries are grouped under `Unreleased` and describe tested repository
capabilities rather than live-provider or production-deployment guarantees.

## Unreleased

### Added

- deterministic scoring core, versioned framework validation, and the ADBE
  public recorded fixture;
- SQLite-first API/storage with optional PostgreSQL, idempotent review and
  approval, HMAC webhooks, and persisted report artifacts;
- SEC EDGAR/XBRL, company IR, replaceable market-data and hosted LLM provider
  contracts with offline cassettes and explicit safety boundaries;
- deterministic JSON, Markdown, HTML, SVG and optional Playwright/Chromium PDF
  report outputs plus content-addressed manifests and a four-format bundle
  contract;
- Docker/SQLite quickstart with a pinned Noto CJK font, optional PostgreSQL
  Compose, the `fathomark` CLI, plugin auth/template scaffolding, CI migration
  checks, CycloneDX SBOM and `pip-audit` scanning.

### Known boundaries

- live provider availability, rate limits, licensing and credentials remain
  operator-configured;
- PDF pagination, Chinese font packaging and visual browser checks require a
  deployment with Chromium and the selected fonts;
- The CLI and plugin scaffolding are optional clients; the Vue review console
  remains intentionally outside the core v1 delivery.
