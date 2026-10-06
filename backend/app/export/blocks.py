"""The resume as an ordered list of blocks, shared by every output format so they always say the same thing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..profile.models import Profile

Kind = Literal["name", "contact", "heading", "text", "item_title", "item_meta", "bullet"]

SUMMARY = "Summary"
SKILLS = "Skills"
EXPERIENCE = "Experience"
EDUCATION = "Education"
CERTIFICATIONS = "Certifications"
PROJECTS = "Projects"
SECTION_TITLES = (SUMMARY, SKILLS, EXPERIENCE, EDUCATION, CERTIFICATIONS, PROJECTS)


@dataclass(frozen=True)
class Block:
    kind: Kind
    text: str


def _join(parts: list[str], sep: str = ", ") -> str:
    return sep.join(part for part in parts if part)


def _dates(start: str, end: str, current: bool = False) -> str:
    return " - ".join(part for part in (start, "Present" if current and not end else end) if part)


def build_blocks(profile: Profile, *, skills_first: bool = True) -> list[Block]:
    blocks: list[Block] = []
    contact = profile.contact

    if contact.name:
        blocks.append(Block("name", contact.name))
    contact_line = _join(
        [contact.email, contact.phone, contact.location, *(link.url or link.label for link in contact.links)],
        " | ",
    )
    if contact_line:
        blocks.append(Block("contact", contact_line))

    if profile.summary:
        blocks += [Block("heading", SUMMARY), Block("text", profile.summary)]

    skills = _skills_blocks(profile)
    if skills_first:
        blocks += skills
    blocks += _experience_blocks(profile)
    if not skills_first:
        blocks += skills

    blocks += _education_blocks(profile)
    blocks += _certification_blocks(profile)
    blocks += _project_blocks(profile)
    return blocks


def _skills_blocks(profile: Profile) -> list[Block]:
    groups = [g for g in profile.skills if g.items]
    if not groups:
        return []
    lines = [
        Block("text", f"{g.category}: {', '.join(g.items)}" if g.category else ", ".join(g.items)) for g in groups
    ]
    return [Block("heading", SKILLS), *lines]


def _experience_blocks(profile: Profile) -> list[Block]:
    roles = [r for r in profile.experience if r.title or r.company or r.bullets]
    if not roles:
        return []
    blocks = [Block("heading", EXPERIENCE)]
    for role in roles:
        blocks.append(Block("item_title", role.title or role.company))
        where = _join([role.company if role.title else "", role.location])
        meta = _join([where, _dates(role.start, role.end, role.current)], " | ")
        if meta:
            blocks.append(Block("item_meta", meta))
        blocks += [Block("bullet", bullet) for bullet in role.bullets]
    return blocks


def _education_blocks(profile: Profile) -> list[Block]:
    items = [e for e in profile.education if e.school or e.degree]
    if not items:
        return []
    blocks = [Block("heading", EDUCATION)]
    for edu in items:
        degree = _join([edu.degree, edu.field])
        blocks.append(Block("item_title", degree or edu.school))
        where = _join([edu.school if degree else "", edu.location])
        meta = _join([where, _dates(edu.start, edu.end)], " | ")
        if meta:
            blocks.append(Block("item_meta", meta))
        blocks += [Block("bullet", detail) for detail in edu.details]
    return blocks


def _certification_blocks(profile: Profile) -> list[Block]:
    items = [c for c in profile.certifications if c.name]
    if not items:
        return []
    lines = []
    for cert in items:
        text = _join([cert.name, cert.issuer], " - ")
        lines.append(Block("text", f"{text} ({cert.date})" if cert.date else text))
    return [Block("heading", CERTIFICATIONS), *lines]


def _project_blocks(profile: Profile) -> list[Block]:
    items = [p for p in profile.projects if p.name]
    if not items:
        return []
    blocks = [Block("heading", PROJECTS)]
    for project in items:
        blocks.append(Block("item_title", project.name))
        meta = _join([project.description, f"Technologies: {', '.join(project.tech)}" if project.tech else ""], " | ")
        if meta:
            blocks.append(Block("item_meta", meta))
        blocks += [Block("bullet", bullet) for bullet in project.bullets]
    return blocks
