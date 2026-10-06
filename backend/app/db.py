"""SQLite access with a tiny versioned-migration runner (PRAGMA user_version).

Alembic was in the original plan, but plain ordered SQL is enough for a single-user local
database and avoids bundling migration scripts into the PyInstaller binary.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .config import data_dir

# Append only. Never edit or reorder an entry that has shipped; add a new one instead.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
]


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {number}")
    conn.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(data_dir() / "resume-ats.db")
    conn.row_factory = sqlite3.Row
    try:
        _migrate(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
