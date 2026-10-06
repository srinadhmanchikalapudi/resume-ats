from datetime import date

from app.jobs import scoring
from app.jobs.models import JobAnalysis, Requirement, RequirementMatch
from app.profile.models import Profile

TODAY = date(2026, 10, 6)


def role(start, end="", current=False):
    return {"title": "Dev", "start": start, "end": end, "current": current}


def profile_with(*roles):
    return Profile.model_validate({"experience": list(roles)})


def match(importance, status, text="x"):
    requirement = Requirement(id="r", text=text, importance=importance)
    return RequirementMatch(requirement=requirement, status=status)


# --- years ------------------------------------------------------------------------------------


def test_years_for_a_single_dated_role():
    assert scoring.candidate_years(profile_with(role("January 2020", "January 2023")), TODAY) == 3.0


def test_current_role_runs_to_today():
    years = scoring.candidate_years(profile_with(role("Aug 2024", current=True)), TODAY)
    assert years == 2.2  # Aug 2024 -> Oct 2026 = 26 months


def test_overlapping_roles_are_counted_once():
    years = scoring.candidate_years(
        profile_with(role("2018", "2022"), role("2020", "2023")), TODAY
    )
    assert years == 5.0  # 2018 -> 2023, not 4 + 3


def test_gaps_are_not_counted():
    years = scoring.candidate_years(
        profile_with(role("Jan 2016", "Jan 2018"), role("Jan 2020", "Jan 2022")), TODAY
    )
    assert years == 4.0


def test_slash_and_year_only_dates_parse():
    assert scoring.candidate_years(profile_with(role("03/2019", "03/2021")), TODAY) == 2.0
    assert scoring.candidate_years(profile_with(role("2016", "2018")), TODAY) == 2.0


def test_undatable_profile_returns_none():
    assert scoring.candidate_years(profile_with(role("sometime", "later")), TODAY) is None
    assert scoring.candidate_years(Profile(), TODAY) is None


# --- scores -----------------------------------------------------------------------------------


def test_overall_score_is_weighted_by_importance():
    job = JobAnalysis(years_required=None)
    matches = [
        match("required", "matched"),  # 3 of 3
        match("required", "missing"),  # 0 of 3
        match("preferred", "partial"),  # 0.75 of 1.5
        match("nice", "matched"),  # 0.5 of 0.5
    ]
    scores = scoring.compute_scores(job, matches, years=None)
    # (3 + 0 + 0.75 + 0.5) / (3 + 3 + 1.5 + 0.5) = 4.25 / 8
    assert scores.overall == 53
    assert (scores.required_total, scores.required_matched, scores.required_missing) == (2, 1, 1)


def test_unverified_counts_as_missing_for_required_totals():
    scores = scoring.compute_scores(JobAnalysis(), [match("required", "unverified")], years=None)
    assert scores.overall == 0
    assert scores.required_missing == 1


def test_no_requirements_gives_no_score():
    assert scoring.compute_scores(JobAnalysis(), [], years=3.0).overall is None


def test_years_gap_is_reported_only_when_short():
    short = scoring.compute_scores(JobAnalysis(years_required=8), [], years=6.5)
    assert short.years_short_by == 1.5
    enough = scoring.compute_scores(JobAnalysis(years_required=5), [], years=6.5)
    assert enough.years_short_by is None
    unknown = scoring.compute_scores(JobAnalysis(years_required=5), [], years=None)
    assert unknown.years_short_by is None


# --- keyword check ----------------------------------------------------------------------------


def test_keyword_check_matches_literal_terms_with_symbols():
    job = JobAnalysis(keywords=["C#", ".NET", "Node.js", "Kubernetes", "SQL"])
    text = "Built APIs in C# on .NET 8 with SQL Server. Some Node.js tooling."
    result = scoring.check_keywords(job, text)
    assert result.present == ["C#", ".NET", "Node.js", "SQL"]
    assert result.missing == ["Kubernetes"]


def test_keyword_check_respects_word_boundaries_and_case():
    job = JobAnalysis(keywords=["Go", "java", "React"])
    text = "Experienced with JavaScript and Django; used JAVA daily; ported React apps."
    result = scoring.check_keywords(job, text)
    assert result.present == ["java", "React"]  # "Go" must not match inside "Django"
    assert result.missing == ["Go"]


def test_keyword_check_accepts_a_plural_form():
    job = JobAnalysis(keywords=["Azure App Service", "Microservice"])
    result = scoring.check_keywords(job, "Hosted on Azure App Services; split into microservices.")
    assert result.present == ["Azure App Service", "Microservice"]


def test_keyword_terms_are_cleaned_and_descriptions_dropped():
    assert scoring.clean_term("Angular (v12+)") == "Angular"
    assert scoring.clean_term("  .NET   Core (LTS) ") == ".NET Core"
    job = JobAnalysis(
        keywords=[
            "Angular (v12+)",
            "angular",
            "Experience building scalable distributed systems in production",
            "x" * 50,
        ]
    )
    result = scoring.check_keywords(job, "Used Angular daily")
    assert result.present == ["Angular"]
    assert result.missing == []


def test_keyword_check_includes_requirement_keywords_without_duplicates():
    job = JobAnalysis(
        keywords=["Azure"],
        requirements=[Requirement(id="r1", text="x", keywords=["azure", "Terraform"])],
    )
    result = scoring.check_keywords(job, "azure only")
    assert result.present == ["Azure"]
    assert result.missing == ["Terraform"]
