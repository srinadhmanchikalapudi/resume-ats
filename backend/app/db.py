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
    # Application archive: one row per job, its exported resume versions, and its status timeline.
    """
    CREATE TABLE application (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        company TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        location TEXT NOT NULL DEFAULT '',
        job_url TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'saved',
        applied_on TEXT,
        interview_on TEXT,
        notes TEXT NOT NULL DEFAULT '',
        posting_text TEXT NOT NULL,
        posting_hash TEXT NOT NULL,
        analysis_json TEXT,
        match_score INTEGER,
        folder TEXT NOT NULL
    );
    CREATE INDEX idx_application_status ON application (status);
    CREATE INDEX idx_application_hash ON application (posting_hash);

    CREATE TABLE resume_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL REFERENCES application (id) ON DELETE CASCADE,
        number INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        subdir TEXT NOT NULL,
        docx_name TEXT NOT NULL,
        pdf_name TEXT NOT NULL,
        pages INTEGER,
        checks_passed INTEGER NOT NULL DEFAULT 1,
        skills_first INTEGER NOT NULL DEFAULT 1,
        submitted INTEGER NOT NULL DEFAULT 0,
        profile_json TEXT NOT NULL
    );
    CREATE INDEX idx_version_application ON resume_version (application_id);

    CREATE TABLE status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL REFERENCES application (id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        changed_at TEXT NOT NULL
    );
    CREATE INDEX idx_history_application ON status_history (application_id);
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
    conn.execute("PRAGMA foreign_keys = ON")  # needed per connection for ON DELETE CASCADE
    try:
        _migrate(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
