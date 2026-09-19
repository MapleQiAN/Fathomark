import json
from datetime import date
from pathlib import Path

import pytest
from fathomark_core import load_framework
from fathomark_core.schemas import EvidenceItem, ScopeSnapshot
from fathomark_storage.database import create_session_factory, init_db
from fathomark_storage.repository import RunRepository

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


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


@pytest.fixture(scope="module")
def scope():
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    return ScopeSnapshot.model_validate(data["scope"])


@pytest.fixture(scope="module")
def evidence():
    data = json.loads((FIXTURE / "provider_dump.json").read_text(encoding="utf-8"))
    return [EvidenceItem.model_validate(e) for e in data["evidence"]]


@pytest.fixture(scope="module")
def framework():
    return load_framework(ROOT / "frameworks" / "common-stock.yaml")
