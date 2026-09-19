# packages/storage/tests/test_models.py
from datetime import UTC, date, datetime

from fathomark_storage import create_session_factory, init_db
from fathomark_storage.models import ResearchRunRow


def test_run_row_roundtrip():
    sf = create_session_factory("sqlite:///:memory:")
    init_db(sf)
    with sf() as s:
        s.add(
            ResearchRunRow(
                id="run_1",
                idempotency_key="k1",
                symbol="ADBE",
                exchange="NASDAQ",
                research_role="core",
                horizon="3y",
                research_date=date(2026, 9, 3),
                data_cutoff=date(2026, 9, 3),
                framework_ref="common-stock@1.0.0",
                state="created",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()
        row = s.get(ResearchRunRow, "run_1")
        assert row.symbol == "ADBE" and row.state == "created" and row.lock_version == 0
