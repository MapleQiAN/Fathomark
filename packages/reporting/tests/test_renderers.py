import json
from pathlib import Path

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from fathomark_reporting import ReportModel
from fathomark_reporting.renderers import render_json, render_markdown

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def _report():
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    scope = ScopeSnapshot.model_validate(data["scope"])
    evidence = [EvidenceItem.model_validate(item) for item in data["evidence"]]
    proposals = [FactorProposal.model_validate(item) for item in data["proposals"]]
    snapshot = evaluate(
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
