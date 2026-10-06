import pytest

from app import llm
from app.jobs.models import AnalysisResult, JobAnalysis, KeywordCheck, RequirementMatch, Scores
from app.profile import store
from app.profile.models import Profile
from app.tailor import prompt, verify
from app.tailor.models import TailorReply

PROFILE = Profile.model_validate(
    {
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "summary": "Backend engineer with 8 years of experience building billing systems in C#.",
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "start": "2020",
                "current": True,
                "bullets": [
                    "Maintained the internal wiki.",
                    "Built a billing API that cut invoice errors by 40%.",
                    "Led migration of 12 services to Azure Functions.",
                    "Wrote unit tests for the payments module.",
                ],
            },
            {
                "title": "Engineer",
                "company": "Initech",
                "start": "2016",
                "end": "2019",
                "bullets": ["Maintained the reporting platform.", "Built ETL jobs in SQL."],
            },
        ],
        "skills": [
            {"category": "Languages", "items": ["C#", "Python", "SQL"]},
            {"category": "Cloud", "items": ["Azure Functions", "Docker"]},
        ],
    }
)

JOB = JobAnalysis.model_validate(
    {
        "title": "Backend Engineer",
        "company": "Globex",
        "seniority": "senior",
        "keywords": ["C#", "Azure Functions", "Kubernetes", "Docker"],
        "requirements": [
            {"text": "C#", "importance": "required", "keywords": ["C#"]},
            {"text": "Serverless on Azure", "importance": "required", "keywords": ["Azure Functions"]},
            {"text": "Kubernetes in production", "importance": "required", "keywords": ["Kubernetes"]},
            {"text": "Message queues", "importance": "preferred", "keywords": ["message queues"]},
        ],
    }
)
ANALYSIS = AnalysisResult(
    job=JOB,
    matches=[
        RequirementMatch(requirement=JOB.requirements[0], status="matched"),
        RequirementMatch(requirement=JOB.requirements[1], status="matched"),
        RequirementMatch(requirement=JOB.requirements[2], status="missing"),
        # Verified as matched, though the profile never writes "message queues" literally.
        RequirementMatch(requirement=JOB.requirements[3], status="matched"),
    ],
    keywords=KeywordCheck(),
    scores=Scores(),
)


def reply(**data):
    return TailorReply.model_validate(data)


def build(reply_data, length="standard"):
    return verify.build_resume(PROFILE, ANALYSIS, TailorReply.model_validate(reply_data), length)


def role_reply(ref, *bullets):
    return {"ref": ref, "bullets": [{"source": s, "text": t} for s, t in bullets]}


ORIG = PROFILE.experience[0].bullets

# --- caps and prompt ------------------------------------------------------------------------------


def test_role_caps_per_length():
    assert prompt.role_caps(PROFILE, "concise") == [4, 2]  # limited by what each role has
    assert prompt.role_caps(PROFILE, "standard") == [4, 2]
    assert prompt.role_caps(PROFILE, "full") == [4, 2]
    many = Profile.model_validate({"experience": [{"bullets": ["x"] * 20}] * 5})
    assert prompt.role_caps(many, "concise") == [5, 4, 3, 3, 3]
    assert prompt.role_caps(many, "standard") == [8, 6, 5, 4, 4]
    assert prompt.role_caps(many, "full") == [20] * 5


def test_prompt_numbers_bullets_flags_missing_and_limits_skills():
    text = prompt.build_user_message(PROFILE, ANALYSIS, prompt.role_caps(PROFILE, "standard"))
    assert "[exp1] Senior Engineer at Acme (2020 - Present) - keep at most 4 bullets" in text
    assert "2. Built a billing API that cut invoice errors by 40%." in text
    assert "r3 [required] Kubernetes in production -> missing" in text
    assert "the only skills you may list" in text
    assert "Never add a fact" in prompt.SYSTEM_PROMPT
    assert "untrusted" in prompt.SYSTEM_PROMPT


# --- selection and traceability -------------------------------------------------------------------


def test_selects_orders_and_lists_what_was_dropped():
    result = build({"roles": [role_reply("exp1", (3, ORIG[2]), (2, ORIG[1]))]})
    role = result.roles[0]
    assert [b.source for b in role.bullets] == [3, 2]
    assert [b.original for b in role.bullets] == [ORIG[2], ORIG[1]]
    assert [d.source for d in role.dropped] == [1, 4]
    assert role.dropped[0].original == ORIG[0]


