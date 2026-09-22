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
from fathomark_reporting import (
    build_artifact_manifest,
    render_factor_chart,
    render_html,
    render_pdf,
    render_report_bundle,
)

html = render_html(report, theme="print")
factor_svg = render_factor_chart(report, theme="dark")
pdf = render_pdf(report)
bundle = render_report_bundle(report)
manifest = build_artifact_manifest(report, bundle, template_version="report-1")
```

`render_pdf` loads Playwright lazily and sends the print-theme HTML through
Chromium. Install the optional dependency and browser binary before using it:
`uv sync --extra pdf && uv run playwright install chromium`. The function also
accepts an injected launcher for deterministic tests. `build_artifact_manifest`
hashes each rendered byte payload and binds it to the report model and snapshot.

For a target image, run the browser-backed release check against the exact
self-contained HTML that will be printed:

```bash
uv run --extra pdf python scripts/verify_pdf.py \
  --html /path/to/report.html \
  --output /tmp/report.pdf \
  --expected-text "ADBE Research Report" \
  --expected-text "DRAFT — NOT APPROVED"
```

The check exercises both a desktop and narrow viewport, requires the pinned
`Noto Sans CJK SC` font to be loaded, rejects document-level horizontal
overflow, rejects PDF pages without extractable text or font resources, and
checks that expected report text survives PDF generation. It is intentionally
separate from the injected launcher tests because only the deployment's
Chromium and font installation can establish those rendering properties.
On a macOS development host without fontconfig, add `--skip-fontconfig` for a
browser/PDF smoke test; the release command must keep the default strict font
check.

The reporting suite keeps golden SHA-256 hashes for JSON, Markdown and
print-theme HTML, a four-format bundle contract, responsive CSS markers and
basic Markdown/HTML accessibility contracts. These tests catch renderer drift;
they do not replace a browser visual-diff run.
