# README scoring explainer and Chinese mirror — design

**Date:** 2026-09-19  
**Status:** Approved direction; ready for user review before implementation

## Objective

Make the README explain, vividly but truthfully, how Fathomark scores a single stock. The English README remains the primary landing page. A complete Simplified Chinese mirror makes the same project information independently accessible to Chinese readers.

The reader should understand the central promise in under a minute: evidence produces structured factor proposals; versioned deterministic code calculates scores and applies safeguards. The README must clearly distinguish this implemented core from the planned review-and-release workflow, where a person, not a model, approves an official result.

## Scope

1. Add a compact scoring explainer to `README.md`, after “What makes it different” and before the end-to-end pipeline.
2. Add `docs/assets/scoring-snapshot.svg`, a static, accessible decision-console illustration matching the selected visual direction.
3. Add `README.zh-CN.md`, a complete Chinese mirror of the English README after the English update.
4. Add reciprocal language links near the top of both documents.

## Reader experience

### English README section

Title: **How a score earns its grade**

The section uses a dark, dashboard-like SVG card. It presents a clearly labelled offline fixture snapshot, not a live market view or recommendation:

- `ADBE · offline golden fixture`
- `Core lens · 85.75 / A+`
- `Evidence confidence · high`
- `11 factors · Veto clear · human review required`

The alt text and accompanying copy state that this is a reproducibility example based on the recorded `adbe_2026-09-03` fixture.

Below it, a four-step reading path uses concise prose:

1. **Set the frame** — one ordinary listed operating company, a cutoff date and a named framework version.
2. **Turn evidence into proposals** — dated, source-linked evidence and counter-evidence support one 0–10 proposal for each of the 11 factors; gaps are declared rather than smoothed away.
3. **Calculate, then constrain** — the selected lens deterministically weights those proposals into a 100-point total and maps it to a rating. Veto and `NR` rules outrank the total: insufficient confidence yields `NR`; designated risk thresholds yield `X`.
4. **Review before release (planned workflow)** — the planned service keeps a score as a draft until a human approves an immutable version with its evidence trail and input hash. This is a design commitment, not a claim that the review service or report package is already running.

One short “different lenses, same evidence” sentence names `core`, `offensive` and `tactical` without reproducing their full weight tables. A link points readers who want the complete anchors, weights, thresholds and grade spectrum to `frameworks/common-stock.yaml`.

### Chinese mirror

`README.zh-CN.md` mirrors the complete English document’s heading order, diagrams, claims, links, scope and implementation-status boundaries. It translates prose, Markdown labels, alt text and human-readable Mermaid node labels naturally into Simplified Chinese while preserving technical identifiers (`common-stock@1.0.0`, `Veto`, `NR`, `A+`, API paths, file names and command lines) exactly where they identify a contract or executable artifact. Existing branded SVG artwork with embedded English microcopy is reused, with a complete Chinese surrounding explanation and Chinese `alt` text; no second asset is introduced merely to translate decorative labels.

The scoring section is translated as “一只股票如何获得它的评级”, uses the same asset and carries the same fixture disclaimer. It must not be a Chinese-only summary: readers should be able to learn the entire project from this document.

## Truth and safety boundaries

- The ADBE figure is only the checked offline fixture result: core lens `85.75 / A+`, high confidence and no Veto. It is not a current assessment, target, forecast, recommendation or live output.
- The implemented claim is limited to the deterministic scoring core in `packages/core`, `common-stock@1.0.0`, its tests and the offline fixture.
- Agents, provider integrations, review/release flow, report renderers and their production operation remain described as planned where the current README already marks them as such. The implemented core may be described only as its tested `ScoreSnapshot` evaluation; it must not be represented as a published or human-approved rating.
- The copy must never imply automated trading, return prediction or unreviewed rating publication.
- Do not include all 11 anchor definitions, lens weights or every rating band in the README. The framework file remains the canonical full specification.

## Visual and accessibility requirements

- Reuse the repository palette: navy `#0B172A`, deep teal, muted blue-grey and gold `#C9973E`; no remote images, scripts or generated screenshots.
- SVG includes a useful `<title>` and `<desc>` and is understandable through its surrounding Markdown copy and `alt` text.
- The illustration is legible on GitHub’s light and dark page chrome because it carries its own background and high-contrast text.
- This asset depicts an example snapshot, not a product screen; labels such as “offline golden fixture” and “illustrative snapshot” make that distinction explicit.

## Content invariants

Every scoring claim must agree with the current `frameworks/common-stock.yaml` and `packages/core/tests/test_golden_fixture.py`:

| Claim | Evidence of truth |
| --- | --- |
| 11 factors, 0–10 inputs and 100-point weighted ratings | `common-stock.yaml` factors, scale and lenses |
| Lenses are core, offensive and tactical | `common-stock.yaml` lenses |
| Veto thresholds beat an otherwise high total | `common-stock.yaml` veto rules and `test_veto.py` |
| insufficient confidence forces `NR` | `common-stock.yaml` and `test_veto.py` |
| ADBE core result is 85.75 / A+ with high confidence | `test_golden_fixture.py` |
| identical structured input returns the same snapshot/hash | `test_snapshot.py` |

## Non-goals

- No scoring-rule change, test-fixture change or product API/UI work.
- No investment advice, company update, market-data fetch or external provider claim.
- No generated image dependency and no full factor-table duplication.
- No new README status badge that suggests M2 or production components are complete.

## Acceptance criteria

1. English README has the new section, the static SVG renders on GitHub, and language navigation reaches the Chinese mirror.
2. Chinese README provides a complete, faithful mirror and links back to English.
3. The scoring section explains source-linked evidence, 11 structured inputs, deterministic weighting, Veto/`NR`, lens distinction and the planned human-approval gate without requiring the full framework table.
4. Fixture language explicitly identifies the 85.75 / A+ figure as offline and reproducible, not current or advisory.
5. All affected Markdown links and image paths resolve locally; the repository’s relevant tests and formatting/lint checks remain unaffected or pass where applicable.
6. Temporary `.superpowers/` brainstorming artifacts are not committed.
