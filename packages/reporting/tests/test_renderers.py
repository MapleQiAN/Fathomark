import json
from pathlib import Path

import pytest
from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from fathomark_reporting import ReportModel
from fathomark_reporting.renderers import render_html, render_json, render_markdown

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def _report(*, proposals=None, snapshot=None):
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    scope = ScopeSnapshot.model_validate(data["scope"])
    evidence = [EvidenceItem.model_validate(item) for item in data["evidence"]]
    proposals = proposals or [
        FactorProposal.model_validate(item) for item in data["proposals"]
    ]
    snapshot = snapshot or evaluate(
        framework=load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        scope=scope,
        evidence=evidence,
        proposals=proposals,
    )
    return ReportModel.from_snapshot(
        snapshot=snapshot,
        evidence=evidence,
        proposals=proposals,
        review_issues=[],
        status="draft",
    )


def test_json_renderer_preserves_model_hash():
    report = _report()

    rendered = render_json(report)

    assert json.loads(rendered)["model_hash"] == report.model_hash
    assert rendered == render_json(report)


def test_markdown_renderer_has_metadata_draft_marker_and_evidence():
    report = _report()

    rendered = render_markdown(report)

    assert rendered.startswith("---\n")
    assert 'status: "draft"' in rendered
    assert 'symbol: "ADBE"' in rendered
    assert 'framework_ref: "common-stock@1.0.0"' in rendered
    assert f'report_model_hash: "{report.model_hash}"' in rendered
    assert "DRAFT — NOT APPROVED" in rendered
    for item in report.evidence:
        assert item.id in rendered


def test_html_renderer_is_escaped_self_contained_and_accessible():
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    proposals = [FactorProposal.model_validate(item) for item in data["proposals"]]
    proposals[0] = proposals[0].model_copy(
        update={"rationale": "<script>alert('x')</script>"}
    )
    report = _report(proposals=proposals)

    rendered = render_html(report)

    assert "<title>ADBE Research Report</title>" in rendered
    assert '<th scope="col">Factor</th>' in rendered
    assert "DRAFT — NOT APPROVED" in rendered
    assert report.model_hash in rendered
    assert "<script>alert('x')</script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in rendered
    assert "<script src=" not in rendered
    assert '<link href="http' not in rendered


def test_html_themes_include_explicit_dark_and_print_contracts():
    report = _report()
    light = render_html(report, theme="light")
    assert 'data-theme="light"' in light
    assert "--report-background:#fff" in light

    dark = render_html(report, theme="dark")
    assert 'data-theme="dark"' in dark
    assert "--report-background:#17212b" in dark

    printable = render_html(report, theme="print")
    assert 'data-theme="print"' in printable
    assert "@media print" in printable

    with pytest.raises(ValueError, match="unknown HTML theme"):
        render_html(report, theme="sepia")


def test_renderers_show_risk_and_traceability_fields():
    report = _report()
    tactical = report.lenses[-1]
    # Lens results are copied from the snapshot; this makes the risk fields
    # non-empty so the test catches renderers that only expose empty columns.
    flagged = tactical.model_copy(
        update={"flagged": True, "vetoed": True, "veto_reasons": ("risk gate",)}
    )
    report = report.model_copy(
        update={"lenses": (*report.lenses[:-1], flagged)},
    )
    # Recompute the model hash because model_copy intentionally bypasses
    # validation, then exercise the renderer's integrity check.
    report = report.model_copy(update={"model_hash": ""})
    digest = (
        "sha256:"
        + __import__("hashlib")
        .sha256(report._canonical_payload(report).encode("utf-8"))
        .hexdigest()
    )
    report = report.model_copy(update={"model_hash": digest})

    markdown = render_markdown(report)
    html = render_html(report)

    for rendered in (markdown, html):
        assert "Tactical state" in rendered
        assert "Flagged" in rendered
        assert "Veto reasons" in rendered
        assert "Supporting evidence" in rendered
        assert "Counter evidence" in rendered
        assert "Missing data" in rendered
        assert report.snapshot_hash in rendered
        assert report.scope.framework_ref in rendered
        assert "risk gate" in rendered
        assert "Source URL" in rendered


def test_markdown_renderer_escapes_untrusted_text():
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    proposals = [FactorProposal.model_validate(item) for item in data["proposals"]]
    proposals[0] = proposals[0].model_copy(
        update={"rationale": "# heading <script>alert('x')</script>"}
    )
    rendered = render_markdown(_report(proposals=proposals))

    assert "<script>" not in rendered
    assert "\\# heading" in rendered
    assert "\\<script\\>" in rendered


def test_renderer_rejects_tampered_model_hash():
    report = _report().model_copy(update={"snapshot_hash": "sha256:tampered"})

    with pytest.raises(ValueError, match="model hash mismatch"):
        render_json(report)
