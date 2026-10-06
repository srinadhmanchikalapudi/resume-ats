"""The on-disk copy of each application: a plain folder you can browse without the app.

applications/<date>_<company>_<role>/
    posting.txt     the job posting exactly as pasted
    analysis.json   the match analysis
    notes.md        your notes (written whenever they change)
    v1/ v2/ ...     one folder per exported resume version, each with the DOCX and PDF
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from ..config import data_dir
from ..export.text import slug


def applications_root() -> Path:
    path = data_dir() / "applications"
    path.mkdir(parents=True, exist_ok=True)
    return path


def unique_folder_name(stem: str) -> str:
    root = applications_root()
    name, number = stem, 2
    while (root / name).exists():
        name = f"{stem}-{number}"
        number += 1
    return name


def new_folder_name(company: str, title: str) -> str:
    today = datetime.now().astimezone().date().isoformat()
    return unique_folder_name("_".join([today, slug(company) or "Company", slug(title) or "Role"]))


def folder_path(name: str) -> Path:
    """The folder for an application, always inside the applications directory."""
    root = applications_root().resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise ValueError("Invalid application folder.")
    path.mkdir(parents=True, exist_ok=True)  # recreate if the user removed it
    return path


def write_text(name: str, filename: str, text: str) -> None:
    (folder_path(name) / filename).write_text(text, encoding="utf-8")


def remove_file(name: str, filename: str) -> None:
    (folder_path(name) / filename).unlink(missing_ok=True)


def version_dir(name: str, number: int) -> Path:
    path = folder_path(name) / f"v{number}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def delete_folder(name: str) -> None:
    root = applications_root().resolve()
    path = (root / name).resolve()
    if path.parent == root and path.is_dir():
        shutil.rmtree(path)
