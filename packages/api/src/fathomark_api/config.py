"""Zero-config local runtime paths with explicit environment overrides."""

import os
import sys
from pathlib import Path


def default_data_dir() -> Path:
    configured = os.getenv("FATHOMARK_DATA_DIR")
    if configured:
        path = Path(configured).expanduser()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Fathomark"
    elif sys.platform == "win32":
        path = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path /= "Fathomark"
    else:
        path = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path /= "fathomark"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_database_url() -> str:
    """Return ``DATABASE_URL`` or create the local SQLite app-data path."""
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{default_data_dir() / 'fathomark.sqlite3'}"


def default_framework_dir() -> Path:
    configured = os.getenv("FATHOMARK_FRAMEWORK_DIR")
    if configured:
        return Path(configured).expanduser()
    source_root = Path(__file__).resolve().parents[4] / "frameworks"
    if source_root.is_dir():
        return source_root
    return Path("/app/frameworks")
