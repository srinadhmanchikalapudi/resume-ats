from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import data_dir
from .blocks import build_blocks
from .checks import check_docx, check_pdf
from .docx_builder import build_docx
from .models import ExportedFile, ExportRequest, ExportResult
from .pdf_builder import build_pdf
from .text import slug


def applications_dir() -> Path:
    path = data_dir() / "applications"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _unique_folder(base: Path, stem: str) -> Path:
    candidate, number = base / stem, 2
    while candidate.exists():
        candidate = base / f"{stem}-{number}"
        number += 1
    return candidate


def export_resume(request: ExportRequest) -> ExportResult:
    """Writes the resume as DOCX and PDF into a new folder and verifies both files."""
    profile = request.profile
    blocks = build_blocks(profile, skills_first=request.skills_first)
    if not any(block.kind in {"bullet", "item_title", "text"} for block in blocks):
        raise ValueError("There is nothing to export yet. Add work experience to the resume first.")

    name = profile.contact.name.strip()
    today = datetime.now().astimezone().date().isoformat()
    stem = "_".join([today, slug(request.company) or "Company", slug(request.job_title) or "Role"])
    folder = _unique_folder(applications_dir(), stem)
    folder.mkdir(parents=True)

    base_name = f"{slug(name).replace('-', '_') or 'Resume'}_Resume"
    warnings: list[str] = []

    docx_bytes = build_docx(blocks, name=name, paper=request.paper)
    pdf = build_pdf(blocks, name=name, paper=request.paper)

    docx_path, pdf_path = folder / f"{base_name}.docx", folder / f"{base_name}.pdf"
    docx_path.write_bytes(docx_bytes)
    pdf_path.write_bytes(pdf.data)

    pdf_checks, pages = check_pdf(pdf.data, blocks, pdf.replaced_characters)
    files = [
        ExportedFile(
            format="docx",
            path=str(docx_path),
            filename=docx_path.name,
            size_bytes=len(docx_bytes),
            checks=check_docx(docx_bytes, blocks),
        ),
        ExportedFile(
            format="pdf",
            path=str(pdf_path),
            filename=pdf_path.name,
            size_bytes=len(pdf.data),
            pages=pages,
            checks=pdf_checks,
        ),
    ]

    if pdf.replaced_characters:
        warnings.append(
            f"{pdf.replaced_characters} character(s) cannot be drawn with the PDF's standard fonts and show as '?'. "
            "The DOCX keeps them."
        )
    if not profile.contact.email:
        warnings.append("The resume has no email address. Recruiters and applicant tracking systems look for one.")

    return ExportResult(folder=str(folder), files=files, warnings=warnings)
