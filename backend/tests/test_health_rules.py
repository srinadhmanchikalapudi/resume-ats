import pytest

from app.health import rules
from app.health.lexicon import STRONG_FORMS, verb_forms


@pytest.mark.parametrize(
    "text",
    [
        "Cut invoice errors by 40% across all regions.",
        "Reduced cloud spend by $1.2M a year.",
        "Served 12 services with a shared platform.",
        "Handled 10k users at peak load.",
        "Made reports 3x faster with caching.",
        "Reduced deployment time from 4 hours to 20 minutes.",
        "Supported eight trust funds with independent rules.",
        "Mentored 5 junior engineers.",
        "Processed 2,000,000 transactions a day.",
        "Ran 12 regional teams through the migration.",
        "Supported 8 trust funds, each with independent rules.",
        "Managed 4 data centers across 2 regions.",
        "Served 2,000 analysts every morning.",
    ],
)
def test_real_quantities_count_as_metrics(text):
    assert rules.has_metric(text)


@pytest.mark.parametrize(
    "text",
    [
        "Built APIs using .NET 6 and C# 10.",
        "Developed an Angular 12 front end with TypeScript.",
        "Maintained ASP.NET Core 3.1/5 services on Windows Server 2019.",
        "Worked with Azure and SQL Server 2019 on the platform team.",
        "Enhanced the .NET 6 background job services for claim ingestion.",
        "Wrote ES6 modules and Bootstrap 5 layouts.",
        "Designed a distributed caching layer.",
        "Implemented ISO 27001 controls for the platform.",
        "Used TLS 1.2 connections between services.",
        "Hosted databases on Windows Server 2019 machines.",
        "Achieved SOC 2 compliance for the company.",
        "Followed Tier 2 escalation procedures.",
        "Encrypted data with AES-256 encryption keys.",
    ],
)
def test_version_numbers_and_plain_text_are_not_metrics(text):
    assert not rules.has_metric(text)


def test_verb_forms_are_generated_for_regular_and_irregular_verbs():
    assert {"build", "built", "led", "lead", "ran", "wrote"} <= STRONG_FORMS.keys()
    assert STRONG_FORMS["built"] == "build" and STRONG_FORMS["led"] == "lead"
    assert STRONG_FORMS["planned"] == "plan"  # doubled consonant
    assert STRONG_FORMS["modernized"] == "modernize"
    assert STRONG_FORMS["identifies"] == "identify" or "identified" in STRONG_FORMS
    assert "planned" in verb_forms("plan")


def test_opening_verb_returns_the_base_form():
    assert rules.opening_verb("Built a billing API.") == "build"
    assert rules.opening_verb("Led a migration.") == "lead"
    assert rules.opening_verb("Reduced costs.") == "reduce"
    assert rules.opening_verb("Zorbed the thing.") == "zorbed"  # unknown words are returned as written


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Built a billing API.", "strong"),
        ("Joined the platform team and shipped features.", "ok"),
        ("Responsible for the billing system.", "weak"),
        ("Helped the team with deployments.", "weak"),
        ("Worked on internal tools.", "weak"),
        ("Experience with cloud platforms.", "weak"),
        ("Developing new features.", "weak"),
        ("Was in charge of releases.", "weak"),
    ],
)
def test_verb_class(text, expected):
    assert rules.verb_class(text) == expected


def test_weak_opener_explains_itself():
    assert "duty" in rules.weak_opener("Responsible for the billing system.")
    assert rules.weak_opener("Built the billing system.") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Costs were reduced by 20% after the change.", True),
        ("The code was reviewed by two engineers.", True),
        ("Reduced costs by 20%.", False),
        ("Wrote reports that are used by finance.", True),
        ("Designed an open API based on REST.", False),
    ],
)
def test_passive_voice(text, expected):
    assert rules.is_passive(text) is expected


def test_sentence_count():
    assert rules.sentence_count("Built an API.") == 1
    assert rules.sentence_count("Built an API. Cut errors by 40%.") == 2


def test_fluff_and_buzzwords_match_whole_phrases_only():
    assert set(rules.fluff_hits("Successfully delivered various projects etc.")) == {"various", "etc", "successfully"}
    assert rules.fluff_hits("Built a variance report.") == []  # "various" must not match inside "variance"
    assert set(rules.buzzword_hits("Leveraged a robust, seamless pipeline.")) == {"leveraged", "robust", "seamless"}
    assert rules.buzzword_hits("Used a reliable pipeline.") == []


def test_first_person_pronouns():
    assert rules.first_person_hits("I built the API and my team shipped it.") == ["I", "my"]
    assert rules.first_person_hits("Built the API.") == []


def test_generic_versus_specific_lines():
    assert rules.is_generic("Worked with the team to deliver good results for customers.")
    assert not rules.is_generic("Built a billing API in C# on Azure.")
    assert not rules.is_generic("Reduced load times by half.")  # a relative quantity is still specific
    assert not rules.is_generic("Migrated 12 legacy services.")


def test_specific_tokens_find_technologies_and_names():
    found = rules.specific_tokens("Built a billing API with C# and ASP.NET Core on Azure for Globex.")
    assert {"C#", "ASP.NET", "Azure", "Globex"} <= set(found)
    assert rules.specific_tokens("Built the thing for the team") == []


def test_similarity_detects_rewording_but_not_unrelated_lines():
    a = "Built a billing API that cut invoice errors by 40%."
    b = "Built a billing API which cut invoice errors by forty percent."
    assert rules.similarity(a, b) >= 0.6
    assert rules.similarity(a, "Mentored junior engineers on testing practices.") < 0.2
    assert rules.similarity("", a) == 0.0


def test_metric_hint_is_tailored_to_the_verb():
    assert "By how much" in rules.metric_hint("Optimized database queries.")
    assert "people" in rules.metric_hint("Mentored engineers.")
    assert "Add a number" in rules.metric_hint("Zorbed things.")


def test_technology_lists_are_recognised_and_ordinary_bullets_are_not():
    assert rules.is_tech_list("Environment: C# 10, .NET 6, ASP.NET Core, SQL Server")
    assert rules.is_tech_list("Tech stack: Python, Postgres")
    assert not rules.is_tech_list("Built a tool: it cut errors by 40%.")
    assert not rules.is_tech_list("Environments were migrated to Azure.")


def test_irregular_past_tense_openers_are_acceptable():
    assert rules.verb_class("Took ownership of the claims portal and its dashboards.") == "ok"
    assert rules.verb_class("Held weekly design reviews with five teams.") == "ok"
