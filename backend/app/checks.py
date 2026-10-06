"""The result type shared by every ATS-safety check (exported files and uploaded resumes)."""

from __future__ import annotations

from pydantic import BaseModel


class Check(BaseModel):
    name: str
    ok: bool
    detail: str = ""
