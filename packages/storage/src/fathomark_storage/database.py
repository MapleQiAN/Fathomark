"""Engine/session factory. Sync SQLAlchemy; SQLite-first, PostgreSQL-safe."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fathomark_storage.models import Base


def _alembic_dir() -> Path:
    """Locate the bundled alembic directory.

    Wheel installs ship it inside the package (force-include); editable/src
    checkouts keep it at the package root next to ``src/``.
    """
    installed = Path(__file__).resolve().parent / "alembic"
    if installed.is_dir():
        return installed
    return Path(__file__).resolve().parents[2] / "alembic"


def create_session_factory(url: str) -> sessionmaker:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(session_factory: sessionmaker) -> None:
    Base.metadata.create_all(session_factory.kw["bind"])


def migrate_db(url: str) -> None:
    """Run `alembic upgrade head` programmatically against `url`."""
    cfg = Config()
    cfg.set_main_option("script_location", str(_alembic_dir()))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["url_override"] = url  # explicit arg beats FATHOMARK_DATABASE_URL
    command.upgrade(cfg, "head")
