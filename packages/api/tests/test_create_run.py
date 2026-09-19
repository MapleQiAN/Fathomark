# packages/api/tests/test_create_run.py
from conftest import CREATE_PAYLOAD


def test_create_run_returns_201(client):
    r = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-1"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "created" and body["symbol"] == "ADBE"
    assert body["lock_version"] == 0


def test_create_run_requires_idempotency_key(client):
    r = client.post("/v1/research-runs", json=CREATE_PAYLOAD)
    assert r.status_code == 400


def test_create_run_replay_returns_same_run(client):
    r1 = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-2"},
    )
    r2 = client.post(
        "/v1/research-runs",
        json=CREATE_PAYLOAD,
        headers={"Idempotency-Key": "create-2"},
    )
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_get_unknown_run_404(client):
    assert client.get("/v1/research-runs/run_nope").status_code == 404
