"""Engine/session factory. Sync SQLAlchemy; SQLite-first, PostgreSQL-safe."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fathomark_storage.models import Base

_ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


def create_session_factory(url: str) -> sessionmaker:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(session_factory: sessionmaker) -> None:
    Base.metadata.create_all(session_factory.kw["bind"])


def migrate_db(url: str) -> None:
    """Run `alembic upgrade head` programmatically against `url`."""
    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
