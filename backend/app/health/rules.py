"""Pure, individually testable checks on a single line of resume text."""

from __future__ import annotations

import re
from typing import Literal

from .lexicon import (
    FIRST_PERSON,
    FLUFF_PHRASES,
    GENERIC_BUZZWORDS,
    GENERIC_METRIC_HINT,
    IRREGULAR_PAST,
    METRIC_HINTS,
    METRIC_UNITS,
    NUMBER_WORDS,
    STOPWORDS,
    STRONG_FORMS,
    TECH_LIST_PREFIXES,
    VERSION_WORDS,
    WEAK_OPENERS,
)

VerbClass = Literal["strong", "ok", "weak"]

_WORD = re.compile(r"[A-Za-z0-9#+.'/-]+")
_PERCENT = re.compile(r"\d[\d,.]*\s?%")
_MONEY = re.compile(r"[$€£]\s?\d")
_MULTIPLIER = re.compile(r"\b\d+(?:\.\d+)?\s?[xX]\b")
_NUMBER_THEN_UNIT = re.compile(
    r"(?<![\w./])(\d[\d,]*(?:\.\d+)?[kKmMbB]?\+?)\s+(?:[A-Za-z-]+\s+){0,2}?(" + "|".join(METRIC_UNITS) + r")\b",
    re.IGNORECASE,
)
# "2,000 analysts", "40 reviewers": a number directly followed by a plural noun is a count. Words ending in
# ss, us or is (access, status, analysis) are not plurals.
_NUMBER_THEN_PLURAL = re.compile(
    r"(?<![\w./-])(\d[\d,]*)\+?\s+(?:[A-Za-z-]+\s+){0,2}?(?!\w*(?:ss|us|is)\b)[A-Za-z]{3,}s\b"
)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_SPELLED = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\s+[A-Za-z]", re.IGNORECASE)
_FROM_TO = re.compile(r"\bfrom\s+\S+\s+to\s+\S+", re.IGNORECASE)
_RELATIVE = re.compile(r"\b(?:by half|halved|doubled|tripled|quadrupled|twice as|half the)\b", re.IGNORECASE)
_PASSIVE = re.compile(r"\b(?:was|were|been|being|is|are|be)\s+(?:\w+ly\s+)?(\w+(?:ed|en))\b", re.IGNORECASE)
_PASSIVE_NOT = {"based", "needed", "named", "stored", "open", "given", "seen", "loaded"}
_SENTENCE_BREAK = re.compile(r"[.!?]\s+[A-Z]")
_SPECIFIC_TOKEN = re.compile(r"^(?:[A-Z][A-Za-z0-9]*[A-Z0-9#+.][A-Za-z0-9#+.]*|[A-Za-z0-9]*[#+.\d][A-Za-z0-9#+.]*)$")


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def word_count(text: str) -> int:
    return len(text.split())


def first_word(text: str) -> str:
    found = words(text)
    return found[0].lower().strip(".,;:") if found else ""


def _version_context(text: str, start: int) -> bool:
    """Whether the number at `start` is a version number, judged by the word just before it."""
    before = text[:start].rstrip().split()
    return bool(before) and before[-1].lower().strip(",;:()") in VERSION_WORDS


def has_metric(text: str) -> bool:
    """Whether the line contains a real quantity: a percentage, money, multiplier, counted thing or before-and-after."""
    if (
        _PERCENT.search(text)
        or _MONEY.search(text)
        or _MULTIPLIER.search(text)
        or _FROM_TO.search(text)
        or _RELATIVE.search(text)
    ):
        return True
    for match in _NUMBER_THEN_UNIT.finditer(text):
        if not _version_context(text, match.start(1)):
            return True
    for match in _NUMBER_THEN_PLURAL.finditer(text):
        number = match.group(1)
        if not _YEAR.match(number) and not _version_context(text, match.start(1)):
            return True
    return _SPELLED.search(text) is not None


def is_tech_list(text: str) -> bool:
    """A line such as "Environment: C#, .NET, SQL Server" that lists technologies rather than describing an achievement."""
    head, sep, _ = text.partition(":")
    return bool(sep) and head.strip().lower() in TECH_LIST_PREFIXES


def metric_hint(text: str) -> str:
    base = STRONG_FORMS.get(first_word(text))
    return METRIC_HINTS.get(base or "", GENERIC_METRIC_HINT)


def opening_verb(text: str) -> str:
    """The base form of the verb a bullet opens with, or the lower-cased first word if it is not a known verb."""
    word = first_word(text)
    return STRONG_FORMS.get(word, word)


def weak_opener(text: str) -> str | None:
    """Why a bullet opens weakly, or None."""
    lowered = text.strip().lower()
    for phrase, reason in WEAK_OPENERS:
        if lowered.startswith(phrase):
            return reason
    return None


def verb_class(text: str) -> VerbClass:
    """strong: a recognised accomplishment verb. ok: some other past-tense verb. weak: a duty, noun or gerund opener."""
    if weak_opener(text):
        return "weak"
    word = first_word(text)
    if word.endswith("ing"):
        return "weak"  # "Developing..." reads as an ongoing duty, not an achievement
    if word in STRONG_FORMS:
        return "strong"
    if (word.endswith("ed") and len(word) > 3) or word in IRREGULAR_PAST:
        return "ok"
    return "weak"


def is_passive(text: str) -> bool:
    return any(m.group(1).lower() not in _PASSIVE_NOT for m in _PASSIVE.finditer(text))


def sentence_count(text: str) -> int:
    return 1 + len(_SENTENCE_BREAK.findall(text))


def _contains_phrase(lowered: str, phrase: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", lowered) is not None


def fluff_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in FLUFF_PHRASES if _contains_phrase(lowered, phrase)]


def buzzword_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in GENERIC_BUZZWORDS if _contains_phrase(lowered, word)]


def first_person_hits(text: str) -> list[str]:
    return [w for w in words(text) if w.strip("'.,").lower() in FIRST_PERSON]


def specific_tokens(text: str) -> list[str]:
    """Names, products, technologies and numbers: tokens that make a line concrete rather than generic."""
    tokens = [t.strip(".,;:()") for t in text.split()[1:]]
    return [t for t in tokens if t and (_SPECIFIC_TOKEN.match(t) or (t[0].isupper() and len(t) > 1))]


def is_generic(text: str) -> bool:
    """No numbers and no named technology, product or organisation: could describe almost anyone's job."""
    return not has_metric(text) and not re.search(r"\d", text) and not specific_tokens(text)


def content_words(text: str) -> set[str]:
    cleaned = (w.lower().strip(".,;:'-/") for w in words(text))
    return {w for w in cleaned if len(w) > 2 and w not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    """Jaccard overlap of meaningful words, 0 to 1."""
    left, right = content_words(a), content_words(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
