from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from app import llm


class Answer(BaseModel):
    name: str
    count: int = 0


class FakeCompletions:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


class FakeClient:
    def __init__(self, script):
        self.completions = FakeCompletions(script)
        self.chat = SimpleNamespace(completions=self.completions)

    async def close(self):
        pass


def fake_client(monkeypatch, *script) -> FakeClient:
    client = FakeClient(script)
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: client)
    return client


def status_error(cls, status):
    response = httpx.Response(status, request=httpx.Request("POST", "http://test"))
    return cls("failure", response=response, body=None)


async def run():
    return await llm.complete_json(
        base_url="http://test", api_key="k", model="m", system="s", user="u", schema=Answer
    )


def test_extract_json_object_handles_fences_and_chatter():
    assert llm.extract_json_object('{"a": 1}') == {"a": 1}
    assert llm.extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.extract_json_object('Sure! Here it is: {"a": {"b": 2}} Hope that helps.') == {
        "a": {"b": 2}
    }
    with pytest.raises(ValueError):
        llm.extract_json_object("no json here")


async def test_valid_reply_is_parsed_and_json_mode_requested(monkeypatch):
    client = fake_client(monkeypatch, '{"name": "x", "count": 2}')
    result = await run()
    assert result == Answer(name="x", count=2)
    assert client.completions.calls[0]["response_format"] == {"type": "json_object"}


async def test_json_mode_is_dropped_when_the_model_rejects_it(monkeypatch):
    client = fake_client(monkeypatch, status_error(openai.BadRequestError, 400), '{"name": "x"}')
    assert (await run()).name == "x"
    assert "response_format" in client.completions.calls[0]
    assert "response_format" not in client.completions.calls[1]


async def test_invalid_reply_is_retried_once_with_the_error(monkeypatch):
    client = fake_client(monkeypatch, '{"count": 1}', '{"name": "fixed"}')
    assert (await run()).name == "fixed"
    retry_messages = client.completions.calls[1]["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "not valid" in retry_messages[-1]["content"]


async def test_two_invalid_replies_raise(monkeypatch):
    fake_client(monkeypatch, "nonsense", '{"count": 1}')
    with pytest.raises(llm.LlmError, match="usable JSON"):
        await run()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (status_error(openai.AuthenticationError, 401), "key was rejected"),
        (status_error(openai.NotFoundError, 404), "was not found"),
        (status_error(openai.RateLimitError, 429), "rate limiting"),
        (status_error(openai.InternalServerError, 500), "(500)"),
    ],
)
async def test_api_errors_become_friendly_messages(monkeypatch, error, message):
    fake_client(monkeypatch, error)
    with pytest.raises(llm.LlmError, match=message.replace("(", r"\(").replace(")", r"\)")):
        await run()
