from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..applications import files as application_files
from ..applications import store
from .blocks import build_blocks
from .checks import check_docx, check_pdf
from .docx_builder import build_docx
from .models import ExportedFile, ExportRequest, ExportResult
from .pdf_builder import build_pdf
from .text import slug


class ApplicationNotFoundError(LookupError):
    pass


def applications_dir() -> Path:
    return application_files.applications_root()


def export_resume(request: ExportRequest) -> ExportResult:
    """Writes the resume as DOCX and PDF and verifies both files.

    With an application, the files become that application's next numbered version (v1, v2, ...) and are
    recorded in the archive. Without one, they go into a new standalone dated folder.
    """
    profile = request.profile
    blocks = build_blocks(profile, skills_first=request.skills_first)
    if not any(block.kind in {"bullet", "item_title", "text"} for block in blocks):
        raise ValueError("There is nothing to export yet. Add work experience to the resume first.")

    name = profile.contact.name.strip()
    base_name = f"{slug(name).replace('-', '_') or 'Resume'}_Resume"

    version_number: int | None = None
    if request.application_id is not None:
        folder_name = store.folder_of(request.application_id)
        if folder_name is None:
            raise ApplicationNotFoundError(request.application_id)
        version_number = store.next_version_number(request.application_id)
        folder = application_files.version_dir(folder_name, version_number)
    else:
        today = datetime.now().astimezone().date().isoformat()
        stem = "_".join([today, slug(request.company) or "Company", slug(request.job_title) or "Role"])
        folder = application_files.applications_root() / application_files.unique_folder_name(stem)
        folder.mkdir(parents=True)

    warnings: list[str] = []
    docx_bytes = build_docx(blocks, name=name, paper=request.paper)
    pdf = build_pdf(blocks, name=name, paper=request.paper)

    docx_path, pdf_path = folder / f"{base_name}.docx", folder / f"{base_name}.pdf"
    docx_path.write_bytes(docx_bytes)
    pdf_path.write_bytes(pdf.data)

    pdf_checks, pages = check_pdf(pdf.data, blocks, pdf.replaced_characters)
    exported = [
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

    version_id = None
    if request.application_id is not None and version_number is not None:
        version_id = store.add_version(
            request.application_id,
            number=version_number,
            subdir=f"v{version_number}",
            docx_name=docx_path.name,
            pdf_name=pdf_path.name,
            pages=pages,
            checks_passed=all(check.ok for file in exported for check in file.checks),
            skills_first=request.skills_first,
            profile=profile,
        )

    return ExportResult(
        folder=str(folder),
        files=exported,
        warnings=warnings,
        application_id=request.application_id,
        version_id=version_id,
        version_number=version_number,
    )
