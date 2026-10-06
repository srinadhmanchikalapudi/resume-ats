from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile

from .. import llm
from ..config import load_settings
from ..keystore import SecretStoreError
from ..profile import importer, store
from ..profile.extract_text import ExtractError, extract_text
from ..profile.models import ImportResult, ImportTextIn, Profile, ProfileOut

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile() -> ProfileOut:
    profile, updated_at = store.load_profile()
    return ProfileOut(profile=profile, exists=updated_at is not None, updated_at=updated_at)


@router.put("", response_model=ProfileOut)
def put_profile(profile: Profile) -> ProfileOut:
    updated_at = store.save_profile(profile)
    return ProfileOut(profile=profile, exists=True, updated_at=updated_at)


@router.post("/import", response_model=ImportResult)
async def import_file(request: Request, file: UploadFile) -> ImportResult:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 5 MB.")
    try:
        extracted = extract_text(file.filename or "", data)
    except ExtractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _parse(request, extracted.text, extracted.warnings)


@router.post("/import-text", response_model=ImportResult)
async def import_text(request: Request, body: ImportTextIn) -> ImportResult:
    text = body.text.strip()
    if len(text) < 40:
        raise HTTPException(status_code=422, detail="Paste the full text of your resume.")
    return await _parse(request, text, [])


async def _parse(request: Request, text: str, warnings: list[str]) -> ImportResult:
    settings = load_settings()
    model = settings.extraction_model or settings.model
    if not model:
        raise HTTPException(status_code=400, detail="Choose a model in Settings first.")
    try:
        api_key = request.app.state.secret_store.get()
    except SecretStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not api_key:
        raise HTTPException(status_code=400, detail="Add your API key in Settings first.")
    try:
        return await importer.parse_resume(
            text, base_url=settings.base_url, api_key=api_key, model=model, warnings=warnings
        )
    except llm.LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
