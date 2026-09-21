"""Evidence-only Red-Team audit agent (design section 5.8)."""

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

_INSTRUCTIONS = """You are the Red-Team auditor for an equity research pipeline.
Audit the supplied specialist proposals and report objections only. You must not
propose, revise, average, or vote on factor scores. Return JSON {\"issues\": [...]}.
Each issue category must be one of: unsupported_claim, evidence_conflict,
date_or_currency_conflict, duplicate_counting, valuation_cherry_picking,
missing_counter_evidence, veto_candidate, data_gap. Cite only supplied evidence
ids and never cite evidence published after the data cutoff. Set blocking=true
only when a human must review the run before a draft can be produced.

INPUT:
"""


def _prompt(
    scope: ScopeSnapshot,
    evidence: list[EvidenceItem],
    observations: list[MetricObservation],
    proposals: list[FactorProposal],
) -> str:
    payload = {
        "scope": json.loads(scope.model_dump_json()),
        "evidence": [
            {
                "id": item.id,
                "source_name": item.source_name,
                "published_date": item.published_date.isoformat(),
                "data_period_end": item.data_period_end.isoformat()
                if item.data_period_end
                else None,
                "grade": item.grade,
                "excerpt": item.excerpt,
            }
            for item in sorted(evidence, key=lambda item: item.id)
        ],
        "observations": [
            json.loads(item.model_dump_json())
            for item in sorted(
                observations,
                key=lambda item: (
                    item.metric,
                    item.data_date,
                    item.evidence_id,
                ),
            )
        ],
        "proposals": [
            json.loads(item.model_dump_json())
            for item in sorted(proposals, key=lambda item: item.factor)
        ],
    }
    return _INSTRUCTIONS + json.dumps(payload, sort_keys=True, ensure_ascii=False)


class RedTeamAgent:
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
        observations: list[MetricObservation],
        proposals: list[FactorProposal],
    ) -> list[ReviewIssue]:
        evidence_index = {item.id: item.published_date for item in evidence}

        def parse_validate(text: str) -> list[ReviewIssue]:
            try:
                issue_dicts = json.loads(text)["issues"]
                if not isinstance(issue_dicts, list):
                    raise TypeError("issues must be a JSON array")
                issues = [ReviewIssue.model_validate(item) for item in issue_dicts]
            except (KeyError, TypeError) as exc:
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
            _prompt(scope, evidence, observations, proposals),
            "review_issues",
            parse_validate,
            self.max_repairs,
        )
