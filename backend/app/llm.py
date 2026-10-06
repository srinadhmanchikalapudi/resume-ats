"""OpenRouter / OpenAI-compatible access: model catalogue and connection test."""

from __future__ import annotations

import httpx
import openai
from pydantic import BaseModel


class LlmError(RuntimeError):
    pass


class ModelInfo(BaseModel):
    id: str
    name: str
    context_length: int | None = None
    prompt_price: float | None = None  # USD per token, when the provider reports it
    completion_price: float | None = None
    # True/False when the server reports supported_parameters, None when unknown.
    supports_json: bool | None = None


class ConnectionResult(BaseModel):
    ok: bool
    message: str


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_models(payload: dict) -> list[ModelInfo]:
    models: list[ModelInfo] = []
    for item in payload.get("data", []):
        model_id = item.get("id")
        if not model_id:
            continue
        params = item.get("supported_parameters")
        pricing = item.get("pricing") or {}
        models.append(
            ModelInfo(
                id=model_id,
                name=item.get("name") or model_id,
                context_length=item.get("context_length"),
                prompt_price=_to_float(pricing.get("prompt")),
                completion_price=_to_float(pricing.get("completion")),
                supports_json=(
                    None
                    if params is None
                    else any(p in params for p in ("response_format", "structured_outputs"))
                ),
            )
        )
    models.sort(key=lambda m: m.id)
    return models


async def list_models(base_url: str, api_key: str | None) -> list[ModelInfo]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{base_url}/models", headers=headers)
            response.raise_for_status()
            return parse_models(response.json())
    except httpx.HTTPStatusError as exc:
        raise LlmError(f"Model list request failed ({exc.response.status_code}).") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise LlmError(f"Could not fetch the model list: {exc}") from exc


async def check_connection(base_url: str, api_key: str, model: str) -> ConnectionResult:
    """One-token completion: validates the key, the base URL and the chosen model together."""
    client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=30, max_retries=0)
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the word ok."}],
            max_tokens=5,
        )
    except openai.AuthenticationError:
        return ConnectionResult(ok=False, message="The API key was rejected.")
    except openai.NotFoundError:
        return ConnectionResult(ok=False, message=f"Model '{model}' was not found.")
    except openai.APIConnectionError:
        return ConnectionResult(ok=False, message="Could not reach the server. Check the base URL.")
    except openai.APIStatusError as exc:
        return ConnectionResult(ok=False, message=f"The server returned an error ({exc.status_code}).")
    finally:
        await client.close()
    return ConnectionResult(ok=True, message="Connection works.")
