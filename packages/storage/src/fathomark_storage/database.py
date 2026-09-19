"""Engine/session factory. Sync SQLAlchemy; SQLite-first, PostgreSQL-safe."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fathomark_storage.models import Base


def create_session_factory(url: str) -> sessionmaker:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(session_factory: sessionmaker) -> None:
    Base.metadata.create_all(session_factory.kw["bind"])
