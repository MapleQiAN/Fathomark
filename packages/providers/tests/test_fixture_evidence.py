from datetime import date
from pathlib import Path

from fathomark_core.schemas import ScopeSnapshot
from fathomark_providers import FixtureEvidenceProvider

ROOT = Path(__file__).parents[3]

SCOPE = ScopeSnapshot(
    symbol="ADBE",
    exchange="NASDAQ",
    research_role="core",
    horizon="5-10y",
    research_date=date(2026, 9, 3),
    data_cutoff=date(2026, 9, 3),
    framework_ref="common-stock@1.0.0",
)


def test_fixture_provider_returns_typed_evidence():
    provider = FixtureEvidenceProvider(
        ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "provider_dump.json"
    )
    items = provider.fetch(SCOPE)
    assert {e.id for e in items} == {"ev_001", "ev_002"}
    assert all(e.excerpt for e in items)  # dump carries excerpts unlike input.json
    assert provider.name == "fixture-edgar"
