# Plugin development

Fathomark plugins are replaceable clients of host-owned contracts. A plugin
must not write the core database, change framework weights, publish an
approved version, or treat retrieved text as executable instructions.

Use the CLI to create a starting contract:

```bash
uv run fathomark plugin contract-template --kind data > provider.py
uv run fathomark plugin contract-template --kind llm > model.py
uv run fathomark plugin contract-template --kind theme > theme.py
```

Use environment-backed credentials and verify the configuration without
printing secrets:

```bash
export EXAMPLE_API_KEY='set-this-outside-the-repository'
uv run fathomark plugin auth --provider example --env-var EXAMPLE_API_KEY
```

## Contract test boundary

Provider tests should inject transport or replay data and assert:

- valid structured output and stable provider identity;
- non-negative usage and explicit retriable/non-retriable failures for LLMs;
- HTTPS/allowlist, cutoff, freshness, duplicate and provenance rules for data;
- no credentials, private data, or unauthorized paid responses in fixtures;
- no writes outside the host-owned API boundary.

The repository's provider tests under `packages/providers/tests` are the
reference contract tests. The generated templates are scaffolding, not a
claim that a provider is production-ready.

