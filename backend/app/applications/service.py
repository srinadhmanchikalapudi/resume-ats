"""Orchestrates the database and the application folders."""

from __future__ import annotations

from . import files, store
from .models import ApplicationCreate, ApplicationCreated, ApplicationDetail, ApplicationPatch


class NotFoundError(LookupError):
    pass


def create(data: ApplicationCreate) -> ApplicationCreated:
    text = data.posting_text.strip()
    if len(text) < 40:
        raise ValueError("The job posting is too short to save.")

    existing = store.find_by_posting(text)
    if existing is not None:
        detail = store.get(existing)
        assert detail is not None
        return ApplicationCreated(**detail.model_dump(), already_saved=True)

    job = data.analysis.job if data.analysis else None
    company = data.company.strip() or (job.company if job else "")
    title = data.title.strip() or (job.title if job else "")
    location = data.location.strip() or (job.location if job else "")
    score = data.analysis.scores.overall if data.analysis else None

    folder = files.new_folder_name(company, title)
    app_id = store.create(
        company=company,
        title=title,
        location=location,
        job_url=data.job_url.strip(),
        posting_text=text,
        analysis_json=data.analysis.model_dump_json() if data.analysis else None,
        match_score=score,
        folder=folder,
    )
    files.write_text(folder, "posting.txt", text)
    if data.analysis:
        files.write_text(folder, "analysis.json", data.analysis.model_dump_json(indent=2))

    detail = store.get(app_id)
    assert detail is not None
    return ApplicationCreated(**detail.model_dump())


def patch(app_id: int, changes: ApplicationPatch) -> ApplicationDetail:
    detail = store.update(app_id, changes)
    if detail is None:
        raise NotFoundError(app_id)
    if "notes" in changes.model_fields_set:
        folder = store.folder_of(app_id)
        if folder:
            if detail.notes.strip():
                files.write_text(folder, "notes.md", detail.notes)
            else:
                files.remove_file(folder, "notes.md")
    return detail


def delete(app_id: int, *, delete_files: bool) -> None:
    folder = store.delete(app_id)
    if folder is None:
        raise NotFoundError(app_id)
    if delete_files:
        files.delete_folder(folder)
