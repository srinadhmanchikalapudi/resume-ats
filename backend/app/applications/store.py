"""SQL for the application archive. Disk files are handled separately in files.py."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

from ..db import connect
from ..jobs.models import AnalysisResult
from ..profile.models import Profile
from . import files
from .models import (
    ApplicationDetail,
    ApplicationPatch,
    ApplicationSummary,
    HistoryItem,
    SortKey,
    VersionDetail,
    VersionOut,
)


def _now() -> str:
    # Millisecond precision so two changes in the same second still sort in the order they happened.
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def posting_hash(text: str) -> str:
    """Identical postings hash the same even if whitespace or case differ."""
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().lower().encode()).hexdigest()


_SUMMARY_SQL = """
SELECT a.*,
  (SELECT COUNT(*) FROM resume_version v WHERE v.application_id = a.id) AS version_count,
  (SELECT v.number FROM resume_version v WHERE v.application_id = a.id AND v.submitted = 1 LIMIT 1)
      AS submitted_version
FROM application a
"""

_ORDER: dict[str, str] = {
    "updated": "a.updated_at DESC, a.id DESC",
    "company": "a.company COLLATE NOCASE ASC, a.id DESC",
    # Upcoming interviews first (soonest first), then everything else by recent activity.
    "interview": (
        "CASE WHEN a.interview_on IS NOT NULL AND a.interview_on >= date('now', 'localtime') THEN 0 ELSE 1 END, "
        "a.interview_on ASC, a.updated_at DESC"
    ),
}

_SEARCH_COLUMNS = ("company", "title", "location", "job_url", "notes", "posting_text")


def _summary(row: sqlite3.Row) -> ApplicationSummary:
    return ApplicationSummary(
        id=row["id"],
        company=row["company"],
        title=row["title"],
        location=row["location"],
        status=row["status"],
        match_score=row["match_score"],
        applied_on=row["applied_on"],
        interview_on=row["interview_on"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version_count=row["version_count"],
        submitted_version=row["submitted_version"],
    )


def _version(row: sqlite3.Row, folder_name: str) -> VersionOut:
    directory = files.folder_path(folder_name) / row["subdir"]
    return VersionOut(
        id=row["id"],
        number=row["number"],
        created_at=row["created_at"],
        pages=row["pages"],
        checks_passed=bool(row["checks_passed"]),
        submitted=bool(row["submitted"]),
        skills_first=bool(row["skills_first"]),
        folder=str(directory),
        docx_path=str(directory / row["docx_name"]),
        pdf_path=str(directory / row["pdf_name"]),
    )


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _detail(conn: sqlite3.Connection, app_id: int) -> ApplicationDetail | None:
    row = conn.execute(_SUMMARY_SQL + " WHERE a.id = ?", (app_id,)).fetchone()
    if row is None:
        return None
    versions = [
        _version(v, row["folder"])
        for v in conn.execute(
            "SELECT * FROM resume_version WHERE application_id = ? ORDER BY number DESC", (app_id,)
        )
    ]
    history = [
        HistoryItem(status=h["status"], changed_at=h["changed_at"])
        for h in conn.execute(
            "SELECT status, changed_at FROM status_history WHERE application_id = ? ORDER BY id", (app_id,)
        )
    ]
    analysis = None
    if row["analysis_json"]:
        try:
            analysis = AnalysisResult.model_validate_json(row["analysis_json"])
        except ValueError:
            analysis = None  # an older shape that no longer validates must not hide the application
    return ApplicationDetail(
        **_summary(row).model_dump(),
        job_url=row["job_url"],
        notes=row["notes"],
        posting_text=row["posting_text"],
        analysis=analysis,
        folder=str(files.folder_path(row["folder"])),
        versions=versions,
        history=history,
    )


# --- applications -----------------------------------------------------------------------------------


def find_by_posting(text: str) -> int | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM application WHERE posting_hash = ? ORDER BY id LIMIT 1", (posting_hash(text),)
        ).fetchone()
    return row["id"] if row else None


def create(
    *,
    company: str,
    title: str,
    location: str,
    job_url: str,
    posting_text: str,
    analysis_json: str | None,
    match_score: int | None,
    folder: str,
) -> int:
    now = _now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO application (created_at, updated_at, company, title, location, job_url, status,
                                     posting_text, posting_hash, analysis_json, match_score, folder)
            VALUES (?, ?, ?, ?, ?, ?, 'saved', ?, ?, ?, ?, ?)
            """,
            (
                now, now, company, title, location, job_url,
                posting_text, posting_hash(posting_text), analysis_json, match_score, folder,
            ),
        )  # fmt: skip
        app_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO status_history (application_id, status, changed_at) VALUES (?, 'saved', ?)", (app_id, now)
        )
    assert app_id is not None
    return app_id


