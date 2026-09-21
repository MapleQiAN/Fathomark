"""FastAPI app factory."""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fathomark_storage import create_session_factory, init_db

from fathomark_api.config import default_database_url
from fathomark_api.routes.runs import router as runs_router
from fathomark_api.webhooks import WebhookDispatcher


def create_app(
    database_url: str | None,
    framework_dir: Path,
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    orchestrator_factory: Callable | None = None,
) -> FastAPI:
    app = FastAPI(title="Fathomark API", version="0.1.0")
    database_url = database_url or default_database_url()
    session_factory = create_session_factory(database_url)
    init_db(session_factory)
    app.state.session_factory = session_factory
    app.state.database_url = database_url
    app.state.framework_dir = framework_dir
    app.state.webhook_dispatcher = (
        WebhookDispatcher(webhook_url, webhook_secret)
        if webhook_url and webhook_secret
        else None
    )
    app.state.orchestrator_factory = orchestrator_factory
    app.include_router(runs_router, prefix="/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
