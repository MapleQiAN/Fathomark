from datetime import date

from fathomark_core.schemas import ScopeSnapshot
from fathomark_storage.database import create_session_factory, init_db
from fathomark_storage.repository import RunRepository


def _repo(tmp_path):
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
    return repo, row.id


def test_step_lifecycle(tmp_path):
    repo, run_id = _repo(tmp_path)
    assert repo.step_record(run_id, "scope") is None
    rec = repo.begin_step(
        run_id, "scope", "sha256:abc", provider_name="scope-agent", provider_version="1"
    )
    assert rec.status == "running" and rec.attempt == 1
    repo.finish_step(run_id, "scope", {"frozen": True})
    rec = repo.step_record(run_id, "scope")
    assert rec.status == "succeeded" and rec.output_json == {"frozen": True}
    assert rec.finished_at is not None


def test_begin_step_retries_increment_attempt(tmp_path):
    repo, run_id = _repo(tmp_path)
    repo.begin_step(run_id, "collect", "sha256:abc")
    repo.fail_step(run_id, "collect", "provider down")
    rec = repo.begin_step(run_id, "collect", "sha256:abc")
    assert rec.attempt == 2 and rec.status == "running" and rec.error is None
    assert len(repo.steps_of(run_id)) == 1  # upsert, not duplicate
