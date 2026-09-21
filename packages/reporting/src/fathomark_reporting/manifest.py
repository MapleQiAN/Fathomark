"""Deterministic content manifest for report artifacts."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel

from fathomark_reporting.model import ReportModel

_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".pdf": "application/pdf",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}


class ArtifactManifestEntry(BaseModel):
    model_config = {"frozen": True}

    name: str
    media_type: str
    size_bytes: int
    content_hash: str


class ArtifactManifest(BaseModel):
    """Immutable identity and content hashes for one report export set."""

    model_config = {"frozen": True}

    schema_version: Literal["1"] = "1"
    status: Literal["draft", "approved"]
    framework_ref: str
    snapshot_hash: str
    report_model_hash: str
    template_version: str
    artifacts: tuple[ArtifactManifestEntry, ...]
    manifest_hash: str

    @staticmethod
    def _canonical_payload(manifest: "ArtifactManifest") -> str:
        return json.dumps(
            manifest.model_dump(mode="json", exclude={"manifest_hash"}),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def verify_integrity(self) -> None:
        digest = (
            "sha256:"
            + hashlib.sha256(self._canonical_payload(self).encode("utf-8")).hexdigest()
        )
        if digest != self.manifest_hash:
            raise ValueError(
                f"manifest hash mismatch: expected {self.manifest_hash}, computed {digest}"
            )

    def to_json(self) -> str:
        self.verify_integrity()
        return (
            json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def _artifact_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"invalid artifact name: {name!r}")
    return name


def _artifact_bytes(content: str | bytes) -> bytes:
    if isinstance(content, str):
        return content.encode("utf-8")
    if isinstance(content, bytes):
        return content
    raise TypeError("artifact content must be str or bytes")


def _media_type(name: str) -> str:
    for suffix, media_type in _MEDIA_TYPES.items():
        if name.endswith(suffix):
            return media_type
    return "application/octet-stream"


def build_artifact_manifest(
    report: ReportModel,
    artifacts: dict[str, str | bytes],
    *,
    template_version: str = "1",
) -> ArtifactManifest:
    """Build a content-addressed manifest without touching the filesystem."""
    report.verify_integrity()
    if not template_version.strip():
        raise ValueError("template_version must not be empty")
    entries = []
    for name, content in sorted(artifacts.items()):
        safe_name = _artifact_name(name)
        payload = _artifact_bytes(content)
        entries.append(
            ArtifactManifestEntry(
                name=safe_name,
                media_type=_media_type(safe_name),
                size_bytes=len(payload),
                content_hash="sha256:" + hashlib.sha256(payload).hexdigest(),
            )
        )
    manifest = ArtifactManifest(
        status=report.status,
        framework_ref=report.scope.framework_ref,
        snapshot_hash=report.snapshot_hash,
        report_model_hash=report.model_hash,
        template_version=template_version,
        artifacts=tuple(entries),
        manifest_hash="",
    )
    digest = (
        "sha256:"
        + hashlib.sha256(
            ArtifactManifest._canonical_payload(manifest).encode("utf-8")
        ).hexdigest()
    )
    return manifest.model_copy(update={"manifest_hash": digest})
