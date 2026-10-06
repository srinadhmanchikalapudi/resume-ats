import sqlite3

import pytest
from factories import RESUME, make_docx

from app import db, llm
from app.config import data_dir
from app.profile import store
from app.profile.models import Experience, ImportResult, Profile

SAMPLE = Profile.model_validate(
    {
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "start": "2020",
                "current": True,
                "bullets": ["Built a billing API."],
            }
        ],
        "skills": [{"category": "Languages", "items": ["Python", "C#"]}],
    }
)


@pytest.fixture
def configured(client, auth, store):
    """A client with an API key and model set, so import endpoints get as far as the LLM."""
    store.set("sk-test")
    client.put("/settings", headers=auth, json={"model": "test/model"})
    return client


def fake_parse(captured=None):
    async def fake(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return SAMPLE.model_copy(deep=True)

    return fake


# --- models -----------------------------------------------------------------------------------


def test_profile_tolerates_messy_llm_output():
    profile = Profile.model_validate(
        {
            "summary": None,
            "experience": [{"title": None, "bullets": None, "start": 2019, "extra": "ignored"}],
            "skills": [{"category": "Cloud", "items": "Azure, AWS, "}],
            "projects": None,
        }
    )
    assert profile.summary == ""
    assert profile.experience[0].start == "2019"
    assert profile.experience[0].bullets == []
    assert profile.skills[0].items == ["Azure", "AWS"]
    assert profile.projects == []


def test_current_role_drops_any_end_date():
    role = Experience.model_validate({"title": "Engineer", "current": True, "end": "Mar 2023"})
    assert role.end == ""
    assert Experience.model_validate({"current": False, "end": "Mar 2023"}).end == "Mar 2023"


def test_entries_get_unique_stable_ids():
    first, second = Experience(), Experience()
    assert first.id and first.id != second.id
    assert Profile.model_validate_json(Profile(experience=[first]).model_dump_json()).experience[0].id == first.id


# --- storage ----------------------------------------------------------------------------------


def test_load_returns_empty_profile_before_first_save():
    profile, updated_at = store.load_profile()
    assert profile.is_empty()
    assert updated_at is None


def test_save_then_load_roundtrip_and_overwrite():
    store.save_profile(SAMPLE)
    loaded, updated_at = store.load_profile()
    assert loaded == SAMPLE
    assert updated_at

    store.save_profile(Profile())
    assert store.load_profile()[0].is_empty()


def test_migrations_are_applied_once_and_recorded():
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    with db.connect() as conn:  # reopening must not re-run them
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    raw = sqlite3.connect(data_dir() / "resume-ats.db")
    assert raw.execute("SELECT name FROM sqlite_master WHERE name = 'profile'").fetchone()
    raw.close()


# --- API --------------------------------------------------------------------------------------


def test_profile_endpoints_require_token(client):
    assert client.get("/profile").status_code == 401
    assert client.post("/profile/import-text", json={"text": "x"}).status_code == 401


def test_get_put_get_profile(client, auth):
    first = client.get("/profile", headers=auth).json()
    assert first["exists"] is False

    saved = client.put("/profile", headers=auth, json=SAMPLE.model_dump())
    assert saved.status_code == 200
    assert saved.json()["exists"] is True

    again = client.get("/profile", headers=auth).json()
    assert again["exists"] is True
    assert again["profile"]["contact"]["name"] == "Jane Doe"
    assert again["profile"]["skills"][0]["items"] == ["Python", "C#"]


def test_import_text_uses_the_extraction_model_when_set(configured, auth, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(llm, "complete_json", fake_parse(captured))
    configured.put(
        "/settings", headers=auth, json={"model": "test/model", "extraction_model": "cheap/model"}
    )

    response = configured.post("/profile/import-text", headers=auth, json={"text": RESUME * 3})

    assert response.status_code == 200
    assert response.json()["profile"]["contact"]["name"] == "Jane Doe"
    assert captured["model"] == "cheap/model"
    assert captured["api_key"] == "sk-test"
    assert "Senior Engineer" in captured["user"]


def test_import_does_not_save_the_draft(configured, auth, monkeypatch):
    monkeypatch.setattr(llm, "complete_json", fake_parse())
    configured.post("/profile/import-text", headers=auth, json={"text": RESUME * 3})
    assert configured.get("/profile", headers=auth).json()["exists"] is False


def test_import_docx_file_returns_extraction_warnings(configured, auth, monkeypatch):
    monkeypatch.setattr(llm, "complete_json", fake_parse())
    docx_bytes = make_docx(header="Jane Doe | 555-0100")
    response = configured.post(
        "/profile/import", headers=auth, files={"file": ("resume.docx", docx_bytes)}
    )
    assert response.status_code == 200
    assert any("header or footer" in w for w in response.json()["warnings"])


def test_import_warns_when_nothing_useful_was_found(configured, auth, monkeypatch):
    async def empty(**kwargs):
        return Profile()

    monkeypatch.setattr(llm, "complete_json", empty)
    result = ImportResult.model_validate(
        configured.post("/profile/import-text", headers=auth, json={"text": RESUME * 3}).json()
    )
    assert any("No work experience" in w for w in result.warnings)


def test_import_needs_model_and_key(client, auth, store):
    body = {"text": RESUME * 3}
    no_model = client.post("/profile/import-text", headers=auth, json=body)
    assert no_model.status_code == 400
    assert "model" in no_model.json()["detail"]

    client.put("/settings", headers=auth, json={"model": "test/model"})
    no_key = client.post("/profile/import-text", headers=auth, json=body)
    assert no_key.status_code == 400
    assert "API key" in no_key.json()["detail"]


def test_import_rejects_bad_input(configured, auth):
    assert configured.post("/profile/import-text", headers=auth, json={"text": "hi"}).status_code == 422
    unsupported = configured.post("/profile/import", headers=auth, files={"file": ("a.png", b"x" * 100)})
    assert unsupported.status_code == 422
    too_big = configured.post(
        "/profile/import", headers=auth, files={"file": ("a.txt", b"x" * (5 * 1024 * 1024 + 1))}
    )
    assert too_big.status_code == 413


def test_llm_failure_is_a_502(configured, auth, monkeypatch):
    async def boom(**kwargs):
        raise llm.LlmError("The API key was rejected.")

    monkeypatch.setattr(llm, "complete_json", boom)
    response = configured.post("/profile/import-text", headers=auth, json={"text": RESUME * 3})
    assert response.status_code == 502
    assert "rejected" in response.json()["detail"]
