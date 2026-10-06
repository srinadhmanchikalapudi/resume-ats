"""A citable view of the profile: the model quotes from it and the server verifies the quotes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..profile.models import Profile


@dataclass(frozen=True)
class Entry:
    ref: str  # short id the model cites, e.g. "exp1"
    label: str  # human-readable source shown in the UI
    heading: str  # the line shown to the model above the entry's body
    lines: tuple[str, ...]  # body lines (bullets, details)

    @property
    def text(self) -> str:
        return "\n".join((self.heading, *self.lines))


def _dates(start: str, end: str, current: bool = False) -> str:
    end = "Present" if current and not end else end
    return " - ".join(part for part in (start, end) if part)


def build_index(profile: Profile) -> list[Entry]:
    entries: list[Entry] = []
    if profile.summary:
        entries.append(Entry("summary", "Summary", "Summary", (profile.summary,)))

    for i, role in enumerate(profile.experience, start=1):
        label = " at ".join(part for part in (role.title, role.company) if part) or f"Role {i}"
        dates = _dates(role.start, role.end, role.current)
        heading = f"{label} ({dates})" if dates else label
        entries.append(Entry(f"exp{i}", label, heading, tuple(role.bullets)))

    for i, edu in enumerate(profile.education, start=1):
        label = ", ".join(part for part in (edu.degree, edu.field, edu.school) if part) or f"Education {i}"
        entries.append(Entry(f"edu{i}", label, label, tuple(edu.details)))

    if profile.skills:
        lines = tuple(
            f"{group.category}: {', '.join(group.items)}" if group.category else ", ".join(group.items)
            for group in profile.skills
        )
        entries.append(Entry("skills", "Skills", "Skills", lines))

    for i, cert in enumerate(profile.certifications, start=1):
        label = " - ".join(part for part in (cert.name, cert.issuer) if part) or f"Certification {i}"
        entries.append(Entry(f"cert{i}", label, label, ()))

    for i, project in enumerate(profile.projects, start=1):
        label = project.name or f"Project {i}"
        body = tuple(part for part in (project.description, *project.bullets) if part)
        tech = (f"Technologies: {', '.join(project.tech)}",) if project.tech else ()
        entries.append(Entry(f"proj{i}", f"Project: {label}", label, (*body, *tech)))

    return entries


def render_for_prompt(entries: list[Entry]) -> str:
    blocks = []
    for entry in entries:
        body = "\n".join(f"- {line}" for line in entry.lines)
        blocks.append(f"[{entry.ref}] {entry.heading}" + (f"\n{body}" if body else ""))
    return "\n\n".join(blocks)


def normalize(text: str) -> str:
    """Case, spacing, dash and quote insensitive form used when comparing quotes."""
    text = text.lower().replace("–", "-").replace("—", "-")
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip(" .;,-\"'")


def quote_is_in(quote: str, entry: Entry) -> bool:
    needle = normalize(quote)
    return len(needle) >= 2 and needle in normalize(entry.text)


def full_text(entries: list[Entry]) -> str:
    return "\n".join(entry.text for entry in entries)
