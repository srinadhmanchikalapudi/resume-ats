"""Tailoring: a job-specific selection and rewording of the master profile."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from ..jobs.models import AnalysisResult
from ..lenient import Lenient, OptionalInt, Text, as_list
from ..profile.models import Certification, Contact, Education, Project, SkillGroup

Length = Literal["concise", "standard", "full"]


# --- the model's reply (untrusted until verified) ----------------------------------------------


class BulletIn(Lenient):
    source: OptionalInt = None  # 1-based number of the original bullet within its role
    text: Text = ""


class RoleIn(Lenient):
    ref: Text = ""
    bullets: Annotated[list[BulletIn], BeforeValidator(as_list)] = Field(default_factory=list)


class TailorReply(Lenient):
    summary: Text = ""
    roles: Annotated[list[RoleIn], BeforeValidator(as_list)] = Field(default_factory=list)
    skills: Annotated[list[SkillGroup], BeforeValidator(as_list)] = Field(default_factory=list)


# --- the verified result sent to the UI --------------------------------------------------------


class Flag(BaseModel):
    kind: Literal["reverted", "review"]
    message: str


class TailoredBullet(BaseModel):
    source: int  # 1-based position of the original bullet in the profile role
    original: str
    proposed: str  # equals `original` when unchanged or when a rewrite was reverted
    flags: list[Flag] = Field(default_factory=list)


class DroppedBullet(BaseModel):
    source: int
    original: str


class TailoredRole(BaseModel):
    id: str
    title: str
    company: str
    location: str
    start: str
    end: str
    current: bool
    bullets: list[TailoredBullet]
    dropped: list[DroppedBullet] = Field(default_factory=list)


class TailoredSummary(BaseModel):
    original: str
    proposed: str
    flags: list[Flag] = Field(default_factory=list)


class TailoredResume(BaseModel):
    contact: Contact
    summary: TailoredSummary
    roles: list[TailoredRole]
    skills: list[SkillGroup]
    education: list[Education]
    certifications: list[Certification]
    projects: list[Project]
    warnings: list[str] = Field(default_factory=list)


class TailorRequest(BaseModel):
    analysis: AnalysisResult
    length: Length = "standard"
