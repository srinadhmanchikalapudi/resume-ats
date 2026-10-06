import pytest

from app import llm
from app.jobs.models import JobAnalysis, MatchIn
from app.profile import store
from app.profile.models import Profile

POSTING = (
    "Senior Backend Engineer at Globex. Remote. You will build billing APIs. "
    "Requirements: 5+ years of C# and .NET, experience with serverless on Azure, "
    "Kubernetes in production. Preferred: Python."
)

PROFILE = Profile.model_validate(
    {
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "start": "January 2018",
                "end": "January 2024",
                "bullets": ["Led migration of 12 services to Azure Functions.", "Wrote C# APIs on .NET."],
            }
        ],
        "skills": [{"category": "Languages", "items": ["C#", "Python"]}],
    }
)

JOB_REPLY = {
    "title": "Senior Backend Engineer",
    "company": "Globex",
    "seniority": "senior",
    "years_required": 5,
    "keywords": ["C#", ".NET", "Azure", "Kubernetes", "Python"],
    "requirements": [
        {"text": "C# and .NET", "category": "skill", "importance": "required", "keywords": ["C#", ".NET"]},
        {"text": "Serverless on Azure", "category": "skill", "importance": "required"},
        {"text": "Kubernetes in production", "category": "tool", "importance": "required"},
        {"text": "Python", "category": "skill", "importance": "preferred"},
    ],
}

MATCH_REPLY = {
    "matches": [
        {"requirement_id": "r1", "status": "matched", "evidence": [{"ref": "exp1", "quote": "Wrote C# APIs on .NET."}]},
        {
            "requirement_id": "r2",
            "status": "matched",
            "evidence": [{"ref": "exp1", "quote": "migration of 12 services to Azure Functions"}],
        },
        {"requirement_id": "r3", "status": "matched", "evidence": [{"ref": "exp1", "quote": "Ran Kubernetes clusters"}]},
        {"requirement_id": "r4", "status": "matched", "evidence": [{"ref": "skills", "quote": "Python"}]},
    ]
}


@pytest.fixture
def ready(client, auth, store):
    store.set("sk-test")
    client.put("/settings", headers=auth, json={"model": "big/model", "extraction_model": "small/model"})
    return client


@pytest.fixture
def fake_llm(monkeypatch):
    """Answers by schema and records which model was used for which step."""
    used = {}

    async def fake(**kwargs):
        schema = kwargs["schema"]
        used[schema.__name__] = kwargs["model"]
        reply = JOB_REPLY if schema is JobAnalysis else MATCH_REPLY
        return schema.model_validate(reply)

    monkeypatch.setattr(llm, "complete_json", fake)
    return used


def test_analyze_requires_token(client):
    assert client.post("/jobs/analyze", json={"text": POSTING}).status_code == 401


def test_analyze_needs_a_saved_profile(ready, auth, fake_llm):
    response = ready.post("/jobs/analyze", headers=auth, json={"text": POSTING})
    assert response.status_code == 400
    assert "master profile" in response.json()["detail"]


def test_short_text_is_rejected(ready, auth, fake_llm):
    store.save_profile(PROFILE)
    assert ready.post("/jobs/analyze", headers=auth, json={"text": "too short"}).status_code == 422


def test_full_analysis_end_to_end(ready, auth, fake_llm):
    store.save_profile(PROFILE)
    response = ready.post("/jobs/analyze", headers=auth, json={"text": POSTING})
    assert response.status_code == 200
    data = response.json()

    assert data["job"]["title"] == "Senior Backend Engineer"
    statuses = {m["requirement"]["id"]: m["status"] for m in data["matches"]}
    # r3's quote does not exist in the profile, so the claimed match must not count.
    assert statuses == {"r1": "matched", "r2": "matched", "r3": "unverified", "r4": "matched"}
    assert any("could not be verified" in w for w in data["warnings"])

    scores = data["scores"]
    assert scores["required_total"] == 3
    assert scores["required_matched"] == 2
    assert scores["required_missing"] == 1
    # (3 + 3 + 0 + 1.5) / (3 + 3 + 3 + 1.5)
    assert scores["overall"] == 71
    assert scores["candidate_years"] == 6.0
    assert scores["years_short_by"] is None

    assert data["keywords"]["present"] == ["C#", ".NET", "Azure", "Python"]
    assert data["keywords"]["missing"] == ["Kubernetes"]


def test_each_step_uses_its_own_model(ready, auth, fake_llm):
    store.save_profile(PROFILE)
    ready.post("/jobs/analyze", headers=auth, json={"text": POSTING})
    assert fake_llm == {"JobAnalysis": "small/model", "MatchIn": "big/model"}


def test_posting_without_requirements_is_a_clear_error(ready, auth, monkeypatch):
    store.save_profile(PROFILE)

    async def empty(**kwargs):
        return kwargs["schema"]()

    monkeypatch.setattr(llm, "complete_json", empty)
    response = ready.post("/jobs/analyze", headers=auth, json={"text": POSTING})
    assert response.status_code == 422
    assert "No requirements" in response.json()["detail"]


def test_model_failure_is_a_502(ready, auth, monkeypatch):
    store.save_profile(PROFILE)

    async def boom(**kwargs):
        raise llm.LlmError("The model server returned an error (500).")

    monkeypatch.setattr(llm, "complete_json", boom)
    assert ready.post("/jobs/analyze", headers=auth, json={"text": POSTING}).status_code == 502


def test_analyze_needs_model_and_key(client, auth):
    store.save_profile(PROFILE)
    assert "model" in client.post("/jobs/analyze", headers=auth, json={"text": POSTING}).json()["detail"]


def test_match_reply_schema_is_what_the_prompt_describes():
    assert MatchIn.model_validate(MATCH_REPLY).matches[0].evidence[0].ref == "exp1"
