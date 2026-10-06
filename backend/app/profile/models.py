"""The master profile: structured source of truth for a person's career."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ..checks import Check
from ..lenient import Lenient as _Lenient
from ..lenient import Text, TextList
from ..lenient import as_list as _list


def _new_id() -> str:
    return uuid.uuid4().hex


class Link(_Lenient):
    label: Text = ""
    url: Text = ""


class Contact(_Lenient):
    name: Text = ""
    email: Text = ""
    phone: Text = ""
    location: Text = ""
    links: Annotated[list[Link], BeforeValidator(_list)] = Field(default_factory=list)


class Experience(_Lenient):
    id: Text = Field(default_factory=_new_id)
    title: Text = ""
    company: Text = ""
    location: Text = ""
    start: Text = ""
    end: Text = ""
    current: bool = False
    bullets: TextList = Field(default_factory=list)

    @model_validator(mode="after")
    def _current_role_has_no_end_date(self) -> Experience:
        # Models sometimes return both "current": true and an end date; the flag wins.
        if self.current:
            self.end = ""
        return self


class Education(_Lenient):
    id: Text = Field(default_factory=_new_id)
    school: Text = ""
    degree: Text = ""
    field: Text = ""
    location: Text = ""
    start: Text = ""
    end: Text = ""
    details: TextList = Field(default_factory=list)


class SkillGroup(_Lenient):
    category: Text = ""
    items: TextList = Field(default_factory=list)


class Certification(_Lenient):
    id: Text = Field(default_factory=_new_id)
    name: Text = ""
    issuer: Text = ""
    date: Text = ""


class Project(_Lenient):
    id: Text = Field(default_factory=_new_id)
    name: Text = ""
    description: Text = ""
    url: Text = ""
    tech: TextList = Field(default_factory=list)
    bullets: TextList = Field(default_factory=list)


class Profile(_Lenient):
    contact: Contact = Field(default_factory=Contact)
    summary: Text = ""
    experience: Annotated[list[Experience], BeforeValidator(_list)] = Field(default_factory=list)
    education: Annotated[list[Education], BeforeValidator(_list)] = Field(default_factory=list)
    skills: Annotated[list[SkillGroup], BeforeValidator(_list)] = Field(default_factory=list)
    certifications: Annotated[list[Certification], BeforeValidator(_list)] = Field(default_factory=list)
    projects: Annotated[list[Project], BeforeValidator(_list)] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return self == Profile()


class ProfileOut(BaseModel):
    profile: Profile
    exists: bool
    updated_at: str | None = None


class ImportResult(BaseModel):
    profile: Profile
    warnings: list[str] = Field(default_factory=list)
    # How readable the uploaded file itself is for applicant tracking systems (empty for pasted text).
    file_checks: list[Check] = Field(default_factory=list)


class ImportTextIn(BaseModel):
    text: str
