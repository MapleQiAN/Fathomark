# packages/api/tests/test_webhooks.py
import json
import time

import pytest
from conftest import ROOT, run_to_draft
from fastapi.testclient import TestClient
from fathomark_api import create_app
from fathomark_api.webhooks import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookDispatcher,
    WebhookEvent,
    sign,
    verify,
)

SECRET = b"test-secret"


def test_sign_verify_roundtrip():
    body = b'{"event":"approved"}'
    ts = int(time.time())
    sig = sign(SECRET, ts, body)
    assert verify(SECRET, sig, ts, body) is True


def test_verify_tampered_body_rejected():
    ts = int(time.time())
    sig = sign(SECRET, ts, b'{"event":"approved"}')
    assert verify(SECRET, sig, ts, b'{"event":"failed"}') is False


def test_verify_expired_timestamp_rejected():
    body = b"{}"
    ts = int(time.time()) - 301
    sig = sign(SECRET, ts, body)
    assert verify(SECRET, sig, ts, body) is False
    now = ts + 300
    assert verify(SECRET, sig, ts, body, now=now) is True
    assert verify(SECRET, sig, ts, body, now=now + 1) is False


def test_verify_future_timestamp_beyond_tolerance_rejected():
    body = b"{}"
    now = int(time.time())
    ts = now + 301
    sig = sign(SECRET, ts, body)
    assert verify(SECRET, sig, ts, body, now=now) is False
    assert verify(SECRET, sig, ts, body, now=now + 300) is True


def test_verify_wrong_secret_rejected():
    body = b"{}"
    ts = int(time.time())
    sig = sign(b"other-secret", ts, body)
    assert verify(SECRET, sig, ts, body) is False


def test_dispatcher_sends_verifiable_signature():
    sent = []
    dispatcher = WebhookDispatcher(
        "https://hooks.example.test/fm",
        "test-secret",
        lambda url, headers, body: sent.append((url, headers, body)),
    )
    event = WebhookEvent(
        event="approved",
        run_id="run-1",
        occurred_at=1_700_000_000,
        payload={"version_id": "v1"},
    )
    dispatcher.dispatch(event)

    assert len(sent) == 1
    url, headers, body = sent[0]
    assert url == "https://hooks.example.test/fm"
    assert headers["Content-Type"] == "application/json"
    ts = int(headers[TIMESTAMP_HEADER])
    assert verify(SECRET, headers[SIGNATURE_HEADER], ts, body) is True
    # Body is canonical JSON (sorted keys, tight separators)
    assert (
        body
        == json.dumps(json.loads(body), separators=(",", ":"), sort_keys=True).encode()
    )
    assert json.loads(body)["event"] == "approved"


@pytest.fixture()
def hooked_client(tmp_path):
    """App with a recording webhook dispatcher; yields (client, deliveries)."""
    deliveries = []
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
    )
    app.state.webhook_dispatcher = WebhookDispatcher(
        "https://hooks.example.test/fm",
        "test-secret",
        lambda url, headers, body: deliveries.append((url, headers, body)),
    )
    with TestClient(app) as c:
        yield c, deliveries


def _events(deliveries):
    return [json.loads(body) for _, _, body in deliveries]


def test_approve_fires_exactly_one_approved_event(hooked_client):
    client, deliveries = hooked_client
    run_id = run_to_draft(client, "wh-app-1")
    lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "wh-app-1"},
    )
    assert r.status_code == 201
    events = _events(deliveries)
    assert [e["event"] for e in events] == ["approved"]
    assert events[0]["run_id"] == run_id
    # Headers carry a verifiable signature
    _, headers, body = deliveries[0]
    assert (
        verify(SECRET, headers[SIGNATURE_HEADER], int(headers[TIMESTAMP_HEADER]), body)
        is True
    )

    # Idempotent replay fires no second event
    r2 = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "wh-app-1"},
    )
    assert r2.status_code == 200
    assert len(deliveries) == 1


def test_review_return_fires_needs_review_event(hooked_client):
    client, deliveries = hooked_client
    run_id = run_to_draft(client, "wh-rev-1")
    lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
    r = client.post(
        f"/v1/research-runs/{run_id}/review-decisions",
        json={
            "action": "return",
            "reason": "缺少证据",
            "actor": "reviewer-1",
            "expected_lock_version": lock,
        },
    )
    assert r.status_code == 200
    events = _events(deliveries)
    assert [e["event"] for e in events] == ["needs_review"]
    assert events[0]["run_id"] == run_id
    assert events[0]["payload"]["reason"] == "缺少证据"


def test_failed_mutation_delivers_no_events(hooked_client):
    """A 409 (stale lock) rolls back before dispatch: zero phantom events."""
    client, deliveries = hooked_client
    run_id = run_to_draft(client, "wh-stale-1")
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": 999},
        headers={"Idempotency-Key": "wh-stale-1"},
    )
    assert r.status_code == 409
    assert deliveries == []


def test_sender_failure_does_not_break_mutation(tmp_path):
    def boom(url, headers, body):
        raise RuntimeError("webhook endpoint down")

    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
    )
    app.state.webhook_dispatcher = WebhookDispatcher(
        "https://hooks.example.test/fm", "test-secret", boom
    )
    with TestClient(app) as client:
        run_id = run_to_draft(client, "wh-fail-1")
        lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
        r = client.post(
            f"/v1/research-runs/{run_id}/approve",
            json={"expected_lock_version": lock},
            headers={"Idempotency-Key": "wh-fail-1"},
        )
        assert r.status_code == 201
        assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "approved"


def test_app_without_webhooks_still_works(client):
    run_id = run_to_draft(client, "wh-none-1")
    lock = client.get(f"/v1/research-runs/{run_id}").json()["lock_version"]
    r = client.post(
        f"/v1/research-runs/{run_id}/approve",
        json={"expected_lock_version": lock},
        headers={"Idempotency-Key": "wh-none-1"},
    )
    assert r.status_code == 201
