# LLM provider development

Implement the `LLMProvider` protocol in `packages/providers` and return an
`LLMResponse` with text, model identity and non-negative usage when the
provider supplies it. Adapters may translate request envelopes and parse
responses; they may not calculate scores, bypass Pydantic contracts, or write
storage rows.

Provider failures must be explicit and classified as retriable or
non-retriable. Use injected transports for tests. Keep timeouts, call counts,
token limits, cost limits and runtime limits at the host/orchestrator boundary.

For deterministic tests, use `FakeLLMProvider` or `ReplayLLMProvider`. Build a
cassette with `scripts/build_cassette.py`; inspect it for secrets and license
permissions before committing. Never record API keys, authorization headers,
private prompts, paid source text, or personal data.
