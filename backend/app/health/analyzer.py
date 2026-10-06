"""Builds a resume health report from a Profile. Deterministic: no model calls, same input, same result."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from ..jobs.scoring import month_index
from ..profile.models import Profile
from . import rules
from .models import CategoryScore, Example, Finding, HealthReport, Severity, Stats

WEIGHTS = {"impact": 30, "verbs": 20, "clarity": 20, "specificity": 15, "completeness": 15}
LABELS = {
    "impact": "Impact and numbers",
    "verbs": "Action verbs",
    "clarity": "Clarity and length",
    "specificity": "Specificity",
    "completeness": "Completeness and consistency",
}
TARGET_METRIC_RATE = 0.4
VERB_CREDIT = {"strong": 1.0, "ok": 0.85, "weak": 0.2}
MAX_EXAMPLES = 6
LONG_BULLET_WORDS = 35
VERY_LONG_BULLET_WORDS = 45
SHORT_BULLET_WORDS = 5
REPEATED_VERB_THRESHOLD = 4
DUPLICATE_SIMILARITY = 0.7
GAP_MONTHS = 6
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}

_FULL_MONTHS = {
    "january", "february", "march", "april", "june", "july", "august", "september", "october", "november",
    "december",
}  # fmt: skip
_ABBREVIATED_MONTHS = {"jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}


@dataclass(frozen=True)
class Line:
    where: str
    text: str


def _bullets(profile: Profile) -> list[Line]:
    lines: list[Line] = []
    for role in profile.experience:
        label = " at ".join(p for p in (role.title, role.company) if p) or "A role"
        lines += [
            Line(f"{label}, bullet {i}", text)
            for i, text in enumerate(role.bullets, start=1)
            if not rules.is_tech_list(text)
        ]
    for project in profile.projects:
        label = f"Project {project.name}" if project.name else "A project"
        lines += [
            Line(f"{label}, bullet {i}", text)
            for i, text in enumerate(project.bullets, start=1)
            if not rules.is_tech_list(text)
        ]
    return lines


def _examples(lines: list[Line], hint=None) -> list[Example]:
    return [
        Example(where=line.where, text=line.text, hint=hint(line.text) if hint else "")
        for line in lines[:MAX_EXAMPLES]
    ]


def _n(count: int, noun: str = "bullet") -> str:
    """"1 bullet", "3 bullets": keeps finding titles grammatical for any count."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _band(score: int) -> str:
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Needs work"
    return "Weak"


def _category(key: str, score: float, summary: str, findings: list[Finding]) -> CategoryScore:
    findings = sorted(findings, key=lambda f: SEVERITY_RANK[f.severity])
    return CategoryScore(
        key=key,
        label=LABELS[key],
        score=max(0, min(100, round(score))),
        weight=WEIGHTS[key],
        summary=summary,
        findings=findings,
    )


# --- impact -------------------------------------------------------------------------------------


def _impact(lines: list[Line]) -> tuple[CategoryScore, list[Line]]:
    if not lines:
        return _category("impact", 0, "No bullets to assess yet.", []), []
    without = [line for line in lines if not rules.has_metric(line.text)]
    rate = (len(lines) - len(without)) / len(lines)
    findings: list[Finding] = []
    if rate < TARGET_METRIC_RATE:
        findings.append(
            Finding(
                rule="no_metric",
                severity="high" if rate < 0.25 else "medium",
                title=f"No measurable result in {len(without)} of {len(lines)} bullets",
                detail=(
                    "Employers and applicant tracking systems look for evidence of impact. Aim for a number in about "
                    "4 of every 10 bullets: counts, percentages, time or money saved, users, requests. Only use a "
                    "figure that is true. If you do not know it exactly, give an honest estimate or leave it out."
                ),
                count=len(without),
                examples=_examples(without, rules.metric_hint),
            )
        )
    summary = f"{len(lines) - len(without)} of {len(lines)} bullets contain a measurable result ({round(rate * 100)}%)."
    return _category("impact", 100 * min(1.0, rate / TARGET_METRIC_RATE), summary, findings), without


# --- verbs --------------------------------------------------------------------------------------


