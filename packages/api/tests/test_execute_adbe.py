# packages/api/tests/test_execute_adbe.py
"""Offline e2e: create run -> execute -> draft matching golden snapshot."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fathomark_agents import Orchestrator
from fathomark_api import create_app
from fathomark_core import load_framework
from fathomark_providers import FixtureEvidenceProvider, ReplayLLMProvider

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"


@pytest.fixture()
def client(tmp_path):
    fixture = FIXTURE

    def factory(repo):
        return Orchestrator(
            repo,
            load_framework(ROOT / "frameworks" / "common-stock.yaml"),
            llm=ReplayLLMProvider(fixture / "llm_cassette.json"),
            evidence_providers=[
                FixtureEvidenceProvider(fixture / "provider_dump.json")
            ],
            stub_path=fixture / "stub_proposals.json",
        )

    app = create_app(
        database_url=f"sqlite:///{tmp_path}/test.db",
        framework_dir=ROOT / "frameworks",
        orchestrator_factory=factory,
    )
    with TestClient(app) as c:
        yield c


def test_create_execute_draft_offline(client):
    scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))["scope"]
    r = client.post(
        "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-1"}
    )
    assert r.status_code == 201
    run_id = r.json()["id"]

    r = client.post(f"/v1/research-runs/{run_id}/execute")
    assert r.status_code == 200
    assert r.json()["state"] == "draft"

    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    expected = json.loads(
        (FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8")
    )
    assert result["snapshot"] == expected
    assert result["snapshot"]["content_hash"] == expected["content_hash"]


def test_execute_twice_is_idempotent(client):
    scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))["scope"]
    run_id = client.post(
        "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-2"}
    ).json()["id"]
    assert client.post(f"/v1/research-runs/{run_id}/execute").json()["state"] == "draft"
    assert client.post(f"/v1/research-runs/{run_id}/execute").json()["state"] == "draft"
    result = client.get(f"/v1/research-runs/{run_id}/result").json()
    assert (
        result["snapshot"]["content_hash"]
        == json.loads((FIXTURE / "expected_snapshot.json").read_text(encoding="utf-8"))[
            "content_hash"
        ]
    )


def test_execute_without_orchestrator_configured(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/t.db", framework_dir=ROOT / "frameworks"
    )
    with TestClient(app) as c:
        scope = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))[
            "scope"
        ]
        run_id = c.post(
            "/v1/research-runs", json=scope, headers={"Idempotency-Key": "m3-3"}
        ).json()["id"]
        assert c.post(f"/v1/research-runs/{run_id}/execute").status_code == 503
