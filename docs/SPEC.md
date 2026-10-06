# Resume ATS — Specification

A local-first desktop app that turns a pasted job posting into a tailored,
ATS-safe resume and keeps a searchable record of every application.

## Goals

1. Paste a job description, get a match analysis and a tailored resume (DOCX + PDF) ready to submit.
2. Archive every application: posting text, the exact resume sent, analysis, status, interview notes.
3. Ship as a Windows installer and a macOS `.dmg`, with in-app update prompts.
4. Bring-your-own LLM key (OpenRouter) and a user-selectable model.

## Non-goals

- Multi-user accounts, hosted service, or any server we operate.
- Fake "ATS score" claims or simulation of specific vendors' internal parsers (they are not public).
- Scraping LinkedIn or job boards.

## Architecture

```
Tauri v2 shell (window + updater)
   └─ Angular + TypeScript UI ──HTTP 127.0.0.1──► FastAPI (PyInstaller sidecar)
                                                     └─ SQLite + files in the OS user-data dir
```

- The Tauri shell picks a free port and a random per-launch token, starts the Python sidecar with
  `--port` / `--token`, and exposes them to the UI through the `get_backend_info` command.
- The sidecar rejects requests that lack the `X-App-Token` header (when a token is configured).
- In browser dev mode (`ng serve` + `uvicorn`) the UI falls back to `http://127.0.0.1:8000` with no token.
- User data lives in the OS data directory (`platformdirs`), never in the install folder, so updates cannot erase it.
- Schema changes are append-only SQL migrations (`backend/app/db.py`, tracked with `PRAGMA user_version`) that run
  at startup, so an update never needs a manual database step. Alembic was dropped: a single-user SQLite file does
  not need it, and plain SQL avoids bundling migration scripts into the sidecar.

## LLM access

- OpenRouter through the OpenAI-compatible API (`https://openrouter.ai/api/v1`); base URL is configurable.
- The API key is stored in the OS keychain via `keyring`, never in a file or the database.
- The model is a plain string setting. Settings UI: searchable dropdown fed by `GET /models` plus a custom-ID field.
- Optional per-task models (cheap model for extraction, stronger model for rewriting).
- Models differ in structured-output support. The client checks `supported_parameters`; when JSON mode / tools are
  unavailable it falls back to prompt-based JSON, validated with Pydantic, with one retry.
- First run discloses that resume text is sent to OpenRouter and the selected model provider.

## Core concepts

- **Master profile** — structured source of truth for the user's career (roles, bullets, projects, skills, metrics).
  Tailoring only selects and rephrases from it. It never invents experience; suggested skills the user lacks are
  flagged, not inserted.
- **Application** — job posting text + company/role + date + tailored resume version + analysis + status + notes.
  Stored in SQLite for search and as files on disk:

  ```
  applications/2026-10-05_Acme_Senior-Engineer/
    job.md  resume.docx  resume.pdf  analysis.json  notes.md
  ```

- **Match estimate** — evidence-based (matched / missing requirements with quotes), explicitly *not* a vendor ATS score.

## Job analysis (Phase 1, slice 2)

`POST /jobs/analyze` takes a pasted posting and the saved master profile and runs two LLM steps:

1. **Extraction** (extraction model): the posting becomes weighted requirements (required / preferred / nice),
   ATS keywords, seniority and years required.
2. **Matching** (default model): each requirement gets matched / partial / missing with evidence quoted from the
   profile. The server **verifies every quote** against the cited profile entry; a claimed match whose quote is not
   found becomes "unverified" and does not count, so a hallucinated match cannot inflate the result.

Numbers are computed by code, not the model: importance-weighted coverage (3 / 1.5 / 0.5), required-item counts,
years of experience from the profile's dates (overlaps counted once), and a literal keyword check against the
profile text. Scores can still move a few points between runs because the model's judgement of borderline
requirements varies, so the UI stresses the gap list over the exact number.

## Tailoring (Phase 1, slice 3)

`POST /jobs/tailor` takes a job analysis and the saved profile and asks the rewriting model to select, order and
lightly reword the profile's content. The model proposes; the server verifies:

