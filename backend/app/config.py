"""Where user data lives and the non-secret settings stored there."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel, field_validator

APP_NAME = "ResumeATS"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def data_dir() -> Path:
    """OS user-data directory (override with RESUME_ATS_DATA_DIR). Survives app updates."""
    override = os.environ.get("RESUME_ATS_DATA_DIR")
    path = Path(override) if override else Path(user_data_dir(APP_NAME, appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


class Settings(BaseModel):
    base_url: str = DEFAULT_BASE_URL
    model: str = ""
    # Optional per-task overrides; empty means "use the default model".
    extraction_model: str = ""
    rewrite_model: str = ""

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return value

    @field_validator("model", "extraction_model", "rewrite_model")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> Settings:
    path = _settings_path()
    if not path.exists():
        return Settings()
    try:
        return Settings.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        # Corrupt file: fall back to defaults rather than blocking app start.
        return Settings()


def save_settings(settings: Settings) -> None:
    _settings_path().write_text(settings.model_dump_json(indent=2), encoding="utf-8")
