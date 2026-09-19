# packages/sdk/tests/test_client_contract.py
"""Contract test: FathomarkClient against the real app over an httpx transport.

httpx's ASGITransport is async-only (httpx 0.28), so the fixture drives the
ASGI app through a minimal synchronous transport instead of TestClient.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fathomark_api import create_app
from fathomark_sdk import FathomarkAPIError, FathomarkClient

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "input.json"


class SyncASGITransport(httpx.BaseTransport):
    """Minimal synchronous transport for an ASGI app (request/response only)."""

    def __init__(self, app):
        self.app = app

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = request.read()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": request.method,
            "scheme": request.url.scheme,
            "path": request.url.path,
            "raw_path": request.url.raw_path,
            "query_string": request.url.query,
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in request.headers.items()
            ],
            "client": ("testclient", 50000),
            "server": ("test", 80),
        }
        status = 500
        headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []

        async def receive() -> dict:
            nonlocal body
            chunk, body = body, b""
            return {"type": "http.request", "body": chunk, "more_body": False}

        async def send(message: dict) -> None:
            nonlocal status, headers
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = message["headers"]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        asyncio.run(self.app(scope, receive, send))
        return httpx.Response(status, headers=headers, content=b"".join(chunks))


@pytest.fixture()
def sdk(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/sdk.db",
        framework_dir=ROOT / "frameworks",
    )
    http = httpx.Client(transport=SyncASGITransport(app=app), base_url="http://test")
    with FathomarkClient("http://test", httpx_client=http) as client:
        yield client


def test_full_adbe_flow_via_sdk(sdk):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    run = sdk.create_run(data["scope"], idem_key="sdk-create")
    run_id = run["id"]
    assert run["state"] == "created"
    assert sdk.get_run(run_id)["id"] == run_id

    run = sdk.ingest_evidence(run_id, data["evidence"])
    assert run["state"] == "collecting"

    run = sdk.ingest_proposals(run_id, data["proposals"])
    assert run["state"] == "analyzing"

    snapshot = sdk.compute(run_id)
    assert snapshot["factor_scores"]

    result = sdk.get_result(run_id)
    assert result["state"] == "draft"
    assert result["snapshot"] == snapshot

    lock = sdk.get_run(run_id)["lock_version"]
    version = sdk.approve(run_id, expected_lock_version=lock, idem_key="sdk-approve")
    assert version["version_no"] == 1
    assert version["content_hash"].startswith("sha256:")

    # idempotent replay: same version, no new row
    replay = sdk.approve(run_id, expected_lock_version=lock, idem_key="sdk-approve")
    assert replay["id"] == version["id"]

    result = sdk.get_result(run_id)
    assert result["state"] == "approved"
    assert result["version"]["id"] == version["id"]


def test_error_raises_fathomark_api_error(sdk):
    with pytest.raises(FathomarkAPIError) as excinfo:
        sdk.get_run("does-not-exist")
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail
