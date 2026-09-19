# packages/api/tests/conftest.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fathomark_api import create_app

ROOT = Path(__file__).parents[3]


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
    )
    with TestClient(app) as c:
        yield c


CREATE_PAYLOAD = {
    "symbol": "ADBE",
    "exchange": "NASDAQ",
    "research_role": "core",
    "horizon": "3y",
    "research_date": "2026-09-03",
    "data_cutoff": "2026-09-03",
    "framework_ref": "common-stock@1.0.0",
}


def create_run(client, key="create-1") -> str:
    r = client.post(
        "/v1/research-runs", json=CREATE_PAYLOAD, headers={"Idempotency-Key": key}
    )
    assert r.status_code == 201
    return r.json()["id"]


def run_to_draft(client, key_prefix="e2e") -> str:
    """ADBE fixture through ingest + compute; returns run_id in state draft."""
    import json

    data = json.loads(
        (ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "input.json").read_text(
            encoding="utf-8"
        )
    )
    r = client.post(
        "/v1/research-runs",
        json=data["scope"],
        headers={"Idempotency-Key": f"{key_prefix}-create"},
    )
    assert r.status_code == 201
    run_id = r.json()["id"]
    assert (
        client.post(
            f"/v1/research-runs/{run_id}/evidence", json={"evidence": data["evidence"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/research-runs/{run_id}/factor-proposals",
            json={"proposals": data["proposals"]},
        ).status_code
        == 200
    )
    assert client.post(f"/v1/research-runs/{run_id}/compute").status_code == 200
    return run_id
