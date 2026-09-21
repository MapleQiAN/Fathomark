import base64

from conftest import run_to_draft


def test_artifact_upload_list_download_and_idempotent_replay(client):
    run_id = run_to_draft(client, key_prefix="artifact")
    encoded = base64.b64encode(b"# draft report\n").decode("ascii")
    payload = {
        "name": "report.md",
        "media_type": "text/markdown; charset=utf-8",
        "content_base64": encoded,
        "manifest_hash": "sha256:manifest",
        "status": "draft",
    }

    response = client.post(
        f"/v1/research-runs/{run_id}/artifacts",
        json=payload,
        headers={"Idempotency-Key": "artifact-upload"},
    )
    assert response.status_code == 201
    artifact = response.json()
    assert artifact["name"] == "report.md"
    assert artifact["size_bytes"] == len(b"# draft report\n")
    assert artifact["content_hash"].startswith("sha256:")

    listed = client.get(f"/v1/research-runs/{run_id}/artifacts")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [artifact["id"]]

    downloaded = client.get(f"/v1/artifacts/{artifact['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"# draft report\n"
    assert downloaded.headers["content-type"] == "text/markdown; charset=utf-8"

    replay = client.post(
        f"/v1/research-runs/{run_id}/artifacts",
        json=payload,
        headers={"Idempotency-Key": "artifact-upload"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == artifact["id"]
