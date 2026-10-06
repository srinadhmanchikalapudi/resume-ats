from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..profile.models import Profile

Paper = Literal["letter", "a4"]


class ExportRequest(BaseModel):
    profile: Profile
    job_title: str = ""
    company: str = ""
    paper: Paper = "letter"
    skills_first: bool = True  # Skills before Experience (True) or after it (False)
    # When set, the files go into that application's folder as its next numbered version.
    application_id: int | None = None


class Check(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class ExportedFile(BaseModel):
    format: Literal["docx", "pdf"]
    path: str
    filename: str
    size_bytes: int
    pages: int | None = None
    checks: list[Check] = Field(default_factory=list)


class ExportResult(BaseModel):
    folder: str
    files: list[ExportedFile]
    warnings: list[str] = Field(default_factory=list)
    application_id: int | None = None
    version_id: int | None = None
    version_number: int | None = None
