from datetime import datetime

from app.health.analyzer import WEIGHTS, analyze
from app.profile.models import Profile

TODAY = datetime(2026, 10, 6).astimezone()

GOOD = Profile.model_validate(
    {
        "contact": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-0100",
            "location": "Austin, TX",
            "links": [{"label": "LinkedIn", "url": "linkedin.com/in/janedoe"}],
        },
        "summary": "Backend engineer with 8 years of experience building billing systems in C# on Azure.",
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "start": "January 2021",
                "current": True,
                "bullets": [
                    "Built a billing API in C# that cut invoice errors by 40% across 12 regions.",
                    "Led migration of 12 services to Azure Functions, saving 30 hours of deploy work a month.",
                    "Reduced p95 latency from 900 ms to 220 ms by adding Redis caching.",
                    "Mentored 4 engineers through promotion to senior.",
                ],
            },
            {
                "title": "Engineer",
                "company": "Initech",
                "start": "March 2017",
                "end": "December 2020",
                "bullets": [
                    "Designed a reporting platform on SQL Server serving 2,000 analysts.",
                    "Automated 15 manual finance reports with Python, freeing 20 hours a week.",
                ],
            },
        ],
        "skills": [{"category": "Languages", "items": ["C#", "Python", "SQL"]}],
        "education": [{"school": "UT Austin", "degree": "BS", "field": "Computer Science", "start": "2013", "end": "2017"}],
    }
)

WEAK = Profile.model_validate(
    {
        "contact": {"name": "Sam"},
        "summary": "I am a passionate, results-driven team player with a proven track record.",
        "experience": [
            {
                "title": "Developer",
                "company": "Acme",
                "bullets": [
                    "Responsible for the billing system.",
                    "Worked on various projects and helped the team with many things.",
                    (
                        "Was involved in the deployment of the application to production environments in order to "
                        "support the business and its customers across various departments and regions successfully "
                        "and to leverage robust seamless innovative tooling in a fast-paced environment."
                    ),
                    "The code was reviewed and bugs were fixed by me.",
                    "Utilized best practices to leverage a robust approach.",
                ],
            }
        ],
    }
)


def rules_of(report):
    return {f.rule: f for category in report.categories for f in category.findings}


def category(report, key):
    return next(c for c in report.categories if c.key == key)


# --- overall behaviour ------------------------------------------------------------------------------


def test_a_strong_resume_scores_well_and_a_weak_one_does_not():
    good, weak = analyze(GOOD, TODAY), analyze(WEAK, TODAY)
    assert good.overall >= 85 and good.band == "Strong"
    assert weak.overall < 50 and weak.band == "Weak"
    assert good.overall > weak.overall + 40


def test_report_has_five_weighted_categories():
    report = analyze(GOOD, TODAY)
    assert [c.key for c in report.categories] == ["impact", "verbs", "clarity", "specificity", "completeness"]
    assert sum(c.weight for c in report.categories) == sum(WEIGHTS.values()) == 100
    assert all(0 <= c.score <= 100 for c in report.categories)


def test_the_same_input_always_gives_the_same_report():
    assert analyze(WEAK, TODAY).model_dump() == analyze(WEAK, TODAY).model_dump()


def test_stats_describe_the_resume():
    report = analyze(GOOD, TODAY)
    assert report.stats.bullets == 6
    assert report.stats.with_metric == 6
    assert report.stats.metric_rate == 1.0
    assert report.stats.strong_verb_bullets == 6
    assert report.stats.weak_opener_bullets == 0


def test_top_fixes_are_the_most_serious_and_capped_at_five():
    report = analyze(WEAK, TODAY)
    assert 1 <= len(report.top_fixes) <= 5
    assert report.top_fixes[0] == next(f.title for c in report.categories for f in c.findings if f.severity == "high")


def test_an_empty_resume_does_not_crash_and_scores_low():
    report = analyze(Profile(), TODAY)
    assert report.overall < 35
    assert "no_experience" in rules_of(report)
    assert category(report, "impact").summary == "No bullets to assess yet."


# --- findings on the weak resume --------------------------------------------------------------------


def test_weak_resume_triggers_the_expected_findings():
    found = rules_of(analyze(WEAK, TODAY))
    for rule in (
        "no_metric", "weak_opener", "passive_voice", "too_long", "filler", "buzzwords", "first_person",
        "generic_bullet", "summary_fluff", "no_email", "no_phone", "no_skills", "undated_role",
    ):  # fmt: skip
        assert rule in found, rule
    assert found["no_metric"].severity == "high"
    assert found["no_email"].severity == "high"


def test_metric_findings_give_a_question_to_answer_not_a_made_up_number():
    finding = rules_of(analyze(WEAK, TODAY))["no_metric"]
    assert finding.count == 5
    assert all(example.hint for example in finding.examples)
    assert all("%" not in example.hint and not any(ch.isdigit() for ch in example.hint) for example in finding.examples)


def test_examples_are_capped_and_say_where_they_are():
    big = WEAK.model_copy(deep=True)
    big.experience[0].bullets = [f"Responsible for item number {i}." for i in range(12)]
    finding = rules_of(analyze(big, TODAY))["weak_opener"]
    assert finding.count == 12 and len(finding.examples) == 6
    assert finding.examples[0].where == "Developer at Acme, bullet 1"


