from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request

from ..config import load_settings
from ..keystore import SecretStoreError


@dataclass(frozen=True)
class LlmAccess:
    base_url: str
    api_key: str
    model: str


def llm_access(request: Request, task: Literal["extraction", "analysis", "rewrite"]) -> LlmAccess:
    """Settings + keychain for one task, or an HTTP error that tells the user what to configure."""
    settings = load_settings()
    model = settings.model_for(task)
    if not model:
        raise HTTPException(status_code=400, detail="Choose a model in Settings first.")
    try:
        api_key = request.app.state.secret_store.get()
    except SecretStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not api_key:
        raise HTTPException(status_code=400, detail="Add your API key in Settings first.")
    return LlmAccess(base_url=settings.base_url, api_key=api_key, model=model)
