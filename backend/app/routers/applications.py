from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..applications import service, store
from ..applications.models import (
    ApplicationCreate,
    ApplicationCreated,
    ApplicationDetail,
    ApplicationPatch,
    ApplicationSummary,
    SortKey,
    VersionDetail,
)

router = APIRouter(prefix="/applications", tags=["applications"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Application not found.")


@router.post("", response_model=ApplicationCreated)
def create(body: ApplicationCreate) -> ApplicationCreated:
    """Saves a job posting (and its analysis). Saving the identical posting again returns the existing record."""
    try:
        return service.create(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[ApplicationSummary])
def list_applications(q: str = "", status: str | None = None, sort: SortKey = "updated") -> list[ApplicationSummary]:
    return store.search(q, status, sort)


@router.get("/{app_id}", response_model=ApplicationDetail)
def get_application(app_id: int) -> ApplicationDetail:
    detail = store.get(app_id)
    if detail is None:
        raise _not_found()
    return detail


@router.patch("/{app_id}", response_model=ApplicationDetail)
def patch_application(app_id: int, body: ApplicationPatch) -> ApplicationDetail:
    try:
        return service.patch(app_id, body)
    except service.NotFoundError as exc:
        raise _not_found() from exc


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: int, delete_files: bool = False) -> None:
    try:
        service.delete(app_id, delete_files=delete_files)
    except service.NotFoundError as exc:
        raise _not_found() from exc


@router.get("/{app_id}/versions/{version_id}", response_model=VersionDetail)
def get_version(app_id: int, version_id: int) -> VersionDetail:
    version = store.get_version(app_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return version


@router.put("/{app_id}/versions/{version_id}/submitted", response_model=ApplicationDetail)
def mark_submitted(app_id: int, version_id: int, submitted: bool = True) -> ApplicationDetail:
    """Marks the version that was actually sent (or clears it). Marking the first one moves "saved" to "applied"."""
    detail = store.set_submitted(app_id, version_id, submitted)
    if detail is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return detail
