# packages/api/tests/test_cancel_retry.py
from conftest import create_run, run_to_draft


def _lock(client, run_id) -> int:
    return client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]


def _return_to_needs_review(client, run_id) -> None:
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


def _approve(client, run_id, key) -> None:
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": _lock(client, run_id)},
        headers={"Idempotency-Key": key},
    )
    assert r.status_code == 201


def _set_state(client, run_id, state) -> None:
    from fathomark_storage.models import ResearchRunRow

    session = client.app.state.session_factory()
    try:
        row = session.get(ResearchRunRow, run_id)
        row.state = state
        session.commit()
    finally:
        session.close()


# --- cancel ---


def test_cancel_from_created(client):
    run_id = create_run(client, "cancel-1")
    r = client.post(f"/v1/research-runs/{run_id}/cancel")
    assert r.status_code == 200
    assert r.json()["state"] == "cancelled"


def test_cancel_from_draft(client):
    run_id = run_to_draft(client, "cancel-2")
    r = client.post(f"/v1/research-runs/{run_id}/cancel")
    assert r.status_code == 200
    assert r.json()["state"] == "cancelled"


def test_cancel_from_needs_review(client):
    run_id = run_to_draft(client, "cancel-3")
    _return_to_needs_review(client, run_id)
    r = client.post(f"/v1/research-runs/{run_id}/cancel")
    assert r.status_code == 200
    assert r.json()["state"] == "cancelled"


def test_cancel_from_approved_409(client):
    run_id = run_to_draft(client, "cancel-4")
    _approve(client, run_id, "cancel-4-approve")
    r = client.post(f"/v1/research-runs/{run_id}/cancel")
    assert r.status_code == 409


def test_cancel_from_cancelled_409(client):
    run_id = create_run(client, "cancel-5")
    assert client.post(f"/v1/research-runs/{run_id}/cancel").status_code == 200
    r = client.post(f"/v1/research-runs/{run_id}/cancel")
    assert r.status_code == 409


def test_cancel_unknown_run_404(client):
    r = client.post("/v1/research-runs/nope/cancel")
    assert r.status_code == 404


# --- retry ---


def test_retry_requires_idempotency_key_400(client):
    run_id = create_run(client, "retry-1")
    r = client.post(f"/v1/research-runs/{run_id}/retry")
    assert r.status_code == 400


def test_retry_from_non_failed_409(client):
    run_id = run_to_draft(client, "retry-2")
    r = client.post(
        f"/v1/research-runs/{run_id}/retry",
        headers={"Idempotency-Key": "retry-2"},
    )
    assert r.status_code == 409


def test_retry_from_failed_moves_to_collecting(client):
    run_id = run_to_draft(client, "retry-3")
    _set_state(client, run_id, "failed")
    r = client.post(
        f"/v1/research-runs/{run_id}/retry",
        headers={"Idempotency-Key": "retry-3"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "collecting"


def test_retry_replay_after_success_200(client):
    run_id = run_to_draft(client, "retry-4")
    _set_state(client, run_id, "failed")
    r1 = client.post(
        f"/v1/research-runs/{run_id}/retry",
        headers={"Idempotency-Key": "retry-4"},
    )
    r2 = client.post(
        f"/v1/research-runs/{run_id}/retry",
        headers={"Idempotency-Key": "retry-4"},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["state"] == "collecting"


# --- resolve-review ---


def test_resolve_review_moves_to_draft(client):
    run_id = run_to_draft(client, "resolve-1")
    _return_to_needs_review(client, run_id)
    r = client.post(
        f"/v1/research-runs/{run_id}/resolve-review",
        json={"reason": "已补充关联交易证据", "actor": "reviewer-1"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "draft"
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "draft"


def test_resolve_review_records_decision(client):
    from fathomark_storage.models import HumanDecisionRow
    from sqlalchemy import select

    run_id = run_to_draft(client, "resolve-2")
    _return_to_needs_review(client, run_id)
    r = client.post(
        f"/v1/research-runs/{run_id}/resolve-review",
        json={"reason": "已补充关联交易证据", "actor": "reviewer-1"},
    )
    assert r.status_code == 200
    session = client.app.state.session_factory()
    try:
        rows = session.scalars(
            select(HumanDecisionRow).where(
                HumanDecisionRow.run_id == run_id,
                HumanDecisionRow.action == "resolve",
            )
        ).all()
    finally:
        session.close()
    assert len(rows) == 1
    assert rows[0].reason == "已补充关联交易证据"
    assert rows[0].actor == "reviewer-1"


def test_resolve_review_from_draft_409(client):
    run_id = run_to_draft(client, "resolve-3")
    r = client.post(
        f"/v1/research-runs/{run_id}/resolve-review",
        json={"reason": "不需要", "actor": "reviewer-1"},
    )
    assert r.status_code == 409


def test_resolve_review_requires_nonempty_reason_422(client):
    run_id = run_to_draft(client, "resolve-4")
    _return_to_needs_review(client, run_id)
    r = client.post(
        f"/v1/research-runs/{run_id}/resolve-review",
        json={"reason": "", "actor": "reviewer-1"},
    )
    assert r.status_code == 422
