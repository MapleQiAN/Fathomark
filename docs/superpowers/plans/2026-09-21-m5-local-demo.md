# M5 Local Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Fathomark runnable without an external database through an app-data SQLite default, a health endpoint, and a single Docker/Compose command.

**Architecture:** Configuration resolution stays in the API package: an explicit `DATABASE_URL` wins, otherwise a platform-aware app-data directory is created and a SQLite URL is returned. `fathomark_api.main` is a small ASGI entrypoint for local/Docker use; the Docker image copies the workspace packages and fixed framework/fixture data, while `/data` is the only mutable volume.

**Tech Stack:** FastAPI, Uvicorn, SQLAlchemy/SQLite, Docker, Docker Compose, pytest.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 11, 15, and M5 in `TODO.md`.

## Global Constraints

- No external database service is required for the default demo.
- `DATABASE_URL` remains an explicit override for PostgreSQL or a custom SQLite path.
- The image must not contain credentials or require live providers to start.
- Health checks must not touch the database or trigger research work.

### Task 1: Configuration and ASGI entrypoint

**Files:**
- Create: `packages/api/src/fathomark_api/config.py`
- Create: `packages/api/src/fathomark_api/main.py`
- Modify: `packages/api/src/fathomark_api/app.py`
- Modify: `packages/api/src/fathomark_api/__init__.py`
- Create: `packages/api/tests/test_app_config.py`
- Modify: `packages/api/pyproject.toml`

- [x] **Step 1: Write failing tests** for `DATABASE_URL` override, isolated app-data SQLite path, directory creation, and `/health`.
- [x] **Step 2: Implement configuration helpers, optional database URL in `create_app`, and the ASGI entrypoint.**
- [x] **Step 3: Add Uvicorn as the runtime dependency and lock the workspace.**
- [x] **Step 4: Run focused API tests and Ruff.**
- [x] **Step 5: Commit `feat(api): add zero-config SQLite app entrypoint`.**

### Task 2: Docker/Compose and quick start

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `docs/quickstart.md`
- Modify: `TODO.md`

- [x] **Step 1: Add a slim workspace image** with `/data` as the only mutable volume and a Uvicorn command.
- [x] **Step 2: Add Compose defaults** for one API container and a named SQLite data volume.
- [x] **Step 3: Document a five-minute start, health check, and `DATABASE_URL` override.**
- [x] **Step 4: Mark only the local startup/quick-start items complete; keep the full golden path and release/security items explicit.**
- [x] **Step 5: Run full tests, Ruff, diff checks, and a Dockerfile static inspection (live Docker build only if Docker is available).**
- [x] **Step 6: Commit `feat(demo): add self-contained Docker startup`.**
