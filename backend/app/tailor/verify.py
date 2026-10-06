"""Turns the model's reply into a TailoredResume the user can trust.

The model proposes; this module disposes. Every output bullet must trace to an original bullet, rewrites
that add numbers or keywords the profile does not support are reverted, and skills come only from the profile.
"""

from __future__ import annotations

import re

from ..jobs.models import AnalysisResult
from ..jobs.scoring import has_term, job_terms
from ..profile.models import Profile
from .models import (
    DroppedBullet,
    Flag,
    Length,
    SkillGroup,
    TailoredBullet,
    TailoredResume,
    TailoredRole,
    TailoredSummary,
    TailorReply,
)
from .prompt import role_caps

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MAX_SUMMARY_WORDS = 90


def numbers(text: str) -> set[str]:
    return {m.group().replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


def profile_text(profile: Profile) -> str:
    parts = [profile.summary]
    for role in profile.experience:
        parts += [role.title, role.company, role.start, role.end, *role.bullets]
    for edu in profile.education:
        parts += [edu.school, edu.degree, edu.field, edu.start, edu.end, *edu.details]
    for group in profile.skills:
        parts += [group.category, *group.items]
    parts += [c.name + " " + c.issuer + " " + c.date for c in profile.certifications]
    for project in profile.projects:
        parts += [project.name, project.description, *project.tech, *project.bullets]
    return "\n".join(part for part in parts if part)


def supported_terms(analysis: AnalysisResult) -> set[str]:
    """Keywords of requirements whose match was verified against the profile (lower case)."""
    return {k.lower() for m in analysis.matches if m.status == "matched" for k in m.requirement.keywords}


def check_rewrite(
    original: str, proposed: str, *, vocab: list[str], context: str, supported: set[str]
) -> list[Flag]:
    """Problems with a reworded bullet. A "reverted" flag means the rewrite must not be used."""
    flags: list[Flag] = []

    added_numbers = numbers(proposed) - numbers(original)
    if added_numbers:
        flags.append(
            Flag(kind="reverted", message=f"Adds number(s) not in the original: {', '.join(sorted(added_numbers))}.")
        )

    for term in vocab:
        if has_term(term, proposed) and not has_term(term, original):
            if has_term(term, context):
                flags.append(
                    Flag(
                        kind="review",
                        message=f"Adds '{term}', which is elsewhere in your profile but not in this bullet. "
                        "Check it is true for this role.",
                    )
                )
            elif term.lower() in supported:
                flags.append(
                    Flag(
                        kind="review",
                        message=f"Adds '{term}'. Your profile never uses these exact words, but the match "
                        "check found evidence for this requirement. Use it only if the wording is accurate.",
                    )
                )
            else:
                flags.append(
                    Flag(kind="reverted", message=f"Adds '{term}', which is not anywhere in your profile.")
                )

    if len(proposed.split()) > max(40, int(len(original.split()) * 1.6)):
        flags.append(Flag(kind="review", message="Much longer than the original."))
    return flags


def build_resume(profile: Profile, analysis: AnalysisResult, reply: TailorReply, length: Length) -> TailoredResume:
    vocab = job_terms(analysis.job)
    context = profile_text(profile)
    supported = supported_terms(analysis)
    caps = role_caps(profile, length)
    warnings: list[str] = []
    replies = {role.ref: role for role in reply.roles}

    roles: list[TailoredRole] = []
    reverted = 0
    for i, role in enumerate(profile.experience):
        proposal = replies.get(f"exp{i + 1}")
        chosen: list[TailoredBullet] = []
        used: set[int] = set()

        for item in proposal.bullets if proposal else []:
            index = item.source
            if index is None or not 1 <= index <= len(role.bullets) or index in used:
                continue  # not a real, unused original bullet: ignore it
            if len(chosen) >= caps[i]:
                break
            original = role.bullets[index - 1]
            proposed = item.text.strip() or original
            flags = (
                check_rewrite(original, proposed, vocab=vocab, context=context, supported=supported)
                if proposed != original
                else []
            )
            if any(f.kind == "reverted" for f in flags):
                reverted += 1
                proposed = original
            used.add(index)
            chosen.append(TailoredBullet(source=index, original=original, proposed=proposed, flags=flags))

        if not chosen and role.bullets:
            label = role.title or f"role {i + 1}"
            warnings.append(f"The model returned no usable bullets for {label}; showing your first originals.")
            for n, original in enumerate(role.bullets[: caps[i]], start=1):
                used.add(n)
                chosen.append(TailoredBullet(source=n, original=original, proposed=original))

        roles.append(
            TailoredRole(
                id=role.id,
                title=role.title,
                company=role.company,
                location=role.location,
                start=role.start,
                end=role.end,
                current=role.current,
                bullets=chosen,
                dropped=[
                    DroppedBullet(source=n, original=text)
                    for n, text in enumerate(role.bullets, start=1)
                    if n not in used
                ],
            )
        )

    if reverted:
        warnings.append(
            f"{reverted} rewrite(s) were reverted to your original wording because they added facts "
            "your profile does not support."
        )

    return TailoredResume(
        contact=profile.contact,
        summary=_summary(profile, reply, vocab, context, supported, warnings),
        roles=roles,
        skills=_skills(profile, reply, warnings),
        education=profile.education,
        certifications=profile.certifications,
        projects=profile.projects,
        warnings=warnings,
    )


def _summary(
    profile: Profile, reply: TailorReply, vocab: list[str], context: str, supported: set[str], warnings: list[str]
) -> TailoredSummary:
    original, proposed = profile.summary, reply.summary.strip()
    if not proposed:
        return TailoredSummary(original=original, proposed=original)

    flags: list[Flag] = []
    unsupported_numbers = numbers(proposed) - numbers(context)
    absent = [t for t in vocab if has_term(t, proposed) and not has_term(t, context)]
    unsupported_terms = [t for t in absent if t.lower() not in supported]
    reworded_terms = [t for t in absent if t.lower() in supported]
    if unsupported_numbers:
        flags.append(
            Flag(kind="reverted", message=f"Mentions number(s) not in your profile: {', '.join(sorted(unsupported_numbers))}.")
        )
    if unsupported_terms:
        flags.append(
            Flag(kind="reverted", message=f"Mentions {', '.join(unsupported_terms)}, which is not in your profile.")
        )
    if reworded_terms:
        flags.append(
            Flag(
                kind="review",
                message=f"Uses {', '.join(reworded_terms)}, wording your profile does not use but whose requirement "
                "the match check verified. Keep it only if accurate.",
            )
        )
    if any(f.kind == "reverted" for f in flags):
        warnings.append("The proposed summary claimed things your profile does not support, so your original is kept.")
        return TailoredSummary(original=original, proposed=original, flags=flags)

    if len(proposed.split()) > MAX_SUMMARY_WORDS:
        flags.append(Flag(kind="review", message="Longer than a typical summary."))
    return TailoredSummary(original=original, proposed=proposed, flags=flags)


def _skills(profile: Profile, reply: TailorReply, warnings: list[str]) -> list[SkillGroup]:
    known = {item.lower().strip(): item for group in profile.skills for item in group.items}
    categories = {group.category.lower().strip(): group.category for group in profile.skills if group.category}

    result: list[SkillGroup] = []
    dropped = 0
    taken: set[str] = set()
    for group in reply.skills:
        items = []
        for raw in group.items:
            key = raw.lower().strip()
            if key not in known:
                dropped += 1
            elif key not in taken:
                taken.add(key)
                items.append(known[key])
        if items:
            category = categories.get(group.category.lower().strip(), group.category) or "Skills"
            result.append(SkillGroup(category=category, items=items))

    if dropped:
        warnings.append(f"{dropped} skill(s) suggested by the model are not in your profile and were removed.")
    if not result:
        return [group.model_copy(deep=True) for group in profile.skills]
    return result
