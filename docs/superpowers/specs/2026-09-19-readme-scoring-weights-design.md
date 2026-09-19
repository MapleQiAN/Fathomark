# README scoring weights map and matrix — design

**Date:** 2026-09-19  
**Status:** Approved direction; ready for review before implementation

## Objective

Extend the existing scoring explainer so readers can see both the overall emphasis and every precise weight in `common-stock@1.0.0`. The presentation combines a visual 100% weight map (C) with a complete side-by-side matrix (A), rather than forcing readers to open YAML for the central answer.

## Scope

1. Add `docs/assets/scoring-weights.svg`, a static, accessible three-bar 100% stacked weight map.
2. Add an English “The 11 factors and their weights” subsection to the existing scoring block in `README.md`.
3. Add the equivalent Chinese subsection, “11 个因子与它们的权重”, in `README.zh-CN.md`.
4. Keep both documents in heading order and content parity.

## Visual weight map

The new SVG sits immediately before the matrix. It shows three complete horizontal bars using the shared Fathomark navy, teal, gold and blue-grey palette:

| Lens | Fundamentals | Growth / valuation | Market |
| --- | ---: | ---: | ---: |
| `core` | 64% | 27% | 9% |
| `offensive` | 37% | 49% | 14% |
| `tactical` | 13% | 16% | 71% |

The map answers “what does each lens emphasize?” It includes a small legend for the three category groups and a text note that every row totals 100%. It must not be an interactive dashboard, live price chart, recommendation, backtest or product UI screenshot.

## Complete weight matrix

The matrix follows the visual and contains these exact framework weights:

| Factor | Category | Core | Offensive | Tactical |
| --- | --- | ---: | ---: | ---: |
| Business moat | Fundamentals | 22% | 15% | 3% |
| Financial health | Fundamentals | 22% | 8% | 8% |
| Governance | Fundamentals | 12% | 8% | 2% |
| Policy risk | Fundamentals | 8% | 6% | 0% |
| Growth sustainability | Growth / valuation | 5% | 24% | 0% |
| Valuation | Growth / valuation | 11% | 17% | 10% |
| Earnings quality | Growth / valuation | 11% | 8% | 6% |
| Trend / momentum | Market | 1% | 5% | 20% |
| Liquidity | Market | 2% | 3% | 16% |
| Volatility / downside | Market | 6% | 2% | 13% |
| Catalyst window | Market | 0% | 4% | 22% |
| **Total** |  | **100%** | **100%** | **100%** |

The Chinese matrix translates human-readable factor and category labels naturally, while retaining `core`, `offensive` and `tactical` as framework lens identifiers.

## Reader guidance and truth boundaries

The text below the matrix states all of the following:

- Every lens reweights the same evidence-backed 0–10 proposals; weights are not a new source of evidence or a shortcut around review.
- `core` prioritizes business quality and financial resilience; `offensive` prioritizes growth and valuation; `tactical` prioritizes timing, liquidity, downside and catalysts.
- Veto/`NR` checks remain upstream of the final grade and cannot be offset by a high weight or high score elsewhere.
- Weights come from the versioned `frameworks/common-stock.yaml`; changes require a framework version change, not a README edit.
- The ADBE fixture remains an offline reproducibility example, never a live assessment or investment instruction.

## Accessibility and validation

- The SVG has a meaningful `<title>`, `<desc>`, `role="img"`, high contrast, no script and no remote assets.
- The Markdown table remains the canonical readable and copyable numerical representation; the image is explanatory, not the only source of a number.
- Every matrix value and category total must be checked against `frameworks/common-stock.yaml` before and after editing.
- The existing deterministic scoring tests must continue to pass; this work changes no scoring data, YAML, code or fixture.

## Non-goals

- No modification to factor definitions, anchors, lens weights, Veto/`NR` thresholds, rating bands or API behavior.
- No new investment recommendation, ranking, screen, market-data integration or agent claim.
- No duplication of all factor anchors in the README; YAML remains the full contract.
