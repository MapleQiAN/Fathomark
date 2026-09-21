"""Red-Team audit agent for evidence-linked review issues (design §5.8)."""

import json

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ReviewIssue,
    ScopeSnapshot,
    validate_review_issue,
)
from fathomark_providers import LLMProvider

from fathomark_agents.repair import complete_with_repairs

REVIEW_ISSUE_CATEGORIES = (
    "unsupported_claim",
    "evidence_conflict",
    "date_or_currency_conflict",
    "duplicate_counting",
    "valuation_cherry_picking",
    "missing_counter_evidence",
    "veto_candidate",
    "data_gap",
)

_INSTRUCTIONS = """You are the Red-Team Agent for an equity research pipeline.
Audit only the supplied scope, evidence, observations, and specialist proposals.
Return JSON {"issues": [...]} only. You cannot propose scores, replace scores,
or average scores. Report only typed objections in these categories:
unsupported_claim, evidence_conflict, date_or_currency_conflict,
duplicate_counting, valuation_cherry_picking, missing_counter_evidence,
veto_candidate, data_gap.
Each issue: category, optional factor, evidence_ids, rationale, blocking,
as_of_date. Only cite evidence ids listed below and never cite evidence
published after the data cutoff.

INPUT:
"""


class RedTeamAgent:
    """Audit specialist outputs without changing deterministic score arithmetic."""

    name = "red-team-agent"
    version = "1.0.0"

    def __init__(self, llm: LLMProvider, max_repairs: int = 2):
        self.llm = llm
        self.max_repairs = max_repairs

    def run(
        self,
        *,
        scope: ScopeSnapshot,
        framework: Framework,
        evidence: list[EvidenceItem],
        observations: list[MetricObservation] | None = None,
        proposals: list[FactorProposal] | None = None,
    ) -> list[ReviewIssue]:
        evidence_index = {item.id: item.published_date for item in evidence}
        payload = {
            "scope": scope.model_dump(mode="json"),
            "evidence": [
                item.model_dump(mode="json")
                for item in sorted(evidence, key=lambda item: item.id)
            ],
            "observations": [
                item.model_dump(mode="json")
                for item in sorted(
                    observations or [], key=lambda item: item.evidence_id
                )
            ],
            "proposals": [
                item.model_dump(mode="json")
                for item in sorted(proposals or [], key=lambda item: item.factor)
            ],
        }
        prompt = _INSTRUCTIONS + json.dumps(payload, sort_keys=True, ensure_ascii=False)

        def parse_validate(text: str) -> list[ReviewIssue]:
            try:
                issue_dicts = json.loads(text)["issues"]
                if not isinstance(issue_dicts, list):
                    raise TypeError("issues must be a list")
                issues = [ReviewIssue.model_validate(item) for item in issue_dicts]
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"malformed review issues payload: {exc}") from exc
            for issue in issues:
                validate_review_issue(
                    issue,
                    framework=framework,
                    evidence=evidence_index,
                    data_cutoff=scope.data_cutoff,
                )
            return issues

        return complete_with_repairs(
            self.llm,
            prompt,
            "review_issues",
            parse_validate,
            self.max_repairs,
        )