def _verbs(lines: list[Line]) -> tuple[CategoryScore, int, int]:
    if not lines:
        return _category("verbs", 0, "No bullets to assess yet.", []), 0, 0
    classes = [rules.verb_class(line.text) for line in lines]
    findings: list[Finding] = []

    weak_lines = [(line, rules.weak_opener(line.text)) for line, cls in zip(lines, classes, strict=True) if cls == "weak"]
    duty = [(line, why) for line, why in weak_lines if why]
    not_verb = [line for line, why in weak_lines if not why]
    if duty:
        findings.append(
            Finding(
                rule="weak_opener",
                severity="high" if len(duty) >= 3 else "medium",
                title=f"Duty-style opening in {_n(len(duty))}",
                detail="Start with a past-tense action verb that says what you did, such as Built, Reduced, Led or Migrated.",
                count=len(duty),
                examples=[Example(where=line.where, text=line.text, hint=why or "") for line, why in duty[:MAX_EXAMPLES]],
            )
        )
    if not_verb:
        findings.append(
            Finding(
                rule="not_a_verb",
                severity="low",
                title=f"No action verb at the start of {_n(len(not_verb))}",
                detail="Open each bullet with a verb in the past tense (or present tense for a current role).",
                count=len(not_verb),
                examples=_examples(not_verb),
            )
        )

    passive = [line for line in lines if rules.is_passive(line.text)]
    if passive:
        findings.append(
            Finding(
                rule="passive_voice",
                severity="medium",
                title=f"Passive voice in {_n(len(passive))}",
                detail="Make yourself the subject. Write \"Reduced costs by 20%\", not \"Costs were reduced by 20%\".",
                count=len(passive),
                examples=_examples(passive),
            )
        )

    counts = Counter(rules.opening_verb(line.text) for line in lines)
    repeated = [(verb, n) for verb, n in counts.most_common() if n >= REPEATED_VERB_THRESHOLD and verb]
    if repeated:
        findings.append(
            Finding(
                rule="repeated_verb",
                severity="low",
                title="The same opening verb is repeated many times",
                detail="Vary your verbs so the bullets do not read as a list of the same task. Try synonyms like built, "
                "delivered, shipped, designed or introduced.",
                count=len(repeated),
                examples=[Example(where=f"“{verb}” opens {n} bullets", text="") for verb, n in repeated[:MAX_EXAMPLES]],
            )
        )

    mean = sum(VERB_CREDIT[c] for c in classes) / len(classes)
    penalty = min(15, 3 * len(repeated))
    strong = classes.count("strong")
    summary = f"{strong} of {len(lines)} bullets open with a strong action verb."
    return _category("verbs", 100 * mean - penalty, summary, findings), strong, len(duty)


# --- clarity ------------------------------------------------------------------------------------


def _bullet_clarity(text: str) -> float:
    count = rules.word_count(text)
    score = 1.0
    if count > VERY_LONG_BULLET_WORDS or count < SHORT_BULLET_WORDS:
        score = 0.4
    elif count > LONG_BULLET_WORDS:
        score = 0.7
    if rules.sentence_count(text) > 1:
        score -= 0.15
    return max(0.0, score)


def _clarity(lines: list[Line]) -> CategoryScore:
    if not lines:
        return _category("clarity", 0, "No bullets to assess yet.", [])
    findings: list[Finding] = []
    long_lines = sorted((line for line in lines if rules.word_count(line.text) > LONG_BULLET_WORDS), key=lambda x: -rules.word_count(x.text))
    if long_lines:
        very = sum(rules.word_count(line.text) > VERY_LONG_BULLET_WORDS for line in long_lines)
        findings.append(
            Finding(
                rule="too_long",
                severity="high" if len(long_lines) >= len(lines) * 0.3 else "medium",
                title=f"{_n(len(long_lines))} over {LONG_BULLET_WORDS} words",
                detail="Readers skim. Keep a bullet to one or two lines: the action, then the result. Split a long bullet "
                f"into two, or cut the detail that does not change the outcome. {very} are over {VERY_LONG_BULLET_WORDS} words."
                if very
                else "Readers skim. Keep a bullet to one or two lines: the action, then the result. Split it or cut detail "
                "that does not change the outcome.",
                count=len(long_lines),
                examples=[
                    Example(where=line.where, text=line.text, hint=f"{rules.word_count(line.text)} words") for line in long_lines[:MAX_EXAMPLES]
                ],
            )
        )
    short_lines = [line for line in lines if rules.word_count(line.text) < SHORT_BULLET_WORDS]
    if short_lines:
        findings.append(
            Finding(
                rule="too_short",
                severity="low",
                title=f"{_n(len(short_lines))} under {SHORT_BULLET_WORDS} words",
                detail="Say what you did and what it achieved.",
                count=len(short_lines),
                examples=_examples(short_lines),
            )
        )
    multi = [line for line in lines if rules.sentence_count(line.text) > 1]
    if multi:
        findings.append(
            Finding(
                rule="multi_sentence",
                severity="low",
                title=f"More than one sentence in {_n(len(multi))}",
                detail="A bullet should be one idea. Split it into separate bullets.",
                count=len(multi),
                examples=_examples(multi),
            )
        )
    average = sum(rules.word_count(line.text) for line in lines) / len(lines)
    score = 100 * sum(_bullet_clarity(line.text) for line in lines) / len(lines)
    return _category("clarity", score, f"Bullets average {average:.0f} words (aim for roughly 12 to 30).", findings)


