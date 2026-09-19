"""FastAPI app factory."""

from pathlib import Path

from fastapi import FastAPI
from fathomark_storage import create_session_factory, init_db

from fathomark_api.routes.runs import router as runs_router


def create_app(database_url: str, framework_dir: Path) -> FastAPI:
    app = FastAPI(title="Fathomark API", version="0.1.0")
    session_factory = create_session_factory(database_url)
    init_db(session_factory)
    app.state.session_factory = session_factory
    app.state.framework_dir = framework_dir
    app.include_router(runs_router, prefix="/v1")
    return app
