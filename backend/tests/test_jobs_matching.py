from app.jobs import analyzer, matcher
from app.jobs.models import EvidenceIn, JobAnalysis, MatchIn, MatchItemIn
from app.jobs.profile_index import build_index, normalize, quote_is_in, render_for_prompt
from app.profile.models import Profile

PROFILE = Profile.model_validate(
    {
        "summary": "Backend engineer building billing systems.",
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "start": "2020",
                "current": True,
                "bullets": [
                    "Built a billing API that cut invoice errors by 40%.",
                    "Led migration of 12 services to Azure Functions.",
                ],
            }
        ],
        "skills": [{"category": "Languages", "items": ["Python", "C#"]}],
    }
)
JOB = JobAnalysis.model_validate(
    {
        "title": "Backend Engineer",
        "requirements": [
            {"text": "Experience with serverless", "importance": "required", "keywords": ["serverless"]},
            {"text": "Kubernetes in production", "importance": "required"},
            {"text": "Knows Python", "importance": "preferred"},
        ],
    }
)
ENTRIES = build_index(PROFILE)


def verdict(requirement_id, status, *evidence, note=""):
    return MatchItemIn(
        requirement_id=requirement_id,
        status=status,
        evidence=[EvidenceIn(ref=r, quote=q) for r, q in evidence],
        note=note,
    )


# --- profile index ----------------------------------------------------------------------------


def test_index_has_stable_short_refs_and_labels():
    refs = {entry.ref: entry.label for entry in ENTRIES}
    assert refs == {"summary": "Summary", "exp1": "Senior Engineer at Acme", "skills": "Skills"}


def test_prompt_rendering_shows_refs_headings_and_bullets():
    rendered = render_for_prompt(ENTRIES)
    assert "[exp1] Senior Engineer at Acme (2020 - Present)" in rendered
    assert "- Led migration of 12 services to Azure Functions." in rendered
    assert "[skills] Skills" in rendered
    assert "- Languages: Python, C#" in rendered


def test_quote_matching_ignores_case_spacing_and_dash_style():
    experience = next(e for e in ENTRIES if e.ref == "exp1")
    assert quote_is_in("led migration  of 12 services to AZURE functions", experience)
    assert quote_is_in("Senior Engineer at Acme (2020 – Present)", experience)
    assert not quote_is_in("Led migration of 40 services to Azure Functions", experience)
    assert not quote_is_in("x", experience)  # too short to mean anything
    assert normalize("  A’s  B ") == "a's b"


# --- verification -----------------------------------------------------------------------------


def test_verified_evidence_keeps_the_match():
    reply = MatchIn(
        matches=[
            verdict("r1", "matched", ("exp1", "migration of 12 services to Azure Functions"), note="ok"),
            verdict("r2", "missing"),
            verdict("r3", "matched", ("skills", "Python")),
        ]
    )
    results, warnings = matcher.verify_matches(JOB, ENTRIES, reply)
    assert [r.status for r in results] == ["matched", "missing", "matched"]
    assert results[0].evidence[0].label == "Senior Engineer at Acme"
    assert warnings == []


def test_invented_quote_downgrades_to_unverified():
    reply = MatchIn(
        matches=[
            verdict("r1", "matched", ("exp1", "Deployed Lambda functions at scale")),
            verdict("r2", "missing"),
            verdict("r3", "missing"),
        ]
    )
    results, warnings = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[0].status == "unverified"
    assert results[0].evidence == []
    assert "not found in your profile" in results[0].note
    assert any("could not be verified" in w for w in warnings)


def test_quote_cited_against_the_wrong_entry_is_rejected():
    reply = MatchIn(
        matches=[
            verdict("r1", "matched", ("skills", "Azure Functions")),
            verdict("r2", "missing"),
            verdict("r3", "missing"),
        ]
    )
    results, _ = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[0].status == "unverified"


def test_unknown_ref_is_rejected():
    reply = MatchIn(matches=[verdict("r3", "matched", ("exp9", "Python"))])
    results, _ = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[2].status == "unverified"


def test_partial_with_some_valid_evidence_stays_partial_and_drops_bad_quotes():
    reply = MatchIn(
        matches=[
            verdict(
                "r1",
                "partial",
                ("exp1", "Azure Functions"),
                ("exp1", "invented words that are not there"),
            ),
        ]
    )
    results, _ = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[0].status == "partial"
    assert [e.quote for e in results[0].evidence] == ["Azure Functions"]


def test_missing_verdict_ignores_any_evidence_the_model_attached():
    reply = MatchIn(matches=[verdict("r2", "missing", ("exp1", "Azure Functions"))])
    results, _ = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[1].status == "missing"
    assert results[1].evidence == []


def test_requirements_the_model_skipped_are_reported_and_shown_missing():
    results, warnings = matcher.verify_matches(JOB, ENTRIES, MatchIn(matches=[]))
    assert [r.status for r in results] == ["missing"] * 3
    assert any("skipped 3" in w for w in warnings)


def test_duplicate_verdicts_use_the_first():
    reply = MatchIn(
        matches=[
            verdict("r3", "matched", ("skills", "Python")),
            verdict("r3", "missing"),
        ]
    )
    results, _ = matcher.verify_matches(JOB, ENTRIES, reply)
    assert results[2].status == "matched"


# --- lenient parsing of model output ----------------------------------------------------------


def test_job_analysis_normalises_messy_model_output():
    job = JobAnalysis.model_validate(
        {
            "title": None,
            "years_required": "5+ years",
            "keywords": "C#, .NET",
            "requirements": [
                {"text": "A", "category": "Programming", "importance": "must-have"},
                {"text": "", "importance": "required"},
                {"text": "B", "importance": "bonus"},
                {"text": "C"},
            ],
        }
    )
    assert job.years_required == 5
    assert job.keywords == ["C#", ".NET"]
    assert [r.id for r in job.requirements] == ["r1", "r2", "r3"]  # blank requirement dropped
    assert [r.category for r in job.requirements] == ["other", "other", "other"]
    assert [r.importance for r in job.requirements] == ["required", "nice", "preferred"]


def test_match_status_synonyms_and_unknowns():
    reply = MatchIn.model_validate(
        {
            "matches": [
                {"requirement_id": "r1", "status": "Yes"},
                {"requirement_id": "r2", "status": "partially"},
                {"requirement_id": "r3", "status": "no idea"},
            ]
        }
    )
    assert [m.status for m in reply.matches] == ["matched", "partial", "missing"]


def test_analyzer_prompt_guards_against_injection():
    assert "untrusted" in analyzer.SYSTEM_PROMPT
    assert "untrusted" in matcher.SYSTEM_PROMPT
