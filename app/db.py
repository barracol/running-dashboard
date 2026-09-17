from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def migrate() -> None:
    with database() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(migration.stem.split("_", 1)[0])
            if version in applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
