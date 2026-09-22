"""Deterministic report renderers with one validated input model."""

import json
from collections.abc import Callable
from typing import Literal
from urllib.parse import urlsplit

from fathomark_reporting.model import ReportModel
from fathomark_reporting.premium_html import render_premium_html

HTMLTheme = Literal["auto", "light", "dark", "print"]
ReportArtifact = str | bytes


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


def render_html(report: ReportModel, *, theme: HTMLTheme = "auto") -> str:
    """Render a self-contained HTML report with escaped untrusted content."""
    _assert_report(report)
    return render_premium_html(report, theme=theme)


def _playwright_pdf(html: str, executable_path: str | None) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF export requires the optional 'playwright' package and a Chromium binary"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable_path)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            return page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()


def render_pdf(
    report: ReportModel,
    *,
    chromium_path: str | None = None,
    launcher: Callable[[str, str | None], bytes] | None = None,
) -> bytes:
    """Render the print-theme HTML through Playwright/Chromium.

    ``launcher`` is a narrow seam for deterministic tests or a deployment's
    browser wrapper. Without it, the optional Playwright dependency is loaded
    lazily so JSON/Markdown/HTML users do not need a browser installed.
    """
    _assert_report(report)
    html = render_html(report, theme="print")
    pdf = (launcher or _playwright_pdf)(html, chromium_path)
    if not isinstance(pdf, bytes):
        raise TypeError("PDF launcher must return bytes")
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("PDF launcher returned bytes without a PDF header")
    return pdf


def render_report_bundle(
    report: ReportModel,
    *,
    html_theme: HTMLTheme = "light",
    chromium_path: str | None = None,
    launcher: Callable[[str, str | None], bytes] | None = None,
) -> dict[str, ReportArtifact]:
    """Render all report formats from the same validated report model.

    The PDF is intentionally the only browser-backed artifact.  Callers can
    inject a launcher in tests or supply the deployment's Chromium path while
    JSON, Markdown and HTML remain usable without the optional browser extra.
    """
    _assert_report(report)
    return {
        "report.json": render_json(report),
        "report.md": render_markdown(report),
        "report.html": render_html(report, theme=html_theme),
        "report.pdf": render_pdf(
            report,
            chromium_path=chromium_path,
            launcher=launcher,
        ),
    }
