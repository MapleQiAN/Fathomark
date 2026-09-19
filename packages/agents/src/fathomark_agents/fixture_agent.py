"""Fixture replay stub for specialist agents not yet implemented (slice M3.1).

The pipeline needs proposals for all 11 framework factors to reach draft.
Scope and Financial agents are real; the other 9 factors are replayed from a
recorded fixture here and persisted with origin="fixture" so draft consumers
can distinguish them from genuine agent output. Remove factors from this stub
as real agents land.
"""

import json
from pathlib import Path

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)


class FixtureReplayAgent:
    name = "fixture-replay-agent"
    version = "1.0.0"

    def __init__(self, stub_path: Path, factors: tuple[str, ...]):
        self._stub_path = Path(stub_path)
        self._factors = set(factors)

    def run(
        self,
        *,
        scope: ScopeSnapshot,
        framework: Framework,
        evidence: list[EvidenceItem],
    ) -> list[FactorProposal]:
        raw = json.loads(self._stub_path.read_text(encoding="utf-8"))
        evidence_index = {e.id: e.published_date for e in evidence}
        proposals = []
        for p in raw["proposals"]:
            proposal = FactorProposal.model_validate(p)
            if proposal.factor not in self._factors:
                continue
            validate_proposal(
                proposal,
                framework=framework,
                evidence=evidence_index,
                data_cutoff=scope.data_cutoff,
            )
            proposals.append(proposal)
        missing = self._factors - {p.factor for p in proposals}
        if missing:
            raise ValueError(f"stub missing proposals for {sorted(missing)}")
        return proposals
