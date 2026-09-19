# packages/api/tests/test_ingest_and_compute.py
import json
from pathlib import Path

from conftest import create_run

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
DATA = json.loads((FIXTURE / "input.json").read_text(encoding="utf-8"))


def test_ingest_evidence_advances_to_collecting(client):
    run_id = create_run(client, "ing-1")
    r = client.post(
        f"/v1/research-runs/{run_id}/evidence", json={"evidence": DATA["evidence"]}
    )
    assert r.status_code == 200
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "collecting"


def test_ingest_proposals_advances_to_analyzing(client):
    run_id = create_run(client, "ing-2")
    client.post(
        f"/v1/research-runs/{run_id}/evidence", json={"evidence": DATA["evidence"]}
    )
    r = client.post(
        f"/v1/research-runs/{run_id}/factor-proposals",
        json={"proposals": DATA["proposals"]},
    )
    assert r.status_code == 200
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "analyzing"


def test_ingest_evidence_wrong_state_409(client):
    run_id = create_run(client, "ing-3")
    client.post(
        f"/v1/research-runs/{run_id}/evidence", json={"evidence": DATA["evidence"]}
    )
    r = client.post(
        f"/v1/research-runs/{run_id}/evidence", json={"evidence": DATA["evidence"]}
    )
    assert r.status_code == 409


def test_compute_produces_draft_snapshot(client):
    run_id = create_run(client, "ing-4")
    client.post(
        f"/v1/research-runs/{run_id}/evidence", json={"evidence": DATA["evidence"]}
    )
    client.post(
        f"/v1/research-runs/{run_id}/factor-proposals",
        json={"proposals": DATA["proposals"]},
    )
    r = client.post(f"/v1/research-runs/{run_id}/compute")
    assert r.status_code == 200
    snap = r.json()
    assert snap["lens_results"]["core"]["total"] == 85.75
    assert snap["lens_results"]["core"]["rating"] == "A+"
    assert client.get(f"/v1/research-runs/{run_id}").json()["state"] == "draft"


def test_compute_wrong_state_409(client):
    run_id = create_run(client, "ing-5")
    assert client.post(f"/v1/research-runs/{run_id}/compute").status_code == 409
