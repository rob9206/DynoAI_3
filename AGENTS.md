# AGENTS.md

## Cursor Cloud specific instructions

### Architecture

DynoAI3 is a monorepo with two required services for development:

| Service | Stack | Port | Start command |
|---------|-------|------|---------------|
| Backend API | Python / Flask | 5001 | `PYTHONPATH=. python3 -m api.app` |
| Frontend | React / Vite / TypeScript | 5173 | `cd frontend && npm run dev` |

SQLite is the default database (auto-created at `./dynoai.db`, zero config). Redis and PostgreSQL are optional (only for production).

### Running services

- **Backend**: `PYTHONPATH=. DYNOAI_DEBUG=true python3 -m api.app` from workspace root. The `PYTHONPATH=.` is required so Python can resolve `api.*` and `dynoai.*` imports.
- **Frontend**: `npm run dev` from `frontend/`. Vite proxies `/api` requests to `http://localhost:5001` automatically (configured in `vite.config.ts`).
- Use `python3` not `python` — the VM may not have a `python` symlink.

### Dependency installation

There are two Python requirements files with a **Flask version conflict** (`requirements.txt` pins `flask==3.1.0`, `api/requirements.txt` pins `flask==3.1.3`). Install them sequentially — `requirements.txt` first, then `api/requirements.txt` — so the API's newer Flask version wins. Also install `bcrypt` (needed by `api/models/user.py` but not listed in either requirements file).

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
pip install -e ".[dev,test]"
pip install bcrypt
```

Frontend uses npm with `package-lock.json`:

```bash
cd frontend && npm ci --legacy-peer-deps
```

### Lint / Test / Build

| Check | Command | Notes |
|-------|---------|-------|
| Python lint | `ruff check .` | Pre-existing warnings exist; `--fix` can auto-fix some |
| Python format | `black --check .` | Pre-existing formatting issues exist |
| Python tests | `PYTHONPATH=. pytest tests/ -v` | ~1260 tests; ~27 pre-existing failures in API auth tests and physics simulator |
| Frontend lint | `cd frontend && npx eslint .` | Pre-existing TS errors exist |
| Frontend tests | `cd frontend && npx vitest run` | ~41 tests; 1 pre-existing failure in pvvParser |
| Frontend build | `cd frontend && npm run build` | TypeScript + Vite production build |

### Gotchas

- The `api.app` module auto-starts the Flask server when imported as `api.app` (not just `__main__`). Set `PYTEST_CURRENT_TEST=1` env var if you need to import `api.app` without it starting the server.
- `DYNOAI_STANDALONE` env var disables some features (rate limiting, root route). Do not set it for normal dev.
- JetDrive hardware features work in **stub/simulator mode** by default (`JETSTREAM_STUB_MODE=true` in `.env`), so no physical dyno hardware is needed.
- The workspace rule in `.cursor/rules/no-physics-in-frontend.mdc` forbids physics/math computations in frontend code. Read it before editing any frontend files that deal with numeric values.
