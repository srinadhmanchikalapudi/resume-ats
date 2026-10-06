from __future__ import annotations

from datetime import UTC, datetime

from ..db import connect
from .models import Profile


def load_profile() -> tuple[Profile, str | None]:
    """Returns the saved profile and its last-saved timestamp, or (empty profile, None)."""
    with connect() as conn:
        row = conn.execute("SELECT data, updated_at FROM profile WHERE id = 1").fetchone()
    if row is None:
        return Profile(), None
    return Profile.model_validate_json(row["data"]), row["updated_at"]


def save_profile(profile: Profile) -> str:
    updated_at = datetime.now(UTC).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO profile (id, data, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """,
            (profile.model_dump_json(), updated_at),
        )
    return updated_at
