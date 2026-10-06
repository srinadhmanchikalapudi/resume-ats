from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..export import service
from ..export.models import ExportRequest, ExportResult

router = APIRouter(prefix="/export", tags=["export"])

MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


@router.post("", response_model=ExportResult)
def export(body: ExportRequest) -> ExportResult:
    try:
        return service.export_resume(body)
    except service.ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="That application no longer exists.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/file")
def download(path: str) -> FileResponse:
    """Serves a previously exported file. Only files inside the exports folder can be fetched."""
    target = Path(path).resolve()
    base = service.applications_dir().resolve()
    if not target.is_relative_to(base) or target.suffix.lower() not in MEDIA_TYPES or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(target, media_type=MEDIA_TYPES[target.suffix.lower()], filename=target.name)
