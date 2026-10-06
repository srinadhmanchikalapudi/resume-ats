"""Job postings, requirement matching and the resulting analysis."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from ..lenient import Lenient, OptionalInt, Text, TextList, as_list

Category = Literal["skill", "tool", "experience", "education", "certification", "domain", "soft", "other"]
Importance = Literal["required", "preferred", "nice"]
MatchStatus = Literal["matched", "partial", "missing", "unverified"]

_CATEGORIES = set(Category.__args__)  # type: ignore[attr-defined]
_REQUIRED_WORDS = {"required", "must", "must-have", "must have", "mandatory", "minimum", "essential"}
_NICE_WORDS = {"nice", "nice-to-have", "nice to have", "bonus", "plus", "optional"}


def _category(value: object) -> str:
    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in _CATEGORIES else "other"


def _importance(value: object) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in _REQUIRED_WORDS:
        return "required"
    if cleaned in _NICE_WORDS:
        return "nice"
    return "preferred"  # includes unlabeled or unrecognised values: the middle weight


def _status(value: object) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in {"matched", "match", "yes", "met"}:
        return "matched"
    if cleaned in {"partial", "partially", "weak", "related"}:
        return "partial"
    return "missing"


# --- extracted from the posting ---------------------------------------------------------------


class Requirement(Lenient):
    id: Text = ""
    text: Text = ""
    category: Annotated[Category, BeforeValidator(_category)] = "other"
    importance: Annotated[Importance, BeforeValidator(_importance)] = "preferred"
    keywords: TextList = Field(default_factory=list)


class JobAnalysis(Lenient):
    title: Text = ""
    company: Text = ""
    location: Text = ""
    work_mode: Text = ""
    seniority: Text = ""
    years_required: OptionalInt = None
    summary: Text = ""
    requirements: Annotated[list[Requirement], BeforeValidator(as_list)] = Field(default_factory=list)
    responsibilities: TextList = Field(default_factory=list)
    keywords: TextList = Field(default_factory=list)

    @model_validator(mode="after")
    def _number_requirements(self) -> JobAnalysis:
        self.requirements = [r for r in self.requirements if r.text]
        for index, requirement in enumerate(self.requirements, start=1):
            requirement.id = f"r{index}"
        return self


# --- the model's matching verdicts (untrusted until verified) -----------------------------------


class EvidenceIn(Lenient):
    ref: Text = ""
    quote: Text = ""


class MatchItemIn(Lenient):
    requirement_id: Text = ""
    status: Annotated[Literal["matched", "partial", "missing"], BeforeValidator(_status)] = "missing"
    evidence: Annotated[list[EvidenceIn], BeforeValidator(as_list)] = Field(default_factory=list)
    note: Text = ""


class MatchIn(Lenient):
    matches: Annotated[list[MatchItemIn], BeforeValidator(as_list)] = Field(default_factory=list)


# --- the verified result sent to the UI --------------------------------------------------------


class Evidence(BaseModel):
    ref: str
    label: str
    quote: str


class RequirementMatch(BaseModel):
    requirement: Requirement
    status: MatchStatus
    evidence: list[Evidence] = Field(default_factory=list)
    note: str = ""


class KeywordCheck(BaseModel):
    present: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class Scores(BaseModel):
    overall: int | None = None
    required_total: int = 0
    required_matched: int = 0
    required_partial: int = 0
    required_missing: int = 0
    candidate_years: float | None = None
    years_required: int | None = None
    years_short_by: float | None = None


class AnalysisResult(BaseModel):
    job: JobAnalysis
    matches: list[RequirementMatch]
    keywords: KeywordCheck
    scores: Scores
    warnings: list[str] = Field(default_factory=list)


class AnalyzeIn(BaseModel):
    text: str
