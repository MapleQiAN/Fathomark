# Contributing

Fathomark is pre-1.0 and contracts may change. Start with an issue or a small
plan for behavior changes, especially changes to schemas, state transitions,
framework weights, provider boundaries, or report formats.

## Development

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests must be deterministic and must not require live providers, secrets,
external databases, or network access. Use `FakeLLMProvider`, cassette replay,
or injected provider transports. When changing the API, regenerate and test
`docs/api/openapi-v1.json` with `uv run python scripts/dump_openapi.py`.

## Pull requests

Describe the contract changed, evidence boundary, migration impact, and the
validation you actually ran. Preserve unrelated worktree changes. Do not
include paid or unauthorized data, credentials, generated local databases, or
provider responses containing secrets. A change is not complete merely because
local unit tests pass: state the live-provider, database, browser, and
deployment boundaries that remain unverified.
