"""FastAPI application factory."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, llm
from .config import Settings, load_settings, save_settings
from .keystore import KeychainStore, SecretStore, SecretStoreError
from .routers import profile

# Origins the Tauri webview uses on each OS, plus the Angular dev server.
ALLOWED_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]


class SettingsOut(Settings):
    has_api_key: bool


class ApiKeyIn(BaseModel):
    api_key: str


def create_app(token: str | None = None, secret_store: SecretStore | None = None) -> FastAPI:
    store: SecretStore = secret_store or KeychainStore()
    app = FastAPI(title="Resume ATS", version=__version__)
    app.state.secret_store = store
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_token(x_app_token: str | None = Header(default=None)) -> None:
        if token is None:
            return
        if x_app_token is None or not hmac.compare_digest(x_app_token, token):
            raise HTTPException(status_code=401, detail="Invalid or missing app token.")

    def current_key() -> str | None:
        try:
            return store.get()
        except SecretStoreError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    api = APIRouter(dependencies=[Depends(require_token)])

    @api.get("/settings", response_model=SettingsOut)
    def get_settings() -> SettingsOut:
        return SettingsOut(**load_settings().model_dump(), has_api_key=bool(current_key()))

    @api.put("/settings", response_model=SettingsOut)
    def put_settings(settings: Settings) -> SettingsOut:
        save_settings(settings)
        return SettingsOut(**settings.model_dump(), has_api_key=bool(current_key()))

    @api.put("/settings/api-key", status_code=204)
    def put_api_key(body: ApiKeyIn) -> None:
        key = body.api_key.strip()
        if not key:
            raise HTTPException(status_code=422, detail="API key must not be empty.")
        try:
            store.set(key)
        except SecretStoreError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @api.delete("/settings/api-key", status_code=204)
    def delete_api_key() -> None:
        try:
            store.delete()
        except SecretStoreError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @api.get("/models", response_model=list[llm.ModelInfo])
    async def get_models() -> list[llm.ModelInfo]:
        try:
            return await llm.list_models(load_settings().base_url, current_key())
        except llm.LlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @api.post("/settings/test", response_model=llm.ConnectionResult)
    async def test_settings() -> llm.ConnectionResult:
        settings = load_settings()
        key = current_key()
        if not key:
            return llm.ConnectionResult(ok=False, message="No API key saved yet.")
        if not settings.model:
            return llm.ConnectionResult(ok=False, message="Choose a model first.")
        return await llm.check_connection(settings.base_url, key, settings.model)

    api.include_router(profile.router)
    app.include_router(api)
    return app
