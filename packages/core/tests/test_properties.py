from datetime import UTC, date, datetime
from pathlib import Path

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from hypothesis import given, settings
from hypothesis import strategies as st

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")
DAY = date(2026, 9, 18)
SCOPE = ScopeSnapshot(
    symbol="T", exchange="NYSE", research_role="core", horizon="1y",
    research_date=DAY, data_cutoff=DAY, framework_ref="common-stock@1.0.0",
)

score_dicts = st.fixed_dictionaries(
    {f.id: st.floats(min_value=0, max_value=10).map(lambda x: round(x * 2) / 2)
     for f in FRAMEWORK.raw_factors}
)


def _run(scores):
    evidence = [
        EvidenceItem(
            id=f"ev_{i:03d}", source_name="fixture", source_class="filings",
            url=None, published_date=DAY, data_period_end=None,
            accessed_at=datetime(2026, 9, 18, tzinfo=UTC), grade="A", content_hash=str(i),
        )
        for i in range(1, 12)
    ]
    proposals = [
        FactorProposal(
            factor=f, proposed_score=s, rationale="r", evidence_ids=[f"ev_{i:03d}"],
            counter_evidence_ids=[], confidence="high", missing_data=[], as_of_date=DAY,
        )
        for i, (f, s) in enumerate(scores.items(), start=1)
    ]
    return evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=evidence, proposals=proposals)


@given(scores=score_dicts)
@settings(max_examples=200, deadline=None)
def test_determinism(scores):
    assert _run(scores) == _run(scores)


@given(scores=score_dicts)
@settings(max_examples=200, deadline=None)
def test_totals_in_range_and_rating_consistent(scores):
    snap = _run(scores)
    for result in snap.lens_results.values():
        if result.total is not None:
            assert 0.0 <= result.total <= 100.0
        assert result.rating in {"S", "A+", "A", "B+", "B", "B-", "C", "D", "X", "NR"}
