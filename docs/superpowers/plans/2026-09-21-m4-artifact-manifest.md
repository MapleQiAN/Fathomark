# M4 Artifact Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic manifest builder that binds every exported report artifact to one validated report model and content hash.

**Architecture:** The reporting package receives already-rendered bytes/text and produces an immutable `ArtifactManifest`; it never reads or writes files and never recalculates report values. Artifact names, byte sizes, media types, SHA-256 hashes, report identity, and a manifest hash are canonicalized for reproducible storage or API integration later.

**Tech Stack:** Python 3.12+, Pydantic, standard-library hashlib/JSON, pytest, Ruff.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 7 and 12; `TODO.md` M4 artifact manifest item.

## Global Constraints

- Manifest content must be deterministic for the same report model and artifact bytes.
- The manifest must bind `report_model_hash`, `snapshot_hash`, `framework_ref`, status, and template version.
- Artifact names must be single path components; no traversal or platform separator is accepted.
- The manifest must preserve UTF-8 byte lengths and never include artifact contents or secrets.

## Review Focus

- Unicode text uses UTF-8 byte length, not Python character count.
- Different bytes under the same name produce different hashes.
- Path traversal and empty names are rejected before hashing.
- Mutating a copied report after manifest creation is detected by report integrity verification.
- JSON output and artifact ordering remain byte-for-byte deterministic.

### Task 1: Manifest model and builder

**Files:**
- Create: `packages/reporting/src/fathomark_reporting/manifest.py`
- Modify: `packages/reporting/src/fathomark_reporting/__init__.py`
- Create: `packages/reporting/tests/test_manifest.py`

- [x] **Step 1: Write failing tests** for deterministic hashes, metadata binding, UTF-8 size, invalid names, and integrity checks.
- [x] **Step 2: Run the focused tests and confirm the module is missing.**
- [x] **Step 3: Implement immutable `ArtifactManifestEntry`, `ArtifactManifest`, and `build_artifact_manifest`.**
- [x] **Step 4: Run focused tests and Ruff.**
- [x] **Step 5: Commit `feat(reporting): add deterministic artifact manifests`.**

### Task 2: Roadmap bookkeeping and full validation

**Files:**
- Modify: `TODO.md`
- Modify: this plan

- [x] **Step 1: Mark manifest/content-hash coverage complete while recording that DB/API artifact persistence remains a follow-up.**
- [x] **Step 2: Run `uv run pytest -q`, Ruff check/format, and `git diff --check`.**
- [x] **Step 3: Commit `docs: record artifact manifest coverage`.**