def test_invented_duplicate_and_out_of_range_bullets_are_ignored():
    result = build(
        {
            "roles": [
                role_reply(
                    "exp1",
                    (None, "A bullet that exists nowhere in the profile."),
                    (9, "Out of range."),
                    (0, "Zero is not valid."),
                    (2, ORIG[1]),
                    (2, "Duplicate of bullet 2."),
                )
            ]
        }
    )
    assert [b.source for b in result.roles[0].bullets] == [2]


def test_cap_is_enforced_even_if_the_model_ignores_it():
    result = build({"roles": [role_reply("exp1", (1, ORIG[0]), (2, ORIG[1]), (3, ORIG[2]), (4, ORIG[3]))]}, "concise")
    assert len(result.roles[0].bullets) == 4  # concise cap is 5, role has 4
    many = Profile.model_validate({"experience": [{"title": "T", "bullets": [f"b{i}" for i in range(10)]}]})
    out = verify.build_resume(
        many, ANALYSIS, TailorReply.model_validate({"roles": [role_reply("exp1", *[(i, f"b{i - 1}") for i in range(1, 11)])]}), "concise"
    )
    assert len(out.roles[0].bullets) == 5


def test_every_profile_role_is_kept_and_pass_through_sections_are_copied():
    result = build({"roles": [role_reply("exp1", (2, ORIG[1]))]})
    assert [r.company for r in result.roles] == ["Acme", "Initech"]
    assert result.contact.name == "Jane Doe"


def test_role_missing_from_the_reply_falls_back_to_originals_with_a_warning():
    result = build({"roles": [role_reply("exp1", (2, ORIG[1]))]})
    initech = result.roles[1]
    assert [b.original for b in initech.bullets] == PROFILE.experience[1].bullets
    assert any("Engineer" in w and "no usable bullets" in w for w in result.warnings)


# --- rewrite checks -------------------------------------------------------------------------------


def test_harmless_rewording_is_kept_without_flags():
    reworded = "Built a billing API, cutting invoice errors by 40%."
    result = build({"roles": [role_reply("exp1", (2, reworded))]})
    bullet = result.roles[0].bullets[0]
    assert bullet.proposed == reworded
    assert bullet.flags == []


def test_added_number_reverts_the_rewrite():
    result = build({"roles": [role_reply("exp1", (2, "Built a billing API that cut invoice errors by 60%."))]})
    bullet = result.roles[0].bullets[0]
    assert bullet.proposed == bullet.original
    assert bullet.flags[0].kind == "reverted"
    assert "60" in bullet.flags[0].message
    assert any("reverted" in w for w in result.warnings)


def test_keyword_not_anywhere_in_profile_reverts_the_rewrite():
    # Kubernetes is a posting keyword the candidate has not shown: classic keyword stuffing.
    result = build({"roles": [role_reply("exp1", (3, "Led migration of 12 services to Azure Functions and Kubernetes."))]})
    bullet = result.roles[0].bullets[0]
    assert bullet.proposed == bullet.original
    assert "Kubernetes" in bullet.flags[0].message
    assert bullet.flags[0].kind == "reverted"


def test_keyword_from_elsewhere_in_profile_is_flagged_for_review_not_reverted():
    # "Docker" is in the skills list but not in this bullet.
    proposed = "Wrote unit tests for the payments module, run in Docker."
    result = build({"roles": [role_reply("exp1", (4, proposed))]})
    bullet = result.roles[0].bullets[0]
    assert bullet.proposed == proposed
    assert [f.kind for f in bullet.flags] == ["review"]


def test_term_from_a_verified_matched_requirement_is_flagged_not_reverted():
    # The profile never says "message queues", but that requirement was verified as matched,
    # so the rewrite is offered for review instead of being thrown away.
    proposed = "Led migration of 12 services to Azure Functions, using message queues."
    bullet = build({"roles": [role_reply("exp1", (3, proposed))]}).roles[0].bullets[0]
    assert bullet.proposed == proposed
    assert [f.kind for f in bullet.flags] == ["review"]
    assert "message queues" in bullet.flags[0].message


def test_terms_from_missing_requirements_are_still_reverted():
    proposed = "Led migration of 12 services to Azure Functions on Kubernetes."
    bullet = build({"roles": [role_reply("exp1", (3, proposed))]}).roles[0].bullets[0]
    assert bullet.proposed == bullet.original
    assert bullet.flags[0].kind == "reverted"


def test_summary_may_use_verified_requirement_wording_with_a_review_flag():
    text = "Backend engineer with 8 years of experience building billing systems with message queues."
    summary = build({"summary": text}).summary
    assert summary.proposed == text
    assert [f.kind for f in summary.flags] == ["review"]


