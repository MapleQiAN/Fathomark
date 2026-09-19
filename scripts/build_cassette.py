"""Rebuild llm_cassette.json deterministically from the ADBE fixture.

Prompts are computed with the real build_prompt; responses are the golden
proposals from input.json grouped by specialist agent. No network, no LLM.
Re-run after changing agent instructions or the prompt builder, and commit
the result.
"""

import json
from pathlib import Path

from fathomark_agents.financial_agent import FinancialAgent
from fathomark_agents.specialist_agent import build_prompt
from fathomark_agents.specialists import (
    BusinessAgent,
    GovernanceRiskAgent,
    GrowthAgent,
    MarketAgent,
    ValuationAgent,
)
from fathomark_core.schemas import EvidenceItem, ScopeSnapshot
from fathomark_providers import prompt_key

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
AGENTS = (
    FinancialAgent,
    BusinessAgent,
    GrowthAgent,
    ValuationAgent,
    GovernanceRiskAgent,
    MarketAgent,
)


def main() -> None:
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    scope = ScopeSnapshot.model_validate(data["scope"])
    golden = data["proposals"]
    dump = json.loads((FIXTURE / "provider_dump.json").read_text(encoding="utf-8"))
    evidence = [EvidenceItem.model_validate(e) for e in dump["evidence"]]
    cassette = {}
    for agent_cls in AGENTS:
        proposals = [p for p in golden if p["factor"] in agent_cls.factors]
        if len(proposals) != len(agent_cls.factors):
            raise SystemExit(f"golden input missing factors for {agent_cls.name}")
        prompt = build_prompt(scope, evidence, agent_cls.instructions)
        cassette[prompt_key(prompt)] = json.dumps(
            {"proposals": proposals}, ensure_ascii=False
        )
    out = FIXTURE / "llm_cassette.json"
    out.write_text(
        json.dumps(cassette, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cassette)} cassette entries to {out}")


if __name__ == "__main__":
    main()
