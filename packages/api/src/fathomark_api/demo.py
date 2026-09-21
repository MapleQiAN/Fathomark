"""Opt-in offline fixture orchestration for the self-contained demo image."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from fathomark_agents import Orchestrator
from fathomark_core import load_framework
from fathomark_providers import FixtureEvidenceProvider, ReplayLLMProvider
from fathomark_storage.repository import RunRepository

OrchestratorFactory = Callable[[RunRepository], Orchestrator]


def fixture_orchestrator_factory(
    fixture_dir: Path, framework_dir: Path
) -> OrchestratorFactory:
    """Build a fresh replay orchestrator for each API execute request.

    The fixture is deliberately opt-in.  Production deployments leave
    ``FATHOMARK_DEMO_FIXTURE_DIR`` unset and therefore have no hidden provider
    or credential behavior.
    """
    fixture_dir = Path(fixture_dir).expanduser()
    framework = load_framework(Path(framework_dir) / "common-stock.yaml")
    llm = ReplayLLMProvider(fixture_dir / "llm_cassette.json")
    evidence = FixtureEvidenceProvider(fixture_dir / "provider_dump.json")

    def factory(repo: RunRepository) -> Orchestrator:
        return Orchestrator(
            repo,
            framework,
            llm=llm,
            evidence_providers=[evidence],
        )

    return factory


def env_orchestrator_factory(framework_dir: Path) -> OrchestratorFactory | None:
    """Return the fixture factory only when the explicit demo env is set."""
    fixture_dir = os.getenv("FATHOMARK_DEMO_FIXTURE_DIR")
    if not fixture_dir:
        return None
    return fixture_orchestrator_factory(Path(fixture_dir), framework_dir)
