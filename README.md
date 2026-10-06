# Resume ATS

A local-first desktop app that turns a pasted job posting into a tailored, ATS-safe resume and keeps a
searchable archive of every application. Bring your own [OpenRouter](https://openrouter.ai) API key and choose
any model in Settings. Runs on Windows and macOS.

> Status: **Phase 0 (skeleton)** — see [docs/SPEC.md](docs/SPEC.md) for the plan.

## Stack

Tauri v2 shell + Angular/TypeScript UI + Python FastAPI backend (bundled as a sidecar), SQLite for storage.

## Development

Prerequisites: Python 3.11+, Node 22.22.3+ or 24.15+ (required by current Angular), Rust (stable) for the Tauri shell.

```bash
# Backend (browser-mode dev needs only this and the frontend)
cd backend
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
python run.py --port 8000

# Frontend
cd frontend
npm install
npm start                     # http://localhost:4200, talks to http://127.0.0.1:8000

# Desktop app (from the repo root)
npm install
python scripts/build_sidecar.py   # bundles the backend into src-tauri/binaries
npm run tauri dev
```

## Releasing

1. Generate an updater signing key once: `npm run tauri signer generate -- -w ~/.tauri/resume-ats.key`
2. Put the **public** key in `src-tauri/tauri.conf.json` (`plugins.updater.pubkey`) and replace `OWNER` in the
   updater endpoint with the GitHub owner of this repo.
3. Add the **private** key and its password as repository secrets `TAURI_SIGNING_PRIVATE_KEY` and
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`. Never commit the key.
4. `git tag v0.1.0 && git push --tags` — GitHub Actions builds the Windows and macOS installers and publishes them.

Installed apps check for a newer release on launch and offer Update / Later.

## Privacy

Resume and job text is sent to OpenRouter and the model provider you select. Your API key is stored in the
operating system keychain, and all application data stays in your OS user-data folder.

## License

MIT
