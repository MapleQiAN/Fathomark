"""Data-provider protocol and fixture-backed evidence provider."""

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from fathomark_core.schemas import EvidenceItem, ScopeSnapshot


@runtime_checkable
class EvidenceProvider(Protocol):
    name: str
    version: str

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]: ...


class FixtureEvidenceProvider:
    """Reads recorded evidence from a JSON dump. Offline; for CI and demos."""

    def __init__(
        self, dump_path: Path, *, name: str = "fixture-edgar", version: str = "1.0.0"
    ):
        self.name = name
        self.version = version
        self._dump_path = Path(dump_path)

    def fetch(self, scope: ScopeSnapshot) -> list[EvidenceItem]:
        raw = json.loads(self._dump_path.read_text(encoding="utf-8"))
        return [EvidenceItem.model_validate(e) for e in raw["evidence"]]
