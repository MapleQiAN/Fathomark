"""Deterministic report renderers with one validated input model."""

import json

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
