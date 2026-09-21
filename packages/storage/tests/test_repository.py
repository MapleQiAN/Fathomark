# packages/storage/tests/test_repository.py
from datetime import UTC, date, datetime

import pytest
from fathomark_core.schemas import EvidenceItem, MetricObservation, ScopeSnapshot
from fathomark_storage import create_session_factory, init_db
from fathomark_storage.models import MetricObservationRow
from fathomark_storage.repository import RunRepository
from fathomark_storage.state_machine import InvalidTransition, RunState
from sqlalchemy.exc import IntegrityError

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


def _evidence(evidence_id: str = "ev_metric") -> EvidenceItem:
    return EvidenceItem(
        id=evidence_id,
        source_name="Recorded filing",
        source_class="filings",
        url="https://example.test/filing",
        published_date=date(2026, 6, 15),
        data_period_end=date(2026, 5, 29),
        accessed_at=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
        grade="A",
        content_hash="sha256:metric-evidence",
        excerpt="Recorded evidence.",
    )


def _observation(evidence_id: str = "ev_metric") -> MetricObservation:
    return MetricObservation(
        metric="revenue",
        value=5_870_000,
        unit="USD",
        currency="USD",
        basis="quarterly",
        formula=None,
        data_date=date(2026, 5, 29),
        evidence_id=evidence_id,
    )


def test_metric_observation_round_trips_with_its_evidence(repo):
    run, _ = repo.create_run(idem_key="metric-roundtrip", scope=SCOPE)
    repo.add_evidence(run.id, [_evidence()])

    repo.add_metric_observations(run.id, [_observation()])

    assert repo.metric_observations_of(run.id) == [_observation()]


def test_sqlite_rejects_metric_observation_without_its_evidence(repo):
    run, _ = repo.create_run(idem_key="metric-foreign-key", scope=SCOPE)
    repo.session.commit()
    repo.session.add(
        MetricObservationRow(
            run_id=run.id,
            metric="revenue",
            value=5_870_000,
            unit="USD",
            currency="USD",
            basis="quarterly",
            formula=None,
            data_date=date(2026, 5, 29),
            evidence_id="ev_missing",
        )
    )

    with pytest.raises(IntegrityError):
        repo.session.flush()

    repo.session.rollback()
    assert repo.get(run.id).id == run.id
