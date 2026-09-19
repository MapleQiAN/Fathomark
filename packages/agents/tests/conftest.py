from datetime import date

import pytest
from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage.database import create_session_factory, init_db
from fathomark_storage.repository import RunRepository


@pytest.fixture
def seeded_run(tmp_path):
    factory = create_session_factory(f"sqlite:///{tmp_path}/t.db")
    init_db(factory)
    repo = RunRepository(factory())
    scope = ScopeSnapshot(
        symbol="ADBE",
        exchange="NASDAQ",
        research_role="core",
        horizon="5-10y",
        research_date=date(2026, 9, 3),
        data_cutoff=date(2026, 9, 3),
        framework_ref="common-stock@1.0.0",
    )
    row, _ = repo.create_run(idem_key="k1", scope=scope)
    yield repo, row.id
