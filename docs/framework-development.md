# Scoring framework development

Framework files live in `frameworks/` and are loaded by
`fathomark_core.load_framework`. A framework version owns factor definitions,
lens weights, score anchors, Veto rules, confidence thresholds, freshness
policy, and rating mapping. The deterministic core is the source of truth;
agents only propose factor scores with evidence references.

When changing a framework:

1. Copy the existing file to a new semantic version; do not mutate an approved
   version in place.
2. Keep factor IDs, weights and thresholds explicit and make every lens sum to
   1.0.
3. Add boundary, invalid-configuration, Veto, confidence and golden-fixture
   tests under `packages/core/tests`.
4. Rebuild or add a fixture only when its data and redistribution terms allow
   it. Record the cutoff date and expected content hash.
5. Run `uv run pytest -q packages/core` and the full repository checks.

Framework changes are research-contract changes. Explain why a weight or
threshold moved and do not describe a new score as a historical performance
result without a reproducible, externally sourced study.
