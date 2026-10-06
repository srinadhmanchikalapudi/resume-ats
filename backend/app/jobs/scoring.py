"""Deterministic numbers: the model judges matches, code does the arithmetic."""

from __future__ import annotations

import re
from datetime import date, datetime

from ..profile.models import Profile
from .models import Importance, JobAnalysis, KeywordCheck, MatchStatus, RequirementMatch, Scores

IMPORTANCE_WEIGHT: dict[Importance, float] = {"required": 3.0, "preferred": 1.5, "nice": 0.5}
STATUS_CREDIT: dict[MatchStatus, float] = {"matched": 1.0, "partial": 0.5, "missing": 0.0, "unverified": 0.0}

MAX_KEYWORDS = 40

_MONTHS = {
    name: index
    for index, name in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
_PRESENT = {"present", "current", "now", "today", "ongoing"}


# --- years of experience ------------------------------------------------------------------------


def _month_index(text: str, today: date) -> int | None:
    """Months since year 0 for strings like "Jan 2020", "June 2018", "2016", "03/2021"; else None."""
    cleaned = text.strip().lower()
    if not cleaned:
        return None
    if cleaned in _PRESENT:
        return today.year * 12 + today.month
    slash = re.search(r"\b(\d{1,2})\s*/\s*(\d{4})\b", cleaned)
    if slash:
        return int(slash.group(2)) * 12 + min(max(int(slash.group(1)), 1), 12)
    year = re.search(r"\b(19|20)\d{2}\b", cleaned)
    if not year:
        return None
    month = 1
    named = re.search(r"\b([a-z]{3})[a-z]*\b", cleaned[: year.start()])
    if named and named.group(1) in _MONTHS:
        month = _MONTHS[named.group(1)]
    return int(year.group()) * 12 + month


def candidate_years(profile: Profile, today: date | None = None) -> float | None:
    """Total time covered by the profile's roles, counting overlapping roles once. None if undatable."""
    today = today or datetime.now().astimezone().date()
    spans: list[tuple[int, int]] = []
    for role in profile.experience:
        start = _month_index(role.start, today)
        end = _month_index("present" if role.current else role.end, today)
        if start is not None and end is not None and end >= start:
            spans.append((start, end))
    if not spans:
        return None

    spans.sort()
    total, (cur_start, cur_end) = 0, spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return round(total / 12, 1)


# --- scoring ------------------------------------------------------------------------------------


def compute_scores(job: JobAnalysis, matches: list[RequirementMatch], years: float | None) -> Scores:
    weighted = sum(IMPORTANCE_WEIGHT[m.requirement.importance] * STATUS_CREDIT[m.status] for m in matches)
    possible = sum(IMPORTANCE_WEIGHT[m.requirement.importance] for m in matches)

    required = [m for m in matches if m.requirement.importance == "required"]
    short_by = None
    if job.years_required is not None and years is not None and years < job.years_required:
        short_by = round(job.years_required - years, 1)

    return Scores(
        overall=round(100 * weighted / possible) if possible else None,
        required_total=len(required),
        required_matched=sum(m.status == "matched" for m in required),
        required_partial=sum(m.status == "partial" for m in required),
        required_missing=sum(m.status in {"missing", "unverified"} for m in required),
        candidate_years=years,
        years_required=job.years_required,
        years_short_by=short_by,
    )


# --- literal keyword check ----------------------------------------------------------------------


def clean_term(term: str) -> str:
    """Drops parenthetical asides ("Angular (v12+)" -> "Angular") and extra spacing."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", term)).strip(" ,;:")


def _unique(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for raw in terms:
        term = clean_term(raw)
        key = term.lower()
        # Long strings are descriptions, not keywords, so a literal search for them is meaningless.
        if key and key not in seen and len(term) <= 40 and len(term.split()) <= 4:
            seen.add(key)
            result.append(term)
    return result


def check_keywords(job: JobAnalysis, profile_text: str) -> KeywordCheck:
    """Which of the posting's terms appear, as written, in the profile (what a keyword filter sees)."""
    terms = _unique([*job.keywords, *(k for r in job.requirements for k in r.keywords)])[:MAX_KEYWORDS]
    present, missing = [], []
    for term in terms:
        # Lookarounds instead of \b so terms like "C#", ".NET" and "Node.js" match correctly.
        # An optional trailing "s" lets "Azure App Service" match "Azure App Services".
        pattern = rf"(?<![\w]){re.escape(term)}s?(?![\w])"
        (present if re.search(pattern, profile_text, flags=re.IGNORECASE) else missing).append(term)
    return KeywordCheck(present=present, missing=missing)
