# packages/api/tests/test_openapi_pinned.py
import json
from pathlib import Path

from fathomark_api import create_app

ROOT = Path(__file__).parents[3]
PINNED = ROOT / "docs" / "api" / "openapi-v1.json"


def test_openapi_document_is_pinned(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path}/pinned.db",
        framework_dir=ROOT / "frameworks",
    )
    committed = json.loads(PINNED.read_text(encoding="utf-8"))
    assert app.openapi() == committed, (
        "OpenAPI drift: run `uv run python scripts/dump_openapi.py` "
        "and commit the updated docs/api/openapi-v1.json"
    )
