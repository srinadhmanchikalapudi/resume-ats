"""The application archive: one record per job, with its resume versions and status timeline."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..jobs.models import AnalysisResult
from ..profile.models import Profile

Status = Literal["saved", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn"]
STATUSES: tuple[str, ...] = (
    "saved", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn",
)  # fmt: skip
SortKey = Literal["updated", "interview", "company"]

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_date(value: str | None) -> str | None:
    """A YYYY-MM-DD string, or None to clear. Anything else is rejected."""
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if not _ISO_DATE.match(value):
        raise ValueError("Dates must look like 2026-10-31.")
    return value


class ApplicationCreate(BaseModel):
    posting_text: str
    analysis: AnalysisResult | None = None
    company: str = ""
    title: str = ""
    location: str = ""
    job_url: str = ""


class ApplicationPatch(BaseModel):
    """Only the fields present in the request are changed; a date set to "" is cleared."""

    company: str | None = None
    title: str | None = None
    location: str | None = None
    job_url: str | None = None
    status: Status | None = None
    applied_on: str | None = None
    interview_on: str | None = None
    notes: str | None = None

    @field_validator("applied_on", "interview_on")
    @classmethod
    def _dates(cls, value: str | None) -> str | None:
        return _clean_date(value)


class VersionOut(BaseModel):
    id: int
    number: int
    created_at: str
    pages: int | None = None
    checks_passed: bool = True
    submitted: bool = False
    skills_first: bool = True  # section order used in the exported files
    folder: str  # absolute folder holding this version's files
    docx_path: str
    pdf_path: str


class VersionDetail(VersionOut):
    profile: Profile


class HistoryItem(BaseModel):
    status: Status
    changed_at: str


class ApplicationSummary(BaseModel):
    id: int
    company: str
    title: str
    location: str
    status: Status
    match_score: int | None = None
    applied_on: str | None = None
    interview_on: str | None = None
    created_at: str
    updated_at: str
    version_count: int = 0
    submitted_version: int | None = None  # number of the version marked as submitted


class ApplicationDetail(ApplicationSummary):
    job_url: str
    notes: str
    posting_text: str
    analysis: AnalysisResult | None = None
    folder: str
    versions: list[VersionOut] = Field(default_factory=list)
    history: list[HistoryItem] = Field(default_factory=list)


class ApplicationCreated(ApplicationDetail):
    already_saved: bool = False  # the identical posting was saved before, so this is the existing record
