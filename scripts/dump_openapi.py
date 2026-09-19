"""Dump the pinned OpenAPI document for the /v1 API.

Usage: uv run python scripts/dump_openapi.py
"""

import json
import tempfile
from pathlib import Path

from fathomark_api import create_app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "api" / "openapi-v1.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(
            database_url=f"sqlite:///{tmp}/openapi.db",
            framework_dir=ROOT / "frameworks",
        )
    spec = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