def test_much_longer_rewrite_is_flagged():
    proposed = "Wrote unit tests for the payments module " + "and also " * 30
    bullet = build({"roles": [role_reply("exp1", (4, proposed))]}).roles[0].bullets[0]
    assert any("longer" in f.message for f in bullet.flags)


def test_unchanged_text_has_no_flags():
    bullet = build({"roles": [role_reply("exp1", (2, ORIG[1]))]}).roles[0].bullets[0]
    assert bullet.proposed == bullet.original
    assert bullet.flags == []


# --- summary --------------------------------------------------------------------------------------


def test_supported_summary_is_proposed():
    text = "Backend engineer with 8 years of experience building billing systems in C# and Azure Functions."
    summary = build({"summary": text}).summary
    assert summary.proposed == text
    assert summary.original == PROFILE.summary
    assert summary.flags == []


def test_summary_with_unsupported_claims_keeps_the_original():
    result = build({"summary": "Kubernetes expert with 15 years of experience."})
    assert result.summary.proposed == PROFILE.summary
    assert {f.kind for f in result.summary.flags} == {"reverted"}
    assert any("summary" in w for w in result.warnings)


def test_empty_summary_reply_keeps_the_original():
    assert build({"summary": ""}).summary.proposed == PROFILE.summary


# --- skills ---------------------------------------------------------------------------------------


def test_skills_are_limited_to_the_profile_with_canonical_spelling():
    result = build(
        {
            "skills": [
                {"category": "cloud", "items": ["azure functions", "Kubernetes", "terraform"]},
                {"category": "Languages", "items": ["c#", "C#", "Rust"]},
            ]
        }
    )
    assert [(g.category, g.items) for g in result.skills] == [
        ("Cloud", ["Azure Functions"]),
        ("Languages", ["C#"]),
    ]
    assert any("3 skill(s)" in w for w in result.warnings)


def test_no_usable_skills_falls_back_to_the_profile_skills():
    result = build({"skills": [{"category": "X", "items": ["Kubernetes"]}]})
    assert [g.category for g in result.skills] == ["Languages", "Cloud"]


# --- API ------------------------------------------------------------------------------------------


@pytest.fixture
def ready(client, auth, store):
    store.set("sk-test")
    client.put("/settings", headers=auth, json={"model": "default/model", "rewrite_model": "writer/model"})
    return client


def payload(length="standard"):
    return {"analysis": ANALYSIS.model_dump(), "length": length}


def test_tailor_requires_token(client):
    assert client.post("/jobs/tailor", json=payload()).status_code == 401


def test_tailor_needs_a_saved_profile(ready, auth):
    response = ready.post("/jobs/tailor", headers=auth, json=payload())
    assert response.status_code == 400
    assert "master profile" in response.json()["detail"]


def test_tailor_needs_an_analysed_posting(ready, auth):
    store.save_profile(PROFILE)
    empty = AnalysisResult(job=JobAnalysis(), matches=[], keywords=KeywordCheck(), scores=Scores())
    response = ready.post("/jobs/tailor", headers=auth, json={"analysis": empty.model_dump()})
    assert response.status_code == 422


def test_tailor_end_to_end_uses_the_rewrite_model(ready, auth, monkeypatch):
    store.save_profile(PROFILE)
    seen = {}

    async def fake(**kwargs):
        seen["model"] = kwargs["model"]
        seen["user"] = kwargs["user"]
        return kwargs["schema"].model_validate(
            {
                "summary": "Backend engineer with 8 years of experience building billing systems.",
                "roles": [role_reply("exp1", (2, ORIG[1]), (3, ORIG[2]))],
                "skills": [{"category": "Languages", "items": ["C#", "SQL"]}],
            }
        )

    monkeypatch.setattr(llm, "complete_json", fake)
    response = ready.post("/jobs/tailor", headers=auth, json=payload("concise"))

    assert response.status_code == 200
    data = response.json()
    assert seen["model"] == "writer/model"
    assert "keep at most 4 bullets" in seen["user"]
    assert [b["source"] for b in data["roles"][0]["bullets"]] == [2, 3]
    assert data["skills"][0]["items"] == ["C#", "SQL"]
    assert data["summary"]["proposed"].startswith("Backend engineer")


def test_tailor_model_failure_is_a_502(ready, auth, monkeypatch):
    store.save_profile(PROFILE)

    async def boom(**kwargs):
        raise llm.LlmError("The model server returned an error (500).")

    monkeypatch.setattr(llm, "complete_json", boom)
    assert ready.post("/jobs/tailor", headers=auth, json=payload()).status_code == 502
