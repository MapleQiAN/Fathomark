import hashlib
import json
from pathlib import Path

import pytest
from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from fathomark_reporting import ReportModel
from fathomark_reporting.renderers import (
    render_html,
    render_json,
    render_markdown,
    render_pdf,
    render_report_bundle,
)

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


def test_report_formats_match_golden_hashes_and_cross_format_identity():
    report = _report()
    outputs = {
        "json": render_json(report),
        "markdown": render_markdown(report),
        "html": render_html(report, theme="print"),
    }

    expected_hashes = {
        "json": "sha256:4b6b4efd8656cd1bf8ae873de8bec499aa92fdf652a6e3fea0bb3c52218f8f51",
        "markdown": "sha256:c218c2631a147f2532fd553764a923e1145d8b88e55d849086c9f293059a550a",
        "html": "sha256:b3537a4cd12d700778640321cef7c8f9c5329b1d56aa5b094bf6ef1dc2967221",
    }
    assert {
        name: "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
        for name, value in outputs.items()
    } == expected_hashes
    for evidence in report.evidence:
        assert all(evidence.id in value for value in outputs.values())
    assert all(report.model_hash in value for value in outputs.values())
    assert all(report.snapshot_hash in value for value in outputs.values())


def test_markdown_and_html_renderers_meet_basic_format_and_accessibility_contract():
    report = _report()
    markdown = render_markdown(report)
    html = render_html(report, theme="print")

    assert all(not line.endswith(" ") for line in markdown.splitlines())
    assert markdown.count("\n# ") == 1
    assert 'lang="en"' in html
    assert '<meta name="viewport"' in html
    assert html.count('<th scope="col">') >= 7
    assert "<link href=" not in html
    assert "<script src=" not in html


def test_pdf_renderer_uses_print_html_and_injected_chromium_launcher():
    report = _report()
    captured = {}

    def launcher(html, executable_path):
        captured["html"] = html
        captured["executable_path"] = executable_path
        return b"%PDF-recorded"

    pdf = render_pdf(report, chromium_path="/opt/chromium", launcher=launcher)

    assert pdf == b"%PDF-recorded"
    assert 'data-theme="print"' in captured["html"]
    assert captured["executable_path"] == "/opt/chromium"


def test_report_bundle_uses_one_report_model_for_all_formats():
    report = _report()
    captured = {}

    def launcher(html, executable_path):
        captured["html"] = html
        return b"%PDF-1.7 recorded"

    bundle = render_report_bundle(report, launcher=launcher)

    assert set(bundle) == {"report.json", "report.md", "report.html", "report.pdf"}
    assert json.loads(bundle["report.json"])["model_hash"] == report.model_hash
    for item in report.evidence:
        assert item.id in bundle["report.md"]
        assert item.id in bundle["report.html"]
        assert item.id in captured["html"]
    for rendered in (
        bundle["report.json"],
        bundle["report.md"],
        bundle["report.html"],
        captured["html"],
    ):
        assert report.snapshot_hash in rendered
        assert report.model_hash in rendered
    assert bundle["report.pdf"].startswith(b"%PDF-")


def test_html_renderer_has_responsive_table_boundary():
    html = render_html(_report(), theme="light")

    assert "overflow-x:auto" in html
    assert "overflow-wrap:anywhere" in html
    assert "@media(max-width:720px)" in html
    assert html.count('<div class="table-wrap">') == 2
    assert "cell.setAttribute('data-label'" in html


def test_html_renderer_exposes_grouped_reader_and_quick_mode_contract():
    html = render_html(_report(), theme="light")

    for group in ("结论", "公司", "估值", "风险与监控"):
        assert f'data-toc-group="{group}"' in html
    assert 'data-reading-mode="quick"' in html
    assert 'data-reading-mode="full"' in html
    assert 'data-quick="true"' in html
    assert 'data-quick="false"' in html
    assert 'id="executive-overview"' in html
    assert 'href="#lens-results"' in html
    assert 'href="#valuation-analysis"' in html
    assert 'href="#risk-monitoring"' in html


def test_html_renderer_exposes_toolbar_search_resume_and_mobile_contracts():
    html = render_html(_report(), theme="auto")

    assert 'data-action="search"' in html
    assert 'data-action="theme"' in html
    assert 'data-action="more"' in html
    assert 'data-action="print"' in html
    assert 'data-action="top"' in html
    assert 'id="search-dialog"' in html
    assert 'id="current-section"' in html
    assert 'id="reading-progress"' in html
    assert 'id="mobile-prev"' in html
    assert 'id="mobile-catalog"' in html
    assert 'id="mobile-next"' in html
    assert 'data-report-date="2026-09-03"' in html
    assert "event.metaKey || event.ctrlKey" in html
    assert "event.key === 'Escape'" in html
    assert "localStorage" in html
    assert "data-label" in html
