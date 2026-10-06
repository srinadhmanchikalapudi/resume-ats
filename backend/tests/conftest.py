import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class MemoryStore:
    def __init__(self) -> None:
        self.value: str | None = None

    def get(self) -> str | None:
        return self.value

    def set(self, value: str) -> None:
        self.value = value

    def delete(self) -> None:
        self.value = None


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_ATS_DATA_DIR", str(tmp_path))


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def client(store) -> TestClient:
    return TestClient(create_app(token="secret", secret_store=store))


@pytest.fixture
def auth() -> dict[str, str]:
    return {"X-App-Token": "secret"}
