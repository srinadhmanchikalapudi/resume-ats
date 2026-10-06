from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..profile.models import Profile

Severity = Literal["high", "medium", "low", "info"]


class HealthRequest(BaseModel):
    profile: Profile


class Example(BaseModel):
    where: str
    text: str
    hint: str = ""


class Finding(BaseModel):
    rule: str
    severity: Severity
    title: str
    detail: str
    count: int = 1  # how many places this applies to; examples show the first few
    examples: list[Example] = Field(default_factory=list)


class CategoryScore(BaseModel):
    key: str
    label: str
    score: int
    weight: int
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class Stats(BaseModel):
    bullets: int = 0
    words: int = 0
    average_bullet_words: float = 0.0
    with_metric: int = 0
    metric_rate: float = 0.0
    strong_verb_bullets: int = 0
    weak_opener_bullets: int = 0


class HealthReport(BaseModel):
    overall: int
    band: str
    categories: list[CategoryScore]
    top_fixes: list[str] = Field(default_factory=list)
    stats: Stats