- every output bullet must cite the number of an original bullet, so no bullet can be invented, merged or duplicated;
- a rewrite that adds a number not in the original is reverted;
- a rewrite that adds a posting keyword found nowhere in the profile (for example Kubernetes) is reverted;
- a keyword found elsewhere in the profile, or belonging to a requirement the match check verified, is kept but
  flagged for review and starts unselected, so the user opts in;
- skills come only from the profile; a summary that claims unsupported numbers or terms falls back to the original;
- length presets cap bullets per role (concise 5/4/3, standard 8/6/5/4, full keeps all).

Code cannot detect every invented claim (for example "led" for "contributed"), so the UI shows the original beside
every proposal and the user decides item by item. The edited result is a plain `Profile`, ready for export.

## Exports (Phase 1, slice 4)

`POST /export` takes the final resume (a `Profile`) and writes a **DOCX and a PDF** into a new folder,
`<data dir>/applications/<date>_<company>_<role>/`, named `<Name>_Resume.docx|pdf`. Both come from one shared block list
so they always say the same thing. Skills go before Experience by default (an option moves them after).

- **DOCX** (`python-docx`): one column, Arial, real Word Heading 1 and List Bullet styles, no tables, images, text boxes,
  headers or footers; theme fonts removed so the font name is honoured; current Word compatibility mode; the document
  author is the candidate, not the library.
- **PDF** (`fpdf2`): one column, standard Helvetica with a real text layer, Windows-1252 so bullets, dashes, curly quotes
  and accents work; characters outside it fall back to a plain letter or are counted and reported (the DOCX keeps them).
  WeasyPrint is avoided because its native libraries are hard to bundle on both OSes. Embedding a Unicode font would
  remove the Windows-1252 limit and is a possible follow-up for non-Latin names.
- **Verified by reading the files back**, not by trusting the builders: the DOCX is re-opened to confirm one column, no
  tables, graphics or header/footer text, standard fonts and headings; the PDF is text-extracted to confirm a text layer,
  reading order, no images, standard fonts and page count. Every bullet must be found in both files. Results are shown
  to the user beside each file.
- `GET /export/file?path=` serves an exported file for browser mode and refuses anything outside the exports folder.
- The desktop app opens files and the folder through the Tauri opener plugin, with permission limited to its own data
  folder. The plugin's reveal-in-folder permission is not scoped, so the app opens the folder instead of using it.

## Application archive (Phase 2)

Every job is kept so it can be found again when an interview is scheduled. Stored twice on purpose: SQLite for search
and relationships, and a plain folder you can browse without the app.

- **Database** (migration 2): `application` (company, role, location, link, status, applied and interview dates, notes,
  the posting verbatim, its analysis, match score, folder), `resume_version` (the exact resume content, file names,
  page count, whether the ATS checks passed, the section order used, and whether it was submitted) and
  `status_history` (a timeline). Foreign keys cascade, so deleting an application removes its versions and history.
- **Folder** `applications/<date>_<company>_<role>/`: `posting.txt`, `analysis.json`, `notes.md` (mirrored whenever notes
  change) and `v1/`, `v2/`... each holding that version's DOCX and PDF.
- **Saving:** explicit from the Job match page, and automatic the first time a resume is exported, so an exported resume
  is never detached from its job. Saving the identical posting again (ignoring case and spacing) returns the existing
  record instead of a duplicate.
- **Versions:** each export is a new numbered version; the user marks the one actually sent. Marking the first one moves
  `saved` to `applied` and records the date, but never downgrades a later status or overwrites an existing date.
- **Search and views:** case-insensitive, every word must match somewhere in company, role, location, link, notes or the
  posting text (wildcard characters are treated literally); status filter; sort by recent activity, upcoming interview
  or company. The list page shows an upcoming-interviews strip.
- **API:** `POST/GET /applications`, `GET/PATCH/DELETE /applications/{id}` (delete optionally removes the folder),
  `GET /applications/{id}/versions/{vid}`, `PUT /applications/{id}/versions/{vid}/submitted`.
