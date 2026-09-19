"""Optional PostgreSQL integration path for the storage repository.

CI runs the suite against SQLite only; this module replicates the core
``RunRepository`` behaviors against PostgreSQL when one is available.

To run it locally you need a reachable PostgreSQL server, the ``psycopg2``
driver (``uv pip install psycopg2-binary`` or ``psycopg``), and::

    PG_TEST_URL=postgresql+psycopg2://user:pass@host:5432/dbname \
        uv run pytest packages/storage/tests/test_postgres.py -q

The URL may use any SQLAlchemy PostgreSQL dialect (``psycopg``, ``psycopg2``,
``asyncpg`` is not supported here — the repo is sync). The configured role
needs CREATE/DROP privilege: each test run does ``create_all`` in setup and
``drop_all`` in teardown.
"""

import os
from datetime import datetime

import pytest
from fathomark_core.schemas import EvidenceItem, FactorProposal
from fathomark_core.snapshot import ScoreSnapshot
from fathomark_storage import create_session_factory, init_db
from fathomark_storage.models import Base
from fathomark_storage.repository import ConcurrencyError, RunRepository
from fathomark_storage.state_machine import InvalidTransition, RunState
from test_repository import SCOPE

PG_TEST_URL = os.environ.get("PG_TEST_URL")

pytestmark = pytest.mark.skipif(not PG_TEST_URL, reason="PG_TEST_URL not set")

EVIDENCE = EvidenceItem(
    id="ev_pg1",
    source_name="SEC EDGAR",
    source_class="filings",
    url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000796343",
    published_date=SCOPE.data_cutoff,
    data_period_end=SCOPE.data_cutoff,
    # Columns are naive DateTime on both backends; tzinfo would not survive
    # the roundtrip, so keep the fixture naive for equality checks.
    accessed_at=datetime(2026, 9, 3),
    grade="A",
    content_hash="sha256:" + "ab" * 32,
    excerpt="10-K filing excerpt",
)

PROPOSAL = FactorProposal(
    factor="moat",
    proposed_score=4.0,
    rationale="Durable switching costs in the creative toolchain.",
    evidence_ids=[EVIDENCE.id],
    counter_evidence_ids=[],
    confidence="high",
    missing_data=[],
    as_of_date=SCOPE.data_cutoff,
)


@pytest.fixture()
def pg_repo():
    sf = create_session_factory(PG_TEST_URL)
    init_db(sf)
    with sf() as s:
        yield RunRepository(s)
    Base.metadata.drop_all(sf.kw["bind"])
    sf.kw["bind"].dispose()


def _snapshot() -> ScoreSnapshot:
    return ScoreSnapshot(
        scope=SCOPE,
        lens_results={},
        factor_scores={"moat": 4.0},
        overall_confidence="high",
        content_hash="sha256:" + "cd" * 32,
    )


def test_create_run_idempotent(pg_repo):
    row1, created1 = pg_repo.create_run(idem_key="pg_k1", scope=SCOPE)
    row2, created2 = pg_repo.create_run(idem_key="pg_k1", scope=SCOPE)
    assert created1 and not created2 and row1.id == row2.id


def test_advance_guards_illegal_transition(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k2", scope=SCOPE)
    with pytest.raises(InvalidTransition):
        pg_repo.advance(row.id, RunState.APPROVED)
    pg_repo.advance(row.id, RunState.COLLECTING)
    assert pg_repo.get(row.id).lock_version == 1


def test_scope_roundtrip(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k3", scope=SCOPE)
    assert pg_repo.scope_of(row.id) == SCOPE


def test_touch_bumps_lock_without_transition(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k4", scope=SCOPE)
    pg_repo.touch(row.id)
    after = pg_repo.get(row.id)
    assert after.lock_version == 1 and after.state == "created"


def test_add_evidence_and_reject_duplicate(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k5", scope=SCOPE)
    assert pg_repo.add_evidence(row.id, [EVIDENCE]) == 1
    assert pg_repo.evidence_of(row.id) == [EVIDENCE]
    with pytest.raises(ValueError, match="duplicate evidence id"):
        pg_repo.add_evidence(row.id, [EVIDENCE])


def test_add_proposals(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k6", scope=SCOPE)
    pg_repo.add_evidence(row.id, [EVIDENCE])
    pg_repo.add_proposals(row.id, [PROPOSAL])
    assert pg_repo.proposals_of(row.id) == [PROPOSAL]
    with pytest.raises(ValueError, match="duplicate proposal"):
        pg_repo.add_proposals(row.id, [PROPOSAL])


def test_create_version_idempotent_replay(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k7", scope=SCOPE)
    pg_repo.save_draft_snapshot(row.id, _snapshot())
    for target in (RunState.COLLECTING, RunState.ANALYZING, RunState.DRAFT):
        pg_repo.advance(row.id, target)
    # Three transitions bumped lock_version from 0 to 3.
    version1, created1 = pg_repo.create_version(
        row.id, idem_key="pg_v1", expected_lock=3
    )
    version2, created2 = pg_repo.create_version(
        row.id, idem_key="pg_v1", expected_lock=3
    )
    assert created1 and not created2 and version1.id == version2.id
    assert version1.version_no == 1


def test_create_version_rejects_stale_lock(pg_repo):
    row, _ = pg_repo.create_run(idem_key="pg_k8", scope=SCOPE)
    pg_repo.save_draft_snapshot(row.id, _snapshot())
    pg_repo.touch(row.id)
    with pytest.raises(ConcurrencyError):
        pg_repo.create_version(row.id, idem_key="pg_v2", expected_lock=0)
