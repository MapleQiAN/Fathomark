"""Alembic baseline migration must reproduce the create_all schema."""

import sqlite3

from fathomark_storage.database import create_session_factory, init_db, migrate_db

EXPECTED_TABLES = {
    "research_runs",
    "evidence_items",
    "metric_observations",
    "review_issues",
    "factor_proposals",
    "human_decisions",
    "score_snapshots",
    "research_versions",
    "step_runs",
    "artifacts",
}


def _schema(db_path) -> dict[str, list[str]]:
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
            for t in sorted(tables)
        }
    finally:
        conn.close()


def test_migration_matches_create_all(tmp_path):
    migrated = tmp_path / "migrated.db"
    migrate_db(f"sqlite:///{migrated}")

    created = tmp_path / "created.db"
    init_db(create_session_factory(f"sqlite:///{created}"))

    migrated_schema = _schema(migrated)
    created_schema = _schema(created)

    assert EXPECTED_TABLES | {"alembic_version"} == set(migrated_schema)
    assert EXPECTED_TABLES == set(created_schema)
    for table in EXPECTED_TABLES:
        assert migrated_schema[table] == created_schema[table], table


def test_alembic_version_at_head(tmp_path):
    db = tmp_path / "versioned.db"
    migrate_db(f"sqlite:///{db}")

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    finally:
        conn.close()
    assert rows == [("0005",)]


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "twice.db"
    url = f"sqlite:///{db}"
    migrate_db(url)
    migrate_db(url)

    assert EXPECTED_TABLES | {"alembic_version"} == set(_schema(db))


def test_migrate_db_argument_wins_over_env_var(tmp_path, monkeypatch):
    """Explicit migrate_db(url) must not be hijacked by FATHOMARK_DATABASE_URL."""
    env_db = tmp_path / "env.db"
    monkeypatch.setenv("FATHOMARK_DATABASE_URL", f"sqlite:///{env_db}")

    arg_db = tmp_path / "arg.db"
    migrate_db(f"sqlite:///{arg_db}")

    assert EXPECTED_TABLES | {"alembic_version"} == set(_schema(arg_db))
    assert not env_db.exists()