# --- specificity --------------------------------------------------------------------------------


def _specificity(profile: Profile, lines: list[Line]) -> CategoryScore:
    if not lines:
        return _category("specificity", 0, "No bullets to assess yet.", [])
    findings: list[Finding] = []
    credits: list[float] = []
    generic, fluffy = [], []
    buzz_counter: Counter[str] = Counter()
    buzz_lines: list[Line] = []
    for line in lines:
        credit = 1.0
        if rules.is_generic(line.text):
            generic.append(line)
            credit = 0.3
        fluff = rules.fluff_hits(line.text)
        if fluff:
            fluffy.append((line, fluff))
            credit -= 0.3 * len(fluff)
        buzz = rules.buzzword_hits(line.text)
        if buzz:
            buzz_counter.update(buzz)
            buzz_lines.append(line)
            credit -= 0.2 * len(buzz)
        credits.append(max(0.0, credit))

    if generic:
        findings.append(
            Finding(
                rule="generic_bullet",
                severity="medium" if len(generic) >= 3 else "low",
                title=f"Generic wording in {_n(len(generic))}",
                detail="Name the system, tool, product, customer or number involved. Specific details are what make a "
                "resume sound like a real person and what keyword searches look for.",
                count=len(generic),
                examples=_examples(generic),
            )
        )
    if fluffy:
        findings.append(
            Finding(
                rule="filler",
                severity="medium" if len(fluffy) >= 3 else "low",
                title=f"Filler words or stock phrases in {_n(len(fluffy))}",
                detail="Cut words that add nothing, such as various, successfully, etc. and phrases like team player.",
                count=len(fluffy),
                examples=[Example(where=l.where, text=l.text, hint="Cut: " + ", ".join(h)) for l, h in fluffy[:MAX_EXAMPLES]],
            )
        )
    if sum(buzz_counter.values()) >= 2:
        listed = ", ".join(f"{word} ×{n}" if n > 1 else word for word, n in buzz_counter.most_common(6))
        findings.append(
            Finding(
                rule="buzzwords",
                severity="low",
                title="Buzzwords that read as boilerplate",
                detail=f"Found: {listed}. Plain verbs (used, led, built) are clearer, and heavy use of stock words can "
                "make a resume look machine-written.",
                count=len(buzz_lines),
                examples=_examples(buzz_lines),
            )
        )

    penalty = 0.0
    summary_text = profile.summary.strip()
    if summary_text:
        summary_flags = rules.fluff_hits(summary_text) + rules.buzzword_hits(summary_text)
        if summary_flags:
            penalty += min(10, 3 * len(summary_flags))
            findings.append(
                Finding(
                    rule="summary_fluff",
                    severity="low",
                    title="The summary leans on stock phrases",
                    detail="Replace stock phrases with concrete strengths, years of experience and the technologies you use.",
                    examples=[Example(where="Summary", text=summary_text, hint="Cut: " + ", ".join(summary_flags[:5]))],
                )
            )

    pronouns = [line for line in lines if rules.first_person_hits(line.text)]
    if summary_text and rules.first_person_hits(summary_text):
        pronouns.append(Line("Summary", summary_text))
    if pronouns:
        penalty += min(10, 2 * len(pronouns))
        findings.append(
            Finding(
                rule="first_person",
                severity="low",
                title=f"First-person wording (I, my, we) in {_n(len(pronouns), 'line')}",
                detail="Resumes conventionally leave out first-person pronouns. Start with the verb instead.",
                count=len(pronouns),
                examples=_examples(pronouns),
            )
        )

    mean = sum(credits) / len(credits)
    summary = f"{len(lines) - len(generic)} of {len(lines)} bullets name something concrete (a number, tool, product or organisation)."
    return _category("specificity", 100 * mean - penalty, summary, findings)


