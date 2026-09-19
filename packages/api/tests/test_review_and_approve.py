# packages/api/tests/test_review_and_approve.py
from conftest import run_to_draft


def _lock(client, run_id) -> int:
    return client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]


def test_modify_records_decision_and_recomputes(client):
    run_id = run_to_draft(client, "rev-1")
    before = client.get(f"/v1/research-runs/{run_id}/result").json()["snapshot"]
    old_total = before["lens_results"]["core"]["total"]

    r = client.post(
        f"/v1/research-runs/{run_id}/review-decisions",
        json={
            "action": "modify",
            "factor": "financial_health",
            "final_score": 7.0,
            "reason": "利息覆盖率下降趋势被低估",
            "actor": "reviewer-1",
            "expected_lock_version": _lock(client, run_id),
        },
    )
    assert r.status_code == 200
    after = client.get(f"/v1/research-runs/{run_id}/result").json()["snapshot"]
    assert after["factor_scores"]["financial_health"] == 7.0
    assert after["lens_results"]["core"]["total"] != old_total
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "draft"


def test_review_stale_lock_409(client):
    run_id = run_to_draft(client, "rev-2")
    r = client.post(
        f"/v1/research-runs/{run_id}/review-decisions",
        json={
            "action": "accept",
            "reason": "ok",
            "actor": "reviewer-1",
            "expected_lock_version": 999,
        },
    )
    assert r.status_code == 409


def test_review_requires_nonempty_reason(client):
    run_id = run_to_draft(client, "rev-3")
    r = client.post(
        f"/v1/research-runs/{run_id}/review-decisions",
        json={
            "action": "accept",
            "reason": "",
            "actor": "reviewer-1",
            "expected_lock_version": _lock(client, run_id),
        },
    )
    assert r.status_code == 422


def test_return_moves_to_needs_review(client):
    run_id = run_to_draft(client, "rev-4")
    r = client.post(
        f"/v1/research-runs/{run_id}/review-decisions",
        json={
            "action": "return",
            "reason": "缺少关联交易证据",
            "actor": "reviewer-1",
            "expected_lock_version": _lock(client, run_id),
        },
    )
    assert r.status_code == 200
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "needs_review"


def test_approve_creates_immutable_version(client):
    run_id = run_to_draft(client, "app-1")
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": _lock(client, run_id)},
        headers={"Idempotency-Key": "app-1"},
    )
    assert r.status_code == 201
    version = r.json()
    assert version["version_no"] == 1
    assert version["content_hash"].startswith("sha256:")
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "approved"

    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    assert result["state"] == "approved"
    assert result["version"]["id"] == version["id"]


def test_approve_replay_same_version(client):
    run_id = run_to_draft(client, "app-2")
    lock = _lock(client, run_id)
    r1 = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "app-2"},
    )
    r2 = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "app-2"},
    )
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_approve_stale_lock_409(client):
    run_id = run_to_draft(client, "app-3")
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": 999},
        headers={"Idempotency-Key": "app-3"},
    )
    assert r.status_code == 409


def test_approve_wrong_state_409(client):
    from conftest import create_run

    run_id = create_run(client, "app-4")
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": 0},
        headers={"Idempotency-Key": "app-4"},
    )
    assert r.status_code == 409
