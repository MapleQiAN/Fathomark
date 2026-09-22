"""Report models and renderers for Fathomark."""

from fathomark_reporting.charts import (
    render_factor_chart,
    render_score_change,
    render_valuation_sensitivity,
)
from fathomark_reporting.manifest import (
    ArtifactManifest,
    ArtifactManifestEntry,
    build_artifact_manifest,
)
from fathomark_reporting.model import (
    ReportEvidence,
    ReportFactor,
    ReportIssue,
    ReportLens,
    ReportModel,
)
from fathomark_reporting.pdf_checks import PDFStructureReport, verify_pdf_structure
from fathomark_reporting.renderers import (
    HTMLTheme,
    render_html,
    render_json,
    render_markdown,
    render_pdf,
    render_report_bundle,
)

__all__ = [
    "ArtifactManifest",
    "ArtifactManifestEntry",
    "HTMLTheme",
    "PDFStructureReport",
    "ReportEvidence",
    "ReportFactor",
    "ReportIssue",
    "ReportLens",
    "ReportModel",
    "build_artifact_manifest",
    "render_factor_chart",
    "render_html",
    "render_json",
    "render_markdown",
    "render_pdf",
    "render_report_bundle",
    "render_score_change",
    "render_valuation_sensitivity",
    "verify_pdf_structure",
]
