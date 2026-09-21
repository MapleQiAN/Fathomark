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
from fathomark_reporting import render_factor_chart, render_html, render_pdf

html = render_html(report, theme="print")
factor_svg = render_factor_chart(report, theme="dark")
pdf = render_pdf(report)
```

`render_pdf` loads Playwright lazily and sends the print-theme HTML through
Chromium. Install the optional dependency and browser binary before using it:
`uv sync --extra pdf && uv run playwright install chromium`. The function also
accepts an injected launcher for deterministic tests. `build_artifact_manifest`
hashes each rendered byte payload and binds it to the report model and snapshot;
browser-level visual regression and production font validation remain separate
deployment checks.
