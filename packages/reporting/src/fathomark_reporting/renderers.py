"""Deterministic report renderers with one validated input model."""

import json
from html import escape
from typing import Literal
from urllib.parse import urlsplit

from fathomark_reporting.model import ReportModel

HTMLTheme = Literal["auto", "light", "dark", "print"]


def _assert_report(report: ReportModel) -> None:
    report.verify_integrity()


def render_json(report: ReportModel) -> str:
    """Return canonical, machine-readable JSON for a report model."""
    _assert_report(report)
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


def _markdown_text(value: object) -> str:
    """Escape untrusted text while keeping the report readable as GFM."""
    text = str(value).replace("\r\n", " ").replace("\n", " ")
    for token in ("\\", "`", "*", "_", "~", "#", "[", "]", "<", ">", "|"):
        text = text.replace(token, "\\" + token)
    return text


def _cell(value: object) -> str:
    return _markdown_text(value)


def _markdown_id(value: object) -> str:
    """Keep stable evidence IDs recognizable while blocking footnote syntax."""
    return str(value).replace("\\", "\\\\").replace("]", "\\]")


def _markdown_refs(ids: tuple[str, ...]) -> str:
    return ", ".join(f"[^{_markdown_id(item)}]" for item in ids) or "—"


def _valid_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def render_markdown(report: ReportModel) -> str:
    """Render portable GFM with YAML metadata and evidence footnotes."""
    _assert_report(report)
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
        f"# {_markdown_text(report.scope.symbol)} Research Report",
        "",
        f"> **{status_label}**",
        "",
        "## Scope",
        "",
        f"- Exchange: `{_markdown_text(report.scope.exchange)}`",
        f"- Research role: `{_markdown_text(report.scope.research_role)}`",
        f"- Horizon: `{_markdown_text(report.scope.horizon)}`",
        f"- Research date: `{report.scope.research_date.isoformat()}`",
        f"- Data cutoff: `{report.scope.data_cutoff.isoformat()}`",
        f"- Framework: `{_markdown_text(report.scope.framework_ref)}`",
        f"- Snapshot hash: `{_markdown_text(report.snapshot_hash)}`",
        f"- Overall confidence: **{_markdown_text(report.overall_confidence)}**",
        "",
        "## Lens results",
        "",
        "| Lens | Total | Rating | Tactical state | Flagged | Vetoed | Veto reasons |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        "| {lens} | {total} | {rating} | {tactical} | {flagged} | {vetoed} | {reasons} |".format(
            lens=_cell(lens.lens),
            total=_cell(lens.total if lens.total is not None else "NR"),
            rating=_cell(lens.rating),
            tactical=_cell(lens.tactical_state or "—"),
            flagged="yes" if lens.flagged else "no",
            vetoed="yes" if lens.vetoed else "no",
            reasons=_cell("; ".join(lens.veto_reasons) or "—"),
        )
        for lens in report.lenses
    )
    lines.extend(
        [
            "",
            "## Factor proposals",
            "",
            "| Factor | Score | Confidence | Supporting evidence | Counter evidence | Missing data |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    lines.extend(
        "| {factor} | {score} | {confidence} | {evidence} | {counter} | {missing} |".format(
            factor=_cell(factor.factor),
            score=_cell(factor.proposed_score),
            confidence=_cell(factor.confidence),
            evidence=_markdown_refs(factor.evidence_ids),
            counter=_markdown_refs(factor.counter_evidence_ids),
            missing=_cell("; ".join(factor.missing_data) or "—"),
        )
        for factor in report.factors
    )
    lines.extend(["", "### Rationale", ""])
    for factor in report.factors:
        lines.append(
            f"- **{_markdown_text(factor.factor)}:** {_markdown_text(factor.rationale)}"
        )

    lines.extend(["", "## Evidence", ""])
    for item in report.evidence:
        excerpt = f" — {_markdown_text(item.excerpt)}" if item.excerpt else ""
        source_url = (
            f" Source URL: `{_markdown_text(item.url)}`" if _valid_url(item.url) else ""
        )
        lines.append(
            f"[^{_markdown_id(item.id)}]: {_markdown_text(item.source_name)} "
            f"({item.published_date.isoformat()}, grade {_markdown_text(item.grade)})"
            f"{source_url}{excerpt}"
        )

    if report.review_issues:
        lines.extend(["", "## Review issues", ""])
        for issue in report.review_issues:
            blocking = "blocking" if issue.blocking else "non-blocking"
            refs = _markdown_refs(issue.evidence_ids)
            lines.append(
                f"- **{_markdown_text(issue.category)} ({blocking})** — "
                f"{_markdown_text(issue.rationale)} ({refs})"
            )
    return "\n".join(lines) + "\n"


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def _html_refs(ids: tuple[str, ...]) -> str:
    return (
        ", ".join(f'<a href="#{_html(item)}">{_html(item)}</a>' for item in ids) or "—"
    )


def _html_url(url: str | None) -> str:
    if not url:
        return ""
    if not _valid_url(url):
        return f"<span>{_html(url)}</span>"
    safe_url = _html(url)
    return f'<a href="{safe_url}" rel="noreferrer">Source URL</a>'


def _html_theme_css(theme: HTMLTheme) -> list[str]:
    palettes = {
        "light": ("#fff", "#17212b", "#e8eef2"),
        "dark": ("#17212b", "#f4f7f9", "#33414d"),
        "print": ("#fff", "#000", "#fff"),
        "auto": ("#fff", "#17212b", "#e8eef2"),
    }
    try:
        background, foreground, table_header = palettes[theme]
    except KeyError as exc:
        raise ValueError(f"unknown HTML theme: {theme}") from exc
    lines = [
        f":root{{color-scheme:{'light dark' if theme == 'auto' else theme};font-family:system-ui,sans-serif;line-height:1.5;--report-background:{background};--report-foreground:{foreground};--report-table-header:{table_header}}}",
        "body{max-width:1100px;margin:0 auto;padding:2rem;background:var(--report-background);color:var(--report-foreground)}",
        "table{border-collapse:collapse;width:100%;margin:1rem 0 2rem}",
        "th,td{border:1px solid #b8c4cc;padding:.5rem;text-align:left;vertical-align:top}",
        "th{background:var(--report-table-header)}",
        ".status{border:2px solid #b7791f;padding:.75rem;font-weight:700}",
        ".hash{font-family:ui-monospace,monospace;overflow-wrap:anywhere}",
    ]
    if theme == "auto":
        lines.append(
            "@media(prefers-color-scheme:dark){:root{--report-background:#17212b;--report-foreground:#f4f7f9;--report-table-header:#33414d}}"
        )
    lines.append(
        "@media print{body{max-width:none;padding:0;color:#000;background:#fff}.status{break-inside:avoid}table{break-inside:auto}tr{break-inside:avoid;break-after:auto}}"
    )
    return lines


def render_html(report: ReportModel, *, theme: HTMLTheme = "auto") -> str:
    """Render a self-contained HTML report with escaped untrusted content."""
    _assert_report(report)
    status_label = "DRAFT — NOT APPROVED" if report.status == "draft" else "APPROVED"
    theme_css = _html_theme_css(theme)
    lines = [
        "<!doctype html>",
        f'<html lang="en" data-theme="{_html(theme)}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_html(report.scope.symbol)} Research Report</title>",
        "<style>",
        *theme_css,
        "</style>",
        "</head>",
        "<body>",
        f"<header><h1>{_html(report.scope.symbol)} Research Report</h1>",
        f'<p class="status">{_html(status_label)}</p>',
        f'<p class="hash">Report model: {_html(report.model_hash)}</p>',
        f'<p class="hash">Snapshot: {_html(report.snapshot_hash)}</p>',
        f"<p>Framework: <strong>{_html(report.scope.framework_ref)}</strong></p></header>",
        "<main>",
        '<section aria-labelledby="scope"><h2 id="scope">Scope</h2>',
        f"<p>Exchange: <strong>{_html(report.scope.exchange)}</strong>; role: <strong>{_html(report.scope.research_role)}</strong>; horizon: <strong>{_html(report.scope.horizon)}</strong>; research date: <strong>{_html(report.scope.research_date)}</strong>; data cutoff: <strong>{_html(report.scope.data_cutoff)}</strong>.</p>",
        f"<p>Overall confidence: <strong>{_html(report.overall_confidence)}</strong>.</p></section>",
        '<section aria-labelledby="lenses"><h2 id="lenses">Lens results</h2>',
        '<table><thead><tr><th scope="col">Lens</th><th scope="col">Total</th><th scope="col">Rating</th><th scope="col">Tactical state</th><th scope="col">Flagged</th><th scope="col">Vetoed</th><th scope="col">Veto reasons</th></tr></thead><tbody>',
    ]
    lines.extend(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _html(lens.lens),
            _html(lens.total if lens.total is not None else "NR"),
            _html(lens.rating),
            _html(lens.tactical_state or "—"),
            "yes" if lens.flagged else "no",
            "yes" if lens.vetoed else "no",
            _html("; ".join(lens.veto_reasons) or "—"),
        )
        for lens in report.lenses
    )
    lines.extend(
        [
            "</tbody></table></section>",
            '<section aria-labelledby="factors"><h2 id="factors">Factor proposals</h2>',
            '<table><thead><tr><th scope="col">Factor</th><th scope="col">Score</th><th scope="col">Confidence</th><th scope="col">Supporting evidence</th><th scope="col">Counter evidence</th><th scope="col">Missing data</th><th scope="col">Rationale</th></tr></thead><tbody>',
        ]
    )
    lines.extend(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _html(factor.factor),
            _html(factor.proposed_score),
            _html(factor.confidence),
            _html_refs(factor.evidence_ids),
            _html_refs(factor.counter_evidence_ids),
            _html("; ".join(factor.missing_data) or "—"),
            _html(factor.rationale),
        )
        for factor in report.factors
    )
    lines.extend(
        [
            "</tbody></table></section>",
            '<section aria-labelledby="evidence"><h2 id="evidence">Evidence</h2><ol>',
        ]
    )
    lines.extend(
        f'<li id="{_html(item.id)}"><strong>{_html(item.id)}</strong>: {_html(item.source_name)} ({_html(item.published_date)}, grade {_html(item.grade)})'
        f"{f' — {_html(item.excerpt)}' if item.excerpt else ''}"
        f"{f' — {_html_url(item.url)}' if item.url else ''}</li>"
        for item in report.evidence
    )
    lines.extend(["</ol></section>"])
    if report.review_issues:
        lines.append(
            '<section aria-labelledby="issues"><h2 id="issues">Review issues</h2><ul>'
        )
        lines.extend(
            f"<li><strong>{_html(issue.category)}</strong> ({'blocking' if issue.blocking else 'non-blocking'}): {_html(issue.rationale)} ({_html_refs(issue.evidence_ids)})</li>"
            for issue in report.review_issues
        )
        lines.append("</ul></section>")
    lines.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(lines)