def get(app_id: int) -> ApplicationDetail | None:
    with connect() as conn:
        return _detail(conn, app_id)


def search(query: str = "", status: str | None = None, sort: SortKey = "updated") -> list[ApplicationSummary]:
    clauses: list[str] = []
    params: list[Any] = []
    for term in query.split():
        clauses.append("(" + " OR ".join(f"a.{col} LIKE ? ESCAPE '\\'" for col in _SEARCH_COLUMNS) + ")")
        params += [_like(term)] * len(_SEARCH_COLUMNS)
    if status:
        clauses.append("a.status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(f"{_SUMMARY_SQL}{where} ORDER BY {_ORDER[sort]}", params).fetchall()
    return [_summary(row) for row in rows]


def update(app_id: int, patch: ApplicationPatch) -> ApplicationDetail | None:
    changes = {name: getattr(patch, name) for name in patch.model_fields_set}
    # A cleared text field is stored as "", a cleared date as NULL.
    for name in ("company", "title", "location", "job_url", "notes"):
        if name in changes and changes[name] is None:
            changes[name] = ""
    if "status" in changes and changes["status"] is None:
        del changes["status"]

    with connect() as conn:
        current = conn.execute("SELECT status FROM application WHERE id = ?", (app_id,)).fetchone()
        if current is None:
            return None
        now = _now()
        if changes:
            assignments = ", ".join(f"{name} = ?" for name in changes)
            conn.execute(
                f"UPDATE application SET {assignments}, updated_at = ? WHERE id = ?",
                [*changes.values(), now, app_id],
            )
        if "status" in changes and changes["status"] != current["status"]:
            conn.execute(
                "INSERT INTO status_history (application_id, status, changed_at) VALUES (?, ?, ?)",
                (app_id, changes["status"], now),
            )
        return _detail(conn, app_id)


def delete(app_id: int) -> str | None:
    """Removes the application and returns its folder name (or None if it did not exist)."""
    with connect() as conn:
        row = conn.execute("SELECT folder FROM application WHERE id = ?", (app_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM application WHERE id = ?", (app_id,))
    return row["folder"]


def folder_of(app_id: int) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT folder FROM application WHERE id = ?", (app_id,)).fetchone()
    return row["folder"] if row else None


# --- resume versions --------------------------------------------------------------------------------


def next_version_number(app_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 AS n FROM resume_version WHERE application_id = ?", (app_id,)
        ).fetchone()
    return row["n"]


def add_version(
    app_id: int,
    *,
    number: int,
    subdir: str,
    docx_name: str,
    pdf_name: str,
    pages: int | None,
    checks_passed: bool,
    skills_first: bool,
    profile: Profile,
) -> int:
    now = _now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO resume_version (application_id, number, created_at, subdir, docx_name, pdf_name,
                                        pages, checks_passed, skills_first, profile_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app_id, number, now, subdir, docx_name, pdf_name, pages,
                int(checks_passed), int(skills_first), profile.model_dump_json(),
            ),
        )
        conn.execute("UPDATE application SET updated_at = ? WHERE id = ?", (now, app_id))
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def get_version(app_id: int, version_id: int) -> VersionDetail | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT v.*, a.folder FROM resume_version v JOIN application a ON a.id = v.application_id "
            "WHERE v.id = ? AND v.application_id = ?",
            (version_id, app_id),
        ).fetchone()
    if row is None:
        return None
    return VersionDetail(
        **_version(row, row["folder"]).model_dump(), profile=Profile.model_validate_json(row["profile_json"])
    )


def set_submitted(app_id: int, version_id: int, submitted: bool) -> ApplicationDetail | None:
    """Marks one version as the one that was sent (only one at a time). The first submission moves a
    saved application to "applied" and records the date."""
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM resume_version WHERE id = ? AND application_id = ?", (version_id, app_id)
        ).fetchone()
        if row is None:
            return None
        now = _now()
        conn.execute("UPDATE resume_version SET submitted = 0 WHERE application_id = ?", (app_id,))
        if submitted:
            conn.execute("UPDATE resume_version SET submitted = 1 WHERE id = ?", (version_id,))
            app = conn.execute("SELECT status, applied_on FROM application WHERE id = ?", (app_id,)).fetchone()
            if app["status"] == "saved":
                conn.execute(
                    "UPDATE application SET status = 'applied' WHERE id = ?",
                    (app_id,),
                )
                conn.execute(
                    "INSERT INTO status_history (application_id, status, changed_at) VALUES (?, 'applied', ?)",
                    (app_id, now),
                )
            if not app["applied_on"]:
                conn.execute(
                    "UPDATE application SET applied_on = ? WHERE id = ?",
                    (datetime.now().astimezone().date().isoformat(), app_id),
                )
        conn.execute("UPDATE application SET updated_at = ? WHERE id = ?", (now, app_id))
        return _detail(conn, app_id)
