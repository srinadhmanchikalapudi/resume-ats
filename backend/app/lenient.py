"""Forgiving field types for validating LLM output.

Models return nulls, numbers where strings were asked for, comma-joined lists and extra keys.
These types absorb that instead of failing the whole response.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict


def as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [as_text(item) for item in value if as_text(item)]  # type: ignore[union-attr]


def as_list(value: object) -> object:
    return [] if value is None else value


def as_optional_int(value: object) -> int | None:
    """Accepts 5, "5", "5+", "5 years"; anything without a leading number is None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    digits = ""
    for char in str(value).strip():
        if not char.isdigit():
            break
        digits += char
    return int(digits) if digits else None


Text = Annotated[str, BeforeValidator(as_text)]
TextList = Annotated[list[str], BeforeValidator(as_text_list)]
OptionalInt = Annotated[int | None, BeforeValidator(as_optional_int)]


class Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")
