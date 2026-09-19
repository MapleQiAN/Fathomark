# packages/storage/tests/test_repository.py
from datetime import date

import pytest
from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage import create_session_factory, init_db
from fathomark_storage.repository import RunRepository
from fathomark_storage.state_machine import InvalidTransition, RunState

SCOPE = ScopeSnapshot(
    symbol="ADBE",
    exchange="NASDAQ",
    research_role="core",
    horizon="3y",
    research_date=date(2026, 9, 3),
    data_cutoff=date(2026, 9, 3),
    framework_ref="common-stock@1.0.0",
)


@pytest.fixture()
def repo():
    sf = create_session_factory("sqlite:///:memory:")
    init_db(sf)
    with sf() as s:
        yield RunRepository(s)


def test_create_run_idempotent(repo):
    row1, created1 = repo.create_run(idem_key="k1", scope=SCOPE)
    row2, created2 = repo.create_run(idem_key="k1", scope=SCOPE)
    assert created1 and not created2 and row1.id == row2.id


def test_advance_guards_illegal_transition(repo):
    row, _ = repo.create_run(idem_key="k2", scope=SCOPE)
    with pytest.raises(InvalidTransition):
        repo.advance(row.id, RunState.APPROVED)
    repo.advance(row.id, RunState.COLLECTING)
    assert repo.get(row.id).lock_version == 1


def test_touch_bumps_lock_without_transition(repo):
    row, _ = repo.create_run(idem_key="k4", scope=SCOPE)
    repo.touch(row.id)
    after = repo.get(row.id)
    assert after.lock_version == 1 and after.state == "created"


def test_scope_roundtrip(repo):
    row, _ = repo.create_run(idem_key="k3", scope=SCOPE)
    assert repo.scope_of(row.id) == SCOPE
