from pathlib import Path

from fastapi.testclient import TestClient
from fathomark_api import create_app
from fathomark_api.config import default_database_url

ROOT = Path(__file__).parents[3]


def test_database_url_override_wins(monkeypatch, tmp_path):
    override = f"sqlite:///{tmp_path / 'override.db'}"
    monkeypatch.setenv("DATABASE_URL", override)
    monkeypatch.setenv("FATHOMARK_DATA_DIR", str(tmp_path / "ignored"))

    assert default_database_url() == override
    assert not (tmp_path / "ignored").exists()


def test_default_database_url_creates_app_data_directory(monkeypatch, tmp_path):
    data_dir = tmp_path / "app-data"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FATHOMARK_DATA_DIR", str(data_dir))

    url = default_database_url()

    assert url == f"sqlite:///{data_dir / 'fathomark.sqlite3'}"
    assert data_dir.is_dir()


def test_default_app_exposes_health_without_external_database(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FATHOMARK_DATA_DIR", str(tmp_path / "data"))
    app = create_app(database_url=None, framework_dir=ROOT / "frameworks")

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
