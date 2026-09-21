# M4 Artifact Persistence Implementation Plan

**Goal:** Persist report artifacts and expose their immutable bytes through the
headless API without making the database depend on a filesystem layout.

- [x] Add failing repository, migration and API tests for idempotent uploads,
  manifest/content hashes, listing and downloads.
- [x] Add the portable `artifacts` table with binary content, status, manifest
  hash, content hash, size and idempotency key.
- [x] Add upload/list/download API routes with draft-versus-approved state
  guards and bounded base64 input.
- [x] Regenerate the pinned OpenAPI document and document SDK-facing routes.

Validation: all offline tests, Alembic head `0005`, Ruff and `git diff --check`
pass. Object storage, authentication and CDN delivery remain deployment
concerns; this slice is SQLite/PostgreSQL database-backed persistence.
