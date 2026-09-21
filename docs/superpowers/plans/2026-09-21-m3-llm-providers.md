# M3 LLM Provider Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dependency-light OpenAI, Anthropic, and OpenAI-compatible `LLMProvider` adapters with deterministic request contracts, normalized responses, and offline HTTP tests.

**Architecture:** Keep the existing provider protocol and `LLMRequest`/`LLMResponse` models unchanged. A small standard-library JSON transport owns HTTP error classification; three adapters only build provider-specific payloads and parse response envelopes. Tests inject a fake transport, so CI never needs network access or secrets.

**Tech Stack:** Python 3.12+, `urllib.request`, JSON, pytest, Ruff.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` sections 13 and 14; `TODO.md` section 3.

## Global Constraints

- Providers must implement the existing `LLMProvider.complete(request) -> LLMResponse` contract.
- CI and the deterministic core must not require live network calls, provider SDKs, or secrets.
- Provider failures must become `ProviderError` with an explicit `retriable` flag.
- Provider adapters may parse provider envelopes but may not calculate scores or bypass host-side schema validation.
- API keys must never be written to cassettes, response models, or exception messages.

## Review Focus

- HTTP 429/5xx must be retryable while authentication and malformed-response failures are not.
- Empty or malformed provider content must fail closed rather than return an empty successful response.
- Token usage must remain zero when a provider omits usage, and must be copied when present.
- OpenAI-compatible endpoints must be configurable without changing the request contract.
- Missing credentials must fail before any network request and must not echo the secret.

### Task 1: Shared JSON HTTP transport

**Files:**
- Create: `packages/providers/src/fathomark_providers/remote_llm.py`
- Create: `packages/providers/tests/test_remote_llm.py`

**Interfaces:**
- `JsonHttpTransport.post_json(url: str, *, headers: dict[str, str], payload: dict[str, object], timeout_seconds: float) -> object`
- `_UrllibJsonTransport` implements the interface and maps HTTP/network/JSON failures to `ProviderError`.

- [x] **Step 1: Write failing transport tests** for successful JSON, retryable 429/503, non-retryable 401, and malformed JSON.
- [x] **Step 2: Run `uv run pytest -q packages/providers/tests/test_remote_llm.py` and confirm the new module is missing.**
- [x] **Step 3: Implement the transport and common envelope helpers** without adding an SDK dependency.
- [x] **Step 4: Run the focused tests and Ruff.**
- [x] **Step 5: Commit `feat(providers): add dependency-free JSON transport`.**

### Task 2: OpenAI-family adapters

**Files:**
- Modify: `packages/providers/src/fathomark_providers/remote_llm.py`
- Modify: `packages/providers/src/fathomark_providers/__init__.py`
- Modify: `packages/providers/tests/test_remote_llm.py`

**Interfaces:**
- `OpenAIProvider(*, model: str, api_key: str | None = None, endpoint: str = "https://api.openai.com/v1/chat/completions", transport: JsonHttpTransport | None = None, timeout_seconds: float = 30.0)`
- `OpenAICompatibleProvider(*, endpoint: str, model: str, api_key: str | None = None, transport: JsonHttpTransport | None = None, timeout_seconds: float = 30.0)`

- [x] **Step 1: Write failing payload/response tests** for OpenAI and compatible adapters, including usage mapping, missing credentials, and malformed choices.
- [x] **Step 2: Run the focused tests and verify the adapters are absent.**
- [x] **Step 3: Implement shared OpenAI-chat-completions construction/parsing** and export both adapters.
- [x] **Step 4: Run provider tests and Ruff.**
- [x] **Step 5: Commit `feat(providers): add OpenAI-compatible LLM adapters`.**

### Task 3: Anthropic adapter and roadmap update

**Files:**
- Modify: `packages/providers/src/fathomark_providers/remote_llm.py`
- Modify: `packages/providers/src/fathomark_providers/__init__.py`
- Modify: `packages/providers/tests/test_remote_llm.py`
- Modify: `TODO.md`

**Interfaces:**
- `AnthropicProvider(*, model: str, api_key: str | None = None, endpoint: str = "https://api.anthropic.com/v1/messages", transport: JsonHttpTransport | None = None, timeout_seconds: float = 30.0)`

- [x] **Step 1: Write failing Anthropic request/response tests** for headers, content blocks, usage, missing content, and non-leaking errors.
- [x] **Step 2: Implement the adapter and export it.**
- [x] **Step 3: Mark the three M3 provider TODO entries complete with the offline-contract boundary noted.**
- [x] **Step 4: Run the full test suite, Ruff, format, and `git diff --check`.**
- [x] **Step 5: Commit `feat(providers): add Anthropic adapter`.**

## Validation

The completed branch must pass `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check`. Live provider calls remain an operator-controlled validation step and are not claimed by these tests.
