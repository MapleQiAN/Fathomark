"""The opt-in offline demo must drive the public API through approval."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from fathomark_api import create_app
from fathomark_api.demo import env_orchestrator_factory, fixture_orchestrator_factory

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def test_fixture_demo_factory_drives_create_execute_and_approve(tmp_path):
    scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))["scope"]
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/demo.db",
        framework_dir=ROOT / "frameworks",
        orchestrator_factory=fixture_orchestrator_factory(FIXTURE, ROOT / "frameworks"),
    )

    with TestClient(app) as client:
        created = client.post(
            "/v1/research-runs",
            json=scope,
            headers={"Idempotency-Key": "demo-create"},
        )
        assert created.status_code == 201
        run_id = created.json()["id"]

        executed = client.post(f"/v1/research-runs/{run_id}/execute")
        assert executed.status_code == 200
        assert executed.json()["state"] == "draft"

        lock_version = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
        approved = client.post(
            f"/v1/research-runs/{run_id}/approve",
            json={"expected_lock_version": lock_version},
            headers={"Idempotency-Key": "demo-approve"},
        )
        assert approved.status_code == 201
        assert client.get(f"/v1/research-runs/{run_id}/result").json()["state"] == (
            "approved"
        )


def test_env_orchestrator_factory_is_opt_in(monkeypatch):
    monkeypatch.delenv("FATHOMARK_DEMO_FIXTURE_DIR", raising=False)
    assert env_orchestrator_factory(ROOT / "frameworks") is None

    monkeypatch.setenv("FATHOMARK_DEMO_FIXTURE_DIR", str(FIXTURE))
    assert env_orchestrator_factory(ROOT / "frameworks") is not None
