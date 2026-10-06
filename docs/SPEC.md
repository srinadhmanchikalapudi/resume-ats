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

## Exports

- DOCX via `python-docx` (single column, no tables, standard fonts, standard headings).
- PDF via ReportLab or fpdf2 (pure Python, real text layer). WeasyPrint is avoided because its native libraries are
  hard to bundle on both OSes.

## Phases

| Phase | Scope |
|---|---|
| 0 | Skeleton: Tauri + FastAPI sidecar + Angular. Settings (key, model). CI builds Windows + macOS installers; update prompt works end to end. |
| 1 | Master profile import (PDF/DOCX → structured JSON), job paste, match analysis, tailoring, DOCX/PDF export. |
| 2 | Application archive: SQLite + folders, list/search, status tracking, version history. |
| 3 | Quality checks: resume health, ATS-safety checks on PDF/DOCX, specificity and quantification feedback. |
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
