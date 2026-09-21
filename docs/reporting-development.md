# Report and theme development

`ReportModel` is the single validated input for JSON, Markdown and HTML. Build
it from one snapshot plus the exact evidence, proposals and review issues; do
not let a renderer recalculate scores or silently add facts. `model_hash` and
`snapshot_hash` make tampering visible before rendering.

The HTML renderer accepts an explicit theme: `auto` (the default), `light`,
`dark`, or `print`. Every output is self-contained, escapes untrusted text,
declares a viewport, labels table headers with scopes, and includes print
break rules. The SVG helpers in `fathomark_reporting.charts` provide
deterministic factor bars, valuation sensitivity matrices, and before/after
score deltas without a browser or charting dependency.

```python
from fathomark_reporting import render_factor_chart, render_html

html = render_html(report, theme="print")
factor_svg = render_factor_chart(report, theme="dark")
```

`build_artifact_manifest` hashes each rendered byte payload and binds it to the
report model and snapshot. PDF/Chromium export, persisted artifact rows, and
browser-level visual regression remain follow-up work; do not describe these
SVG or HTML checks as a PDF or production browser validation.
