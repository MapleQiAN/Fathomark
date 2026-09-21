"""ASGI entrypoint for local and containerized Fathomark runs."""

import os

from fathomark_api.app import create_app
from fathomark_api.config import default_framework_dir
from fathomark_api.demo import env_orchestrator_factory

framework_dir = default_framework_dir()
app = create_app(
    database_url=os.getenv("DATABASE_URL"),
    framework_dir=framework_dir,
    orchestrator_factory=env_orchestrator_factory(framework_dir),
)
