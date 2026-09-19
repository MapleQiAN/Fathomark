# packages/api/tests/test_e2e_adbe.py
import json
from pathlib import Path

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


def test_adbe_fixture_create_to_approve(client):
    data = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8")
    )

    r = client.post(
        "/v1/research-runs",
        json=data["scope"],
        headers={"Idempotency-Key": "e2e-create"},
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

    r = client.post(f"/v1/research-runs/{run_id}/compute")
    assert r.status_code == 200
    assert r.json() == expected  # same snapshot as offline core

    lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "e2e-approve"},
    )
    assert r.status_code == 201

    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    assert result["state"] == "approved"
    assert result["version"]["snapshot_json"] == expected

    # duplicate approve: same version, no new row
    r2 = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "e2e-approve"},
    )
    assert r2.status_code == 200 and r2.json()["id"] == r.json()["id"]
