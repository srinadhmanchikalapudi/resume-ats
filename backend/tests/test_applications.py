from pathlib import Path

import pytest

from app.applications import files, store
from app.db import connect
from app.jobs.models import AnalysisResult, JobAnalysis, KeywordCheck, Scores
from app.profile.models import Profile

POSTING = (
    "Senior Backend Engineer at Globex. Remote. You will build billing APIs with C# and .NET. "
    "Requirements: 5+ years of C#, Azure experience, Kubernetes in production."
)

ANALYSIS = AnalysisResult(
    job=JobAnalysis.model_validate(
        {"title": "Senior Backend Engineer", "company": "Globex", "location": "Remote", "keywords": ["C#"]}
    ),
    matches=[],
    keywords=KeywordCheck(),
    scores=Scores(overall=62),
)

PROFILE = Profile.model_validate(
    {
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "experience": [{"title": "Engineer", "company": "Acme", "start": "2020", "current": True, "bullets": ["Built APIs."]}],
    }
)


@pytest.fixture
def make(client, auth):
    def create(text=POSTING, **extra):
        body = {"posting_text": text, "analysis": ANALYSIS.model_dump(), **extra}
        response = client.post("/applications", headers=auth, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    return create


def export(client, auth, app_id):
    response = client.post("/export", headers=auth, json={"profile": PROFILE.model_dump(), "application_id": app_id})
    assert response.status_code == 200, response.text
    return response.json()


# --- create -----------------------------------------------------------------------------------------


def test_create_takes_details_from_the_analysis_and_writes_the_folder(make):
    app = make()
    assert (app["company"], app["title"], app["location"]) == ("Globex", "Senior Backend Engineer", "Remote")
    assert app["status"] == "saved"
    assert app["match_score"] == 62
    assert app["already_saved"] is False
    assert [h["status"] for h in app["history"]] == ["saved"]
    assert app["analysis"]["scores"]["overall"] == 62

    folder = Path(app["folder"])
    assert folder.name.endswith("_Globex_Senior-Backend-Engineer")
    assert (folder / "posting.txt").read_text(encoding="utf-8") == POSTING
    assert '"overall": 62' in (folder / "analysis.json").read_text(encoding="utf-8")


def test_explicit_fields_override_the_analysis(make):
    app = make(company="Initech", title="Staff Engineer", job_url="https://example.com/job/1")
    assert (app["company"], app["title"], app["job_url"]) == ("Initech", "Staff Engineer", "https://example.com/job/1")


def test_create_without_an_analysis_still_saves(client, auth):
    response = client.post("/applications", headers=auth, json={"posting_text": POSTING, "company": "Acme"})
    assert response.status_code == 200
    assert response.json()["analysis"] is None
    assert response.json()["match_score"] is None


def test_short_posting_is_rejected(client, auth):
    assert client.post("/applications", headers=auth, json={"posting_text": "too short"}).status_code == 422


def test_saving_the_same_posting_again_returns_the_existing_record(make, client, auth):
    first = make()
    again = make(text="  " + POSTING.upper().replace("  ", " ") + "\n")
    assert again["id"] == first["id"]
    assert again["already_saved"] is True
    assert len(client.get("/applications", headers=auth).json()) == 1


def test_two_applications_to_the_same_company_get_separate_folders(make):
    one = make()
    two = make(text=POSTING + " A different role.")
    assert one["folder"] != two["folder"]


def test_endpoints_require_token(client):
    assert client.get("/applications").status_code == 401
    assert client.post("/applications", json={"posting_text": POSTING}).status_code == 401


# --- list and search --------------------------------------------------------------------------------


def test_list_is_most_recently_updated_first(make, client, auth):
    first = make(company="Alpha")
    second = make(text=POSTING + " second", company="Beta")
    client.patch(f"/applications/{first['id']}", headers=auth, json={"notes": "touched"})
    assert [a["company"] for a in client.get("/applications", headers=auth).json()] == ["Alpha", "Beta"]
    assert second["id"] != first["id"]


def test_search_matches_company_title_notes_and_posting_text(make, client, auth):
    one = make(company="Alpha Bank", title="Platform Engineer")
    two = make(text="Totally different posting about Rust and embedded systems at a robotics firm.", company="Beta Robotics")
    client.patch(f"/applications/{two['id']}", headers=auth, json={"notes": "Recruiter is Dana"})

    def found(query):
        return sorted(a["id"] for a in client.get("/applications", headers=auth, params={"q": query}).json())

    assert found("alpha") == [one["id"]]
    assert found("platform") == [one["id"]]
    assert found("embedded") == [two["id"]]
    assert found("dana") == [two["id"]]
    assert found("kubernetes") == [one["id"]]  # only in the first posting
    assert found("alpha dana") == []  # every word must match
    assert found("") == sorted([one["id"], two["id"]])


def test_search_treats_percent_and_underscore_literally(make, client, auth):
    make(company="Alpha")
    other = make(text=POSTING + " 100% remote", company="Beta")
    assert [a["id"] for a in client.get("/applications", headers=auth, params={"q": "100%"}).json()] == [other["id"]]
    assert client.get("/applications", headers=auth, params={"q": "_"}).json() == []


def test_status_filter(make, client, auth):
    one = make(company="Alpha")
    make(text=POSTING + " b", company="Beta")
    client.patch(f"/applications/{one['id']}", headers=auth, json={"status": "interviewing"})
    result = client.get("/applications", headers=auth, params={"status": "interviewing"}).json()
    assert [a["company"] for a in result] == ["Alpha"]


def test_sort_by_interview_puts_upcoming_first_then_the_rest(make, client, auth):
    soon = make(company="Soon")
    later = make(text=POSTING + " later", company="Later")
    past = make(text=POSTING + " past", company="Past")
    make(text=POSTING + " none", company="None")  # no interview date at all
    client.patch(f"/applications/{soon['id']}", headers=auth, json={"interview_on": "2099-01-01"})
    client.patch(f"/applications/{later['id']}", headers=auth, json={"interview_on": "2099-06-01"})
    client.patch(f"/applications/{past['id']}", headers=auth, json={"interview_on": "2000-01-01"})
    order = [a["company"] for a in client.get("/applications", headers=auth, params={"sort": "interview"}).json()]
    assert order[:2] == ["Soon", "Later"]
    assert set(order[2:]) == {"Past", "None"}


def test_sort_by_company(make, client, auth):
    make(company="beta")
    make(text=POSTING + " x", company="Alpha")
    names = [a["company"] for a in client.get("/applications", headers=auth, params={"sort": "company"}).json()]
    assert names == ["Alpha", "beta"]


# --- detail and update ------------------------------------------------------------------------------


def test_get_unknown_application_is_404(client, auth):
    assert client.get("/applications/999", headers=auth).status_code == 404
    assert client.patch("/applications/999", headers=auth, json={"notes": "x"}).status_code == 404
    assert client.delete("/applications/999", headers=auth).status_code == 404


def test_patch_changes_only_the_fields_sent(make, client, auth):
    app = make()
    updated = client.patch(
        f"/applications/{app['id']}", headers=auth, json={"title": "Principal Engineer", "interview_on": "2099-02-03"}
    ).json()
    assert updated["title"] == "Principal Engineer"
    assert updated["interview_on"] == "2099-02-03"
    assert updated["company"] == "Globex"  # untouched


def test_dates_are_validated_and_can_be_cleared(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    assert client.patch(url, headers=auth, json={"interview_on": "next tuesday"}).status_code == 422
    client.patch(url, headers=auth, json={"applied_on": "2026-10-01"})
    assert client.get(url, headers=auth).json()["applied_on"] == "2026-10-01"
    client.patch(url, headers=auth, json={"applied_on": ""})
    assert client.get(url, headers=auth).json()["applied_on"] is None


def test_unknown_status_is_rejected(make, client, auth):
    app = make()
    assert client.patch(f"/applications/{app['id']}", headers=auth, json={"status": "hired!"}).status_code == 422


def test_status_changes_are_recorded_in_the_timeline_once_each(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    client.patch(url, headers=auth, json={"status": "applied"})
    client.patch(url, headers=auth, json={"status": "applied"})  # no change: no new entry
    client.patch(url, headers=auth, json={"status": "interviewing"})
    history = client.get(url, headers=auth).json()["history"]
    assert [h["status"] for h in history] == ["saved", "applied", "interviewing"]


def test_notes_are_mirrored_to_notes_md_and_removed_when_cleared(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    notes_file = Path(app["folder"]) / "notes.md"
    client.patch(url, headers=auth, json={"notes": "Ask about on-call rotation."})
    assert notes_file.read_text(encoding="utf-8") == "Ask about on-call rotation."
    client.patch(url, headers=auth, json={"notes": "  "})
    assert not notes_file.exists()


def test_unreadable_saved_analysis_does_not_hide_the_application(make, client, auth):
    app = make()
    with connect() as conn:
        conn.execute("UPDATE application SET analysis_json = '{not json' WHERE id = ?", (app["id"],))
    detail = client.get(f"/applications/{app['id']}", headers=auth).json()
    assert detail["analysis"] is None
    assert detail["company"] == "Globex"


# --- delete -----------------------------------------------------------------------------------------


def test_delete_removes_the_record_and_its_versions_but_keeps_files_by_default(make, client, auth):
    app = make()
    export(client, auth, app["id"])
    assert client.delete(f"/applications/{app['id']}", headers=auth).status_code == 204
    assert client.get(f"/applications/{app['id']}", headers=auth).status_code == 404
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM resume_version").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM status_history").fetchone()[0] == 0
    assert (Path(app["folder"]) / "posting.txt").exists()


def test_delete_can_remove_the_folder_too(make, client, auth):
    app = make()
    export(client, auth, app["id"])
    client.delete(f"/applications/{app['id']}", headers=auth, params={"delete_files": True})
    assert not Path(app["folder"]).exists()


def test_folder_paths_cannot_escape_the_applications_directory():
    with pytest.raises(ValueError):
        files.folder_path("../outside")
    with pytest.raises(ValueError):
        files.folder_path("a/b")


# --- resume versions --------------------------------------------------------------------------------


def test_each_export_becomes_a_numbered_version_in_its_own_subfolder(make, client, auth):
    app = make()
    first, second = export(client, auth, app["id"]), export(client, auth, app["id"])
    assert (first["version_number"], second["version_number"]) == (1, 2)
    assert Path(first["folder"]).name == "v1" and Path(second["folder"]).name == "v2"
    assert Path(first["folder"]).parent == Path(app["folder"])

    detail = client.get(f"/applications/{app['id']}", headers=auth).json()
    assert [v["number"] for v in detail["versions"]] == [2, 1]  # newest first
    assert detail["version_count"] == 2
    for version in detail["versions"]:
        assert Path(version["docx_path"]).is_file() and Path(version["pdf_path"]).is_file()
        assert version["checks_passed"] is True
        assert version["pages"] == 1


def test_a_version_keeps_the_exact_resume_content(make, client, auth):
    app = make()
    result = export(client, auth, app["id"])
    version = client.get(f"/applications/{app['id']}/versions/{result['version_id']}", headers=auth).json()
    assert version["profile"]["contact"]["name"] == "Jane Doe"
    assert version["profile"]["experience"][0]["bullets"] == ["Built APIs."]


def test_a_version_remembers_the_section_order_it_was_exported_with(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    default = export(client, auth, app["id"])
    after = client.post(
        "/export",
        headers=auth,
        json={"profile": PROFILE.model_dump(), "application_id": app["id"], "skills_first": False},
    ).json()
    assert client.get(f"{url}/versions/{default['version_id']}", headers=auth).json()["skills_first"] is True
    assert client.get(f"{url}/versions/{after['version_id']}", headers=auth).json()["skills_first"] is False


def test_version_files_can_be_downloaded(make, client, auth):
    app = make()
    result = export(client, auth, app["id"])
    detail = client.get(f"/applications/{app['id']}", headers=auth).json()
    pdf = client.get("/export/file", headers=auth, params={"path": detail["versions"][0]["pdf_path"]})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert result["application_id"] == app["id"]


def test_exporting_for_a_missing_application_is_404(client, auth):
    response = client.post("/export", headers=auth, json={"profile": PROFILE.model_dump(), "application_id": 12345})
    assert response.status_code == 404


def test_unknown_version_is_404(make, client, auth):
    app = make()
    assert client.get(f"/applications/{app['id']}/versions/999", headers=auth).status_code == 404


# --- marking a version as submitted -----------------------------------------------------------------


def test_marking_a_version_submitted_moves_saved_to_applied_and_sets_the_date(make, client, auth):
    app = make()
    version_id = export(client, auth, app["id"])["version_id"]
    detail = client.put(f"/applications/{app['id']}/versions/{version_id}/submitted", headers=auth).json()
    assert detail["status"] == "applied"
    assert detail["applied_on"]
    assert detail["submitted_version"] == 1
    assert [h["status"] for h in detail["history"]] == ["saved", "applied"]


def test_submitting_does_not_downgrade_a_later_status_or_overwrite_the_date(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    client.patch(url, headers=auth, json={"status": "interviewing", "applied_on": "2026-09-01"})
    version_id = export(client, auth, app["id"])["version_id"]
    detail = client.put(f"{url}/versions/{version_id}/submitted", headers=auth).json()
    assert detail["status"] == "interviewing"
    assert detail["applied_on"] == "2026-09-01"


def test_only_one_version_is_submitted_at_a_time_and_it_can_be_cleared(make, client, auth):
    app = make()
    url = f"/applications/{app['id']}"
    one, two = (export(client, auth, app["id"])["version_id"] for _ in range(2))
    client.put(f"{url}/versions/{one}/submitted", headers=auth)
    detail = client.put(f"{url}/versions/{two}/submitted", headers=auth).json()
    assert [(v["number"], v["submitted"]) for v in detail["versions"]] == [(2, True), (1, False)]
    assert detail["submitted_version"] == 2

    cleared = client.put(f"{url}/versions/{two}/submitted", headers=auth, params={"submitted": False}).json()
    assert cleared["submitted_version"] is None


def test_marking_an_unknown_version_submitted_is_404(make, client, auth):
    app = make()
    assert client.put(f"/applications/{app['id']}/versions/999/submitted", headers=auth).status_code == 404


def test_store_helpers_are_consistent():
    assert store.posting_hash("A  b\nC") == store.posting_hash(" a B c ")
    assert store.posting_hash("a") != store.posting_hash("b")
