"""Deterministic report renderers with one validated input model."""

import json
from html import escape

from fathomark_reporting.model import ReportModel


def render_json(report: ReportModel) -> str:
    """Return canonical, machine-readable JSON for a report model."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: ReportModel) -> str:
    """Render portable GFM with YAML metadata and evidence footnotes."""
    status_label = "DRAFT — NOT APPROVED" if report.status == "draft" else "APPROVED"
    lines = [
        "---",
        f"status: {_yaml_string(report.status)}",
        f"symbol: {_yaml_string(report.scope.symbol)}",
        f"framework_ref: {_yaml_string(report.scope.framework_ref)}",
        f"report_model_hash: {_yaml_string(report.model_hash)}",
        f"snapshot_hash: {_yaml_string(report.snapshot_hash)}",
        "---",
        "",
        f"# {report.scope.symbol} Research Report",
        "",
        f"> **{status_label}**",
        "",
        "## Scope",
        "",
        f"- Exchange: `{report.scope.exchange}`",
        f"- Research role: `{report.scope.research_role}`",
        f"- Horizon: `{report.scope.horizon}`",
        f"- Research date: `{report.scope.research_date.isoformat()}`",
        f"- Data cutoff: `{report.scope.data_cutoff.isoformat()}`",
        f"- Overall confidence: **{report.overall_confidence}**",
        "",
        "## Lens results",
        "",
        "| Lens | Total | Rating | Tactical state | Vetoed |",
        "| --- | ---: | --- | --- | --- |",
    ]
    lines.extend(
        "| {lens} | {total} | {rating} | {tactical} | {vetoed} |".format(
            lens=_cell(lens.lens),
            total=_cell(lens.total if lens.total is not None else "NR"),
            rating=_cell(lens.rating),
            tactical=_cell(lens.tactical_state or "—"),
            vetoed="yes" if lens.vetoed else "no",
        )
        for lens in report.lenses
    )
    lines.extend(
        [
            "",
            "## Factor proposals",
            "",
            "| Factor | Score | Confidence | Evidence |",
            "| --- | ---: | --- | --- |",
        ]
    )
    lines.extend(
        "| {factor} | {score} | {confidence} | {evidence} |".format(
            factor=_cell(factor.factor),
            score=_cell(factor.proposed_score),
            confidence=_cell(factor.confidence),
            evidence=_cell(
                ", ".join(f"[^{item}]" for item in factor.evidence_ids) or "—"
            ),
        )
        for factor in report.factors
    )
    lines.extend(["", "### Rationale", ""])
    for factor in report.factors:
        lines.append(f"- **{factor.factor}:** {factor.rationale}")

    lines.extend(["", "## Evidence", ""])
    for item in report.evidence:
        excerpt = f" — {item.excerpt}" if item.excerpt else ""
        lines.append(
            f"[^{item.id}]: {item.source_name} ({item.published_date.isoformat()}, grade {item.grade}){excerpt}"
        )

    if report.review_issues:
        lines.extend(["", "## Review issues", ""])
        for issue in report.review_issues:
            blocking = "blocking" if issue.blocking else "non-blocking"
            refs = (
                ", ".join(f"[^{item}]" for item in issue.evidence_ids) or "no evidence"
            )
            lines.append(
                f"- **{issue.category} ({blocking})** — {issue.rationale} ({refs})"
            )
    return "\n".join(lines) + "\n"


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def render_html(report: ReportModel) -> str:
    """Render a self-contained HTML report with escaped untrusted content."""
    status_label = "DRAFT — NOT APPROVED" if report.status == "draft" else "APPROVED"
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_html(report.scope.symbol)} Research Report</title>",
        "<style>",
        ":root{color-scheme:light dark;font-family:system-ui,sans-serif;line-height:1.5}",
        "body{max-width:1100px;margin:0 auto;padding:2rem;background:#fff;color:#17212b}",
        "@media(prefers-color-scheme:dark){body{background:#17212b;color:#f4f7f9}}",
        "table{border-collapse:collapse;width:100%;margin:1rem 0 2rem}",
        "th,td{border:1px solid #b8c4cc;padding:.5rem;text-align:left;vertical-align:top}",
        "th{background:#e8eef2}",
        ".status{border:2px solid #b7791f;padding:.75rem;font-weight:700}",
        ".hash{font-family:ui-monospace,monospace;overflow-wrap:anywhere}",
        "</style>",
        "</head>",
        "<body>",
        f"<header><h1>{_html(report.scope.symbol)} Research Report</h1>",
        f'<p class="status">{_html(status_label)}</p>',
        f'<p class="hash">Report model: {_html(report.model_hash)}</p></header>',
        "<main>",
        '<section aria-labelledby="scope"><h2 id="scope">Scope</h2>',
        f"<p>Exchange: <strong>{_html(report.scope.exchange)}</strong>; role: <strong>{_html(report.scope.research_role)}</strong>; data cutoff: <strong>{_html(report.scope.data_cutoff)}</strong>.</p>",
        f"<p>Overall confidence: <strong>{_html(report.overall_confidence)}</strong>.</p></section>",
        '<section aria-labelledby="lenses"><h2 id="lenses">Lens results</h2>',
        '<table><thead><tr><th scope="col">Lens</th><th scope="col">Total</th><th scope="col">Rating</th><th scope="col">Vetoed</th></tr></thead><tbody>',
    ]
    lines.extend(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _html(lens.lens),
            _html(lens.total if lens.total is not None else "NR"),
            _html(lens.rating),
            "yes" if lens.vetoed else "no",
        )
        for lens in report.lenses
    )
    lines.extend(
        [
            "</tbody></table></section>",
            '<section aria-labelledby="factors"><h2 id="factors">Factor proposals</h2>',
            '<table><thead><tr><th scope="col">Factor</th><th scope="col">Score</th><th scope="col">Confidence</th><th scope="col">Rationale</th></tr></thead><tbody>',
        ]
    )
    lines.extend(
        f"<tr><td>{_html(factor.factor)}</td><td>{_html(factor.proposed_score)}</td><td>{_html(factor.confidence)}</td><td>{_html(factor.rationale)}</td></tr>"
        for factor in report.factors
    )
    lines.extend(
        [
            "</tbody></table></section>",
            '<section aria-labelledby="evidence"><h2 id="evidence">Evidence</h2><ol>',
        ]
    )
    lines.extend(
        f'<li id="{_html(item.id)}"><strong>{_html(item.id)}</strong>: {_html(item.source_name)} ({_html(item.published_date)}, grade {_html(item.grade)}){f" — {_html(item.excerpt)}" if item.excerpt else ""}</li>'
        for item in report.evidence
    )
    lines.extend(["</ol></section>"])
    if report.review_issues:
        lines.append(
            '<section aria-labelledby="issues"><h2 id="issues">Review issues</h2><ul>'
        )
        lines.extend(
            f"<li><strong>{_html(issue.category)}</strong> ({'blocking' if issue.blocking else 'non-blocking'}): {_html(issue.rationale)}</li>"
            for issue in report.review_issues
        )
        lines.append("</ul></section>")
    lines.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(lines)
