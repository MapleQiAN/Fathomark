import hashlib
import json

import pytest
from fathomark_reporting.manifest import build_artifact_manifest
from test_renderers import _report


def test_manifest_binds_report_identity_and_is_deterministic():
    report = _report()
    artifacts = {
        "report.html": "<html>报告</html>",
        "report.json": b'{"status":"draft"}\n',
    }

    first = build_artifact_manifest(
        report,
        artifacts,
        template_version="html-1",
    )
    second = build_artifact_manifest(
        report,
        dict(reversed(list(artifacts.items()))),
        template_version="html-1",
    )

    assert first == second
    assert first.report_model_hash == report.model_hash
    assert first.snapshot_hash == report.snapshot_hash
    assert first.framework_ref == report.scope.framework_ref
    assert [entry.name for entry in first.artifacts] == [
        "report.html",
        "report.json",
    ]
    assert first.artifacts[0].size_bytes == len("<html>报告</html>".encode())
    assert first.manifest_hash.startswith("sha256:")
    assert json.loads(first.to_json())["manifest_hash"] == first.manifest_hash


def test_manifest_hash_matches_artifact_bytes():
    report = _report()
    manifest = build_artifact_manifest(report, {"report.txt": "hello"})

    assert manifest.artifacts[0].content_hash == (
        "sha256:" + hashlib.sha256(b"hello").hexdigest()
    )
    assert manifest.artifacts[0].media_type == "text/plain; charset=utf-8"


@pytest.mark.parametrize("name", ["", "../report.html", "nested/report.html", "a\\b"])
def test_manifest_rejects_path_traversal_or_empty_names(name):
    with pytest.raises(ValueError, match="artifact name"):
        build_artifact_manifest(_report(), {name: b"content"})


def test_manifest_rejects_tampered_report_copy():
    report = _report().model_copy(update={"snapshot_hash": "sha256:tampered"})

    with pytest.raises(ValueError, match="model hash mismatch"):
        build_artifact_manifest(report, {"report.json": "{}"})
