"""Agent contracts, repair loop, and agent implementations."""

from fathomark_agents.contracts import AgentError
from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.fixture_agent import FixtureReplayAgent
from fathomark_agents.orchestrator import (
    Orchestrator,
    OrchestratorError,
    StepSpec,
    build_default_steps,
)
from fathomark_agents.repair import complete_with_repairs
from fathomark_agents.scope_agent import ScopeAgent

__all__ = [
    "AgentError",
    "FinancialAgent",
    "FixtureReplayAgent",
    "Orchestrator",
    "OrchestratorError",
    "ScopeAgent",
    "StepSpec",
    "build_default_steps",
    "complete_with_repairs",
]
