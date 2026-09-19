"""Scope Agent: freezes the research contract (design §5.1). Deterministic."""

from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage.repository import RunRepository


class ScopeAgent:
    name = "scope-agent"
    version = "1.0.0"

    def run(self, repo: RunRepository, run_id: str) -> ScopeSnapshot:
        return repo.scope_of(run_id)