# --- completeness and consistency ---------------------------------------------------------------


def _date_style(value: str) -> str | None:
    match = re.match(r"^([A-Za-z]+)\.?\s+\d{4}$", value.strip())
    if match:
        month = match.group(1).lower()
        if month == "may":
            return None  # May is spelled the same abbreviated or in full
        if month in _FULL_MONTHS:
            return "full month names (August 2024)"
        if month in _ABBREVIATED_MONTHS:
            return "abbreviated months (Aug 2024)"
        return None
    if re.match(r"^\d{1,2}/\d{4}$", value.strip()):
        return "numbers (08/2024)"
    if re.match(r"^\d{4}$", value.strip()):
        return "years only (2024)"
    return None


def _span(start: str, end: str, current: bool, today: datetime) -> tuple[int, int] | None:
    first = month_index(start, today.date()) if start else None
    last = month_index("present" if current else end, today.date()) if (current or end) else None
    return (first, last) if first is not None and last is not None and last >= first else None


def _month_label(index: int) -> str:
    year, month = divmod(index - 1, 12)
    return f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month]} {year}"


def _completeness(profile: Profile, lines: list[Line], today: datetime) -> CategoryScore:
    findings: list[Finding] = []
    deduction = 0.0

    def add(severity: Severity, rule: str, title: str, detail: str, points: float, **kwargs) -> None:
        nonlocal deduction
        deduction += points
        findings.append(Finding(rule=rule, severity=severity, title=title, detail=detail, **kwargs))

    contact = profile.contact
    if not contact.email.strip():
        add("high", "no_email", "No email address", "Recruiters and applicant tracking systems look for an email address first.", 25)
    if not contact.phone.strip():
        add("medium", "no_phone", "No phone number", "Add a phone number so recruiters can reach you quickly.", 10)
    if not contact.location.strip():
        add("low", "no_location", "No location", "Add your city and state (or country). Many employers filter by location.", 5)
    if not any("linkedin" in link.url.lower() or "linkedin" in link.label.lower() for link in contact.links):
        add("info", "no_linkedin", "No LinkedIn link", "Most recruiters check LinkedIn. Add your profile link if you have one.", 2)
    if not profile.summary.strip():
        add("low", "no_summary", "No summary", "A two- or three-sentence summary helps a reader see the fit in seconds.", 8)
    elif (n := rules.word_count(profile.summary)) > 90:
        add("low", "long_summary", f"The summary is {n} words", "Keep it to two or three sentences, about 30 to 70 words.", 5)
    if not any(group.items for group in profile.skills):
        add("medium", "no_skills", "No skills section", "List your technical skills so keyword searches can find them.", 12)
    elif (total := sum(len(g.items) for g in profile.skills)) > 60:
        add("low", "long_skills", f"The skills list has {total} items", "Long lists dilute the ones that matter. Keep the skills you would be comfortable being asked about.", 3)
    if not profile.experience:
        add("high", "no_experience", "No work experience", "Add your roles with bullets describing what you achieved.", 30)

    # Dates
    spans = []
    undated = []
    # Style is compared among job dates, and separately among education dates, because writing only the year for a
    # degree while using months for jobs is normal.
    styles: dict[str, str] = {}
    education_styles: dict[str, str] = {}
    for role in profile.experience:
        label = " at ".join(p for p in (role.title, role.company) if p) or "A role"
        if not role.start.strip():
            undated.append(label)
        for value in (role.start, role.end):
            style = _date_style(value) if value.strip() else None
            if style:
                styles.setdefault(style, value)
        span = _span(role.start, role.end, role.current, today)
        if span:
            spans.append((span, label))
    for edu in profile.education:
        for value in (edu.start, edu.end):
            style = _date_style(value) if value.strip() else None
            if style:
                education_styles.setdefault(style, value)
    mixed_styles = styles if len(styles) > 1 else education_styles if len(education_styles) > 1 else {}
    if undated:
        add("high", "undated_role", f"Start date missing on {_n(len(undated), 'role')}", "Applicant tracking systems and recruiters need dates to understand your timeline.", 15, count=len(undated), examples=[Example(where=u, text="") for u in undated[:MAX_EXAMPLES]])
    if mixed_styles:
        add("low", "date_style", "Dates are written in different styles", "Pick one style and use it everywhere.", 5, count=len(mixed_styles), examples=[Example(where=style, text=f"for example {value}") for style, value in mixed_styles.items()])

    starts = [month_index(r.start, today.date()) for r in profile.experience if r.start.strip()]
    starts = [s for s in starts if s is not None]
    if any(a < b for a, b in pairwise(starts)):
        add("low", "not_reverse_chronological", "Roles are not newest first", "List your most recent role first.", 5)

    education_spans = [s for s in (_span(e.start, e.end, False, today) for e in profile.education) if s]
    gaps = []
    ordered = sorted(spans, key=lambda item: item[0][0])
    for (prev_span, prev_label), (next_span, next_label) in pairwise(ordered):
        gap_start, gap_end = prev_span[1], next_span[0]
        months = gap_end - gap_start
        if months < GAP_MONTHS:
            continue
        covered = sum(max(0, min(gap_end, e1) - max(gap_start, e0)) for e0, e1 in education_spans)
        if covered >= 0.6 * months:
            continue  # the time is explained by education
        gaps.append(Example(where=f"{_month_label(gap_start)} to {_month_label(gap_end)} ({months} months)", text=f"Between {prev_label} and {next_label}"))
    if gaps:
        add("info", "employment_gap", f"{_n(len(gaps), 'gap')} of {GAP_MONTHS}+ months between roles", "Gaps are normal, but readers notice them. If something filled the time (study, caregiving, freelancing, a career break), a short line explains it.", 3 * min(3, len(gaps)), count=len(gaps), examples=gaps[:MAX_EXAMPLES])

    # Duplicate content
    pairs = []
    for i, first in enumerate(lines):
        for second in lines[i + 1 :]:
            if rules.similarity(first.text, second.text) >= DUPLICATE_SIMILARITY:
                pairs.append((first, second))
    if pairs:
        add("medium", "duplicate_bullets", f"{_n(len(pairs), 'pair')} of near-duplicate bullets", "Repeating the same point in different words wastes space. Keep the stronger bullet.", min(15, 5 * len(pairs)), count=len(pairs), examples=[Example(where=f"{a.where} and {b.where}", text=a.text) for a, b in pairs[:MAX_EXAMPLES]])

    words_total = sum(rules.word_count(line.text) for line in lines) + rules.word_count(profile.summary)
    if words_total > 1000:
        add("low", "long_resume", f"About {words_total} words of content", "That is likely more than two pages. Use the Concise or Standard length when tailoring, or trim older roles.", 3)

    score = 100 - deduction
    summary = "Contact details, dates and structure look complete and consistent." if not findings else f"{len(findings)} thing{'s' if len(findings) != 1 else ''} to check."
    return _category("completeness", score, summary, findings)