- **Desktop permissions:** the app may open only paths inside its own data folder, and only http(s) links.

## Resume health and file checks (Phase 3)

**Resume health** (`POST /health-check`, `backend/app/health/`) scores a resume out of 100 from five weighted categories:
impact and numbers (30), action verbs (20), clarity and length (20), specificity (15) and completeness and
consistency (15). It is deterministic: no model calls, nothing stored, the same input always gives the same report. It is
labelled a writing-quality check, never an ATS score.

- **Numbers:** a bullet counts as quantified only for a real quantity (a percentage, money, a multiplier, a before-and-after,
  a counted thing, or a spelled-out number). Version numbers (".NET 6", "Angular 12") and standards ("ISO 27001") are
  excluded. For bullets without a number, the report asks the question that would produce one ("By how much?" after
  "Optimized"); it never suggests a figure.
- **Verbs:** strong accomplishment verbs, past-tense openers, and duty openers ("Responsible for", "Worked on") flagged;
  gerunds, passive voice and overused opening verbs reported.
- **Clarity and specificity:** bullets over 35 words, multi-sentence bullets, filler and stock phrases, buzzwords that read
  as boilerplate, first-person wording, and bullets with no number or named technology.
- **Completeness:** contact details, summary, skills, missing or inconsistent dates (compared separately for jobs and
  education), roles out of order, near-duplicate bullets, and gaps of six months or more between roles unless education
  covers them. Technology lists such as "Environment: C#, .NET" are not scored as bullets.
- **Where:** an on-demand panel on the Profile page and on the Tailor page (checking the resume as it will be exported).
  It tells the user when edits since the last check make the score out of date.
- Calibrated against a real resume: the findings were reviewed bullet by bullet and false positives (version numbers, tech
  lists, irregular past-tense verbs) were fixed with tests.

**Uploaded-file checks** (`backend/app/profile/file_checks.py`) read the file the user imports and report how an applicant
tracking system would see it: single column, tables, images and text boxes, header and footer text, fonts, text
encoding, and length. They need no model and never block an import.

- Multi-column PDFs are detected from pypdf's layout-aware text (a wide gap with long text on both sides, on a real
  share of the page). A first version that inferred columns from raw text positions passed synthetic tests but missed
  real Word-exported two-column and table-sidebar resumes, so the detector is verified against genuine Word PDFs: single
  column passes; Word's two-column flow and a table-sidebar template are flagged.

## Phases

| Phase | Scope |
|---|---|
| 0 | Skeleton: Tauri + FastAPI sidecar + Angular. Settings (key, model). CI builds Windows + macOS installers; update prompt works end to end. |
| 1 | Master profile import (PDF/DOCX → structured JSON), job paste, match analysis, tailoring, DOCX/PDF export. **Done.** |
| 2 | Application archive: SQLite + folders, list/search, status tracking, version history. **Done.** |
| 3 | Quality checks: resume health, ATS-safety checks on PDF/DOCX, specificity and quantification feedback. **Done.** |
| 4 | Extras: LinkedIn text comparison, interview-prep notes, cover letters. |

## Release & update

- Tag `vX.Y.Z` → GitHub Actions (`tauri-action`) builds Windows (`.exe`/`.msi`) and macOS (`.dmg`, arm64 + x64),
  publishes a GitHub Release and the updater manifest `latest.json`.
- Update bundles are signed with a Tauri (minisign) key; the private key lives in the `TAURI_SIGNING_PRIVATE_KEY`
  GitHub secret, the public key is in `tauri.conf.json`.
- On launch the app checks for a newer version and offers Update / Later.
- OS code signing is optional for now: unsigned Windows builds show a SmartScreen warning; unsigned macOS builds need
  right-click → Open. Apple notarization ($99/yr) can be added later via secrets in the release workflow.

## Repository layout

```
backend/    FastAPI app, tests, PyInstaller entry point
frontend/   Angular app
src-tauri/  Tauri shell (Rust), sidecar launcher, updater config
.github/    CI and release workflows
docs/       This spec
```
