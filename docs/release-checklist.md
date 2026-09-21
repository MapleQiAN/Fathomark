# Release checklist

Use this checklist for a tagged release. A checked local test is evidence for
the repository contract only; it does not certify external providers or a
production deployment.

## Required before tagging

- [x] `uv run pytest -q` passes with no unexpected failures.
- [x] `uv run ruff check .` and `uv run ruff format --check .` pass.
- [x] `git diff --check` is clean and the OpenAPI snapshot is current.
- [x] `docker compose config` and the optional PostgreSQL override validate.
- [x] The clean storage wheel applies the Alembic head migration.
- [x] CI exports the locked SBOM and runs `pip-audit`.
- [ ] Review live-provider terms, user-agent/rate-limit settings and secrets in
      the deployment environment.
- [ ] Run Chromium PDF pagination/font/overflow checks in the target image.
- [ ] Create a signed Git tag and publish release notes after maintainer
      approval.

## Do not claim

- A recorded fixture is not a current market view or investment instruction.
- Passing offline tests does not prove provider uptime, database operations,
  browser rendering or production authentication.