# --- assembly -----------------------------------------------------------------------------------


def analyze(profile: Profile, today: datetime | None = None) -> HealthReport:
    today = today or datetime.now().astimezone()
    lines = _bullets(profile)

    impact, _ = _impact(lines)
    verbs, strong, weak_openers = _verbs(lines)
    categories = [
        impact,
        verbs,
        _clarity(lines),
        _specificity(profile, lines),
        _completeness(profile, lines, today),
    ]
    overall = round(sum(c.score * c.weight for c in categories) / sum(WEIGHTS.values()))

    words_total = sum(rules.word_count(line.text) for line in lines)
    with_metric = sum(rules.has_metric(line.text) for line in lines)
    stats = Stats(
        bullets=len(lines),
        words=words_total + rules.word_count(profile.summary),
        average_bullet_words=round(words_total / len(lines), 1) if lines else 0.0,
        with_metric=with_metric,
        metric_rate=round(with_metric / len(lines), 2) if lines else 0.0,
        strong_verb_bullets=strong,
        weak_opener_bullets=weak_openers,
    )

    ranked = sorted(
        ((f, c) for c in categories for f in c.findings if f.severity in {"high", "medium"}),
        key=lambda pair: (SEVERITY_RANK[pair[0].severity], -pair[1].weight),
    )
    return HealthReport(
        overall=overall,
        band=_band(overall),
        categories=categories,
        top_fixes=[finding.title for finding, _ in ranked[:5]],
        stats=stats,
    )