def test_repeated_verbs_are_reported_once_they_are_overused():
    profile = GOOD.model_copy(deep=True)
    profile.experience[0].bullets = [f"Developed feature {n} in C# for 12 customers." for n in range(5)]
    found = rules_of(analyze(profile, TODAY))
    assert "repeated_verb" in found
    assert "develop" in found["repeated_verb"].examples[0].where.lower() or "Developed" in found["repeated_verb"].examples[0].where


def test_strong_resume_has_no_high_severity_findings():
    report = analyze(GOOD, TODAY)
    assert [f.rule for c in report.categories for f in c.findings if f.severity in {"high", "medium"}] == []


# --- completeness and consistency -------------------------------------------------------------------


def test_mixed_date_styles_are_flagged_but_may_is_neutral():
    profile = GOOD.model_copy(deep=True)
    profile.experience[0].start = "Jan 2021"  # abbreviated, while the other roles use full month names
    found = rules_of(analyze(profile, TODAY))
    assert "date_style" in found

    consistent = GOOD.model_copy(deep=True)
    consistent.experience[1].end = "May 2020"  # May reads the same either way
    assert "date_style" not in rules_of(analyze(consistent, TODAY))


def test_roles_must_be_newest_first():
    profile = GOOD.model_copy(deep=True)
    profile.experience.reverse()
    assert "not_reverse_chronological" in rules_of(analyze(profile, TODAY))
    assert "not_reverse_chronological" not in rules_of(analyze(GOOD, TODAY))


def test_a_gap_between_roles_is_reported():
    profile = GOOD.model_copy(deep=True)
    profile.experience[1].end = "June 2019"  # leaves July 2019 to January 2021
    gaps = rules_of(analyze(profile, TODAY))["employment_gap"]
    assert gaps.severity == "info"
    assert "months" in gaps.examples[0].where


def test_a_gap_explained_by_education_is_not_reported():
    profile = GOOD.model_copy(deep=True)
    profile.experience[1].end = "June 2019"
    profile.education[0].start = "July 2019"
    profile.education[0].end = "December 2020"
    assert "employment_gap" not in rules_of(analyze(profile, TODAY))


def test_short_breaks_are_not_gaps():
    profile = GOOD.model_copy(deep=True)
    profile.experience[1].end = "October 2020"  # three months
    assert "employment_gap" not in rules_of(analyze(profile, TODAY))


def test_near_duplicate_bullets_are_found():
    profile = GOOD.model_copy(deep=True)
    profile.experience[1].bullets.append("Built a billing API in C# that cut invoice errors by 40% across 12 regions today.")
    found = rules_of(analyze(profile, TODAY))
    assert found["duplicate_bullets"].severity == "medium"
    assert "Senior Engineer" in found["duplicate_bullets"].examples[0].where


def test_missing_contact_details_and_sections_are_graded_by_importance():
    profile = GOOD.model_copy(deep=True)
    profile.contact.email = ""
    profile.contact.links = []
    profile.summary = ""
    found = rules_of(analyze(profile, TODAY))
    assert found["no_email"].severity == "high"
    assert found["no_linkedin"].severity == "info"
    assert found["no_summary"].severity == "low"
    assert category(analyze(profile, TODAY), "completeness").score < category(analyze(GOOD, TODAY), "completeness").score


def test_a_very_long_skills_list_and_resume_are_noted():
    profile = GOOD.model_copy(deep=True)
    profile.skills[0].items = [f"Skill{n}" for n in range(70)]
    assert "long_skills" in rules_of(analyze(profile, TODAY))


def test_scores_stay_between_zero_and_one_hundred_for_extreme_input():
    awful = WEAK.model_copy(deep=True)
    awful.experience[0].bullets = ["I was responsible for various things etc."] * 30
    report = analyze(awful, TODAY)
    assert 0 <= report.overall <= 100
    assert all(0 <= c.score <= 100 for c in report.categories)


# --- endpoint ---------------------------------------------------------------------------------------


def test_health_endpoint_requires_a_token_and_returns_a_report(client, auth):
    assert client.post("/health-check", json={"profile": GOOD.model_dump()}).status_code == 401
    response = client.post("/health-check", headers=auth, json={"profile": GOOD.model_dump()})
    assert response.status_code == 200
    data = response.json()
    assert data["band"] == "Strong"
    assert len(data["categories"]) == 5
    assert data["stats"]["bullets"] == 6


def test_health_endpoint_accepts_an_empty_profile(client, auth):
    response = client.post("/health-check", headers=auth, json={"profile": Profile().model_dump()})
    assert response.status_code == 200
    assert response.json()["overall"] < 35


def test_technology_lists_are_not_scored_as_bullets():
    profile = GOOD.model_copy(deep=True)
    profile.experience[0].bullets.append("Environment: C# 10, .NET 6, ASP.NET Core, SQL Server, Azure, Redis")
    before, after = analyze(GOOD, TODAY), analyze(profile, TODAY)
    assert after.stats.bullets == before.stats.bullets
    assert after.overall == before.overall


def test_finding_titles_read_correctly_for_one_and_for_many():
    one = GOOD.model_copy(deep=True)
    one.experience[0].bullets[0] = "Costs were reduced by 20% after the change."
    title = rules_of(analyze(one, TODAY))["passive_voice"].title
    assert title == "Passive voice in 1 bullet"

    many = GOOD.model_copy(deep=True)
    many.experience[0].bullets[:2] = ["Costs were reduced by 20% after the change.", "Bugs were fixed by 3 engineers quickly."]
    assert rules_of(analyze(many, TODAY))["passive_voice"].title == "Passive voice in 2 bullets"
