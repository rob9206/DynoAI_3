# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DynoAI3 (v1.3.1) is a deterministic, post-processing calibration engine for Harley-Davidson dyno data. It pairs deterministic VE math (apply/rollback with SHA-256 verification) with a Bayesian Optimization layer (Gaussian Process surrogate + active-learning pull advisor). Single source of truth for the version is `dynoai/version.py`.

The system is **not** a dyno controller, ECU flasher, or real-time/closed-loop tuner. Core math is deterministic; the GP layer suggests where to test next, while final corrections always come from `VE = AFR_measured / AFR_target` with strict clamping.

## Architecture

### Backend (Python / Flask)

- **`api/`** — Flask REST API. Entry point: `api/app.py`. Notable subtrees:
  - `api/routes/` — endpoint blueprints. JetDrive endpoints live under `api/routes/jetdrive/` (split into `analysis.py`, `hardware.py`, `innovate.py`, `mapping.py`, `simulator.py`). Other routes: `v3_session.py`, `nextgen.py`, `calibration_library.py`, `engine_analyzer.py`, `runs.py`, `reports.py`, `workspace.py`, `wizards.py`, `powercore.py`, `virtual_tune.py`, `watch_folder.py`.
  - `api/services/` — business logic. JetDrive services in `api/services/jetdrive/` include the canonical `wideband_rescale.py` and `jetdrive_realtime_analysis.py`. Other key services: `autotune_workflow.py`, `nextgen_workflow.py`, `v3_session_service.py`, `workspace_analyzer.py`, `calibration_library_service.py`, `coverage_tracker.py`, `progress_broadcaster.py`.
  - `api/auth.py`, `api/rate_limit.py`, `api/middleware/`, `api/errors.py`, `api/metrics.py`, `api/health.py`, `api/admin.py`, `api/docs.py` (Swagger).
- **`dynoai/`** — packaged library. `dynoai/core/` holds the deterministic engine: `ve_math.py`, `ve_operations.py`, `io_contracts.py`, `gp_engine.py`, `surface_builder.py`, `weighted_binning.py`, `cause_tree.py`, `next_test_planner.py`, `spark_valley.py`, `mode_detection.py`, `signal_filters.py`, `transient_fuel.py`, `decel_management.py`, `cylinder_balancing.py`, `knock_optimization.py`, `heat_management.py`, `environmental.py`, `nextgen_payload.py`, `log_normalizer.py`, `afr_targets.py`. `dynoai/api/xai_blueprint.py` and `dynoai/clients/xai_client.py` host xAI integration. `dynoai/gui/` contains a PyQt6 desktop GUI (`analysis_tab.py`, `jetdrive_tab.py`, `results_tab.py`, `settings_tab.py`).
- **`dynoai_v3/`** — V3 AI tuning engine: `gp_surrogate.py` (Gaussian Process), `pull_advisor.py` (Bayesian Active Learning), `session_orchestrator.py`, `adaptive_overlay.py`, `calibration_library.py`, `template_library.py`, `physics_constraints.py`, `grid_config.py`, `grid_utils.py`.
- **Root-level legacy modules** — `io_contracts.py` and `ve_operations.py` are the canonical deterministic apply/rollback/contract modules imported throughout. Do **not** duplicate this math elsewhere.
- **`bridge/`, `extensions/`, `plugins/`, `vendor/`** — integration shims and third-party connectors.
- **`migrations/`** — Alembic; config in `alembic.ini`.

### Frontend (React 19 / Vite / TypeScript)

`frontend/src/` is a strict **renderer only** (see safety rule below). Main areas: `pages/`, `components/`, `hooks/`, `api/`, `services/`, `lib/`, `utils/`, `types/`. Stack: React 19, Vite 6, TanStack Query, Radix UI, Tailwind 4, framer-motion, recharts, three.js, socket.io-client. Telemetry streams from the backend via SSE/`useJetDriveLive`.

### Data flow

CSV/live-capture → `api/services/jetdrive/*` (ingest, normalize, rescale at server) → `autotune_workflow.py` / `nextgen_workflow.py` → `dynoai/core/ve_math.py` + kernels (K1 gradient-limited smoothing, K2 coverage-weighted, K3 spark logic) → `ve_operations.apply` (writes correction + SHA-256 metadata) → frontend renders results / PVV XML / text export. Rollback uses `ve_operations.rollback` against the metadata sidecar.

## Critical Safety Rule: No Physics in the Frontend

`.cursor/rules/no-physics-in-frontend.mdc` is `alwaysApply: true` and **non-negotiable**. The frontend must not perform unit conversions, sensor calibration (e.g., LC-1/LC-2 voltage→AFR `* 3.008 + 7.35`), VE math, clamp/bounds logic, plausibility thresholds (e.g., `afr > 5 && afr < 25`), channel synthesis (MAP-from-RPM, lambda↔AFR), or use physical-constant numeric literals (`14.7`, `7.35`, `3.008`, `1013.25`, `9.81`, `273.15`, etc.).

A real incident occurred where voltage was rescaled to AFR inside a React hook, causing wrong corrections to be applied to real engines. All physics/calibration math must live on the server (typically in `api/services/jetdrive/*` or `api/services/*`); the frontend reads server-provided values with explicit unit metadata.

Allowed in `frontend/`: pixel/CSS values, poll intervals/timeouts, pagination sizes, HTTP status codes, color hex, animation durations, axis ticks for pure visual scaling. Known violations being remediated are listed in the rule file — do not extend them.

## Common Commands

### Setup

```bash
pip install -e .                    # editable install; pulls deps from pyproject.toml
pip install -r requirements.txt     # pinned runtime requirements
pip install -r api/requirements.txt # api-specific extras

cd frontend && npm install
```

### Run

```bash
# Backend (port 5000 by default; some scripts use 5001)
python -c "from api.app import app; app.run(host='127.0.0.1', port=5000)"

# Frontend (port 5173)
cd frontend && npm run dev

# Windows convenience
scripts\windows\quick-start.bat     # fastest, no dep updates
scripts\windows\start-all.bat       # full start with dep updates
```

### Tests

```bash
pytest tests/ -v                                # all tests (pytest config in pyproject.toml)
pytest tests/unit -v                            # unit tests
pytest tests/api -v                             # API tests
pytest tests/jetdrive -v                        # JetDrive protocol/pipeline tests
pytest tests/core -v                            # deterministic core tests
pytest tests/unit/test_ve_math_verification.py  # VE math inverse-property suite (25 tests)
pytest tests/unit/test_ve_math.py::test_specific_name -v  # single test
pytest --cov=api --cov=dynoai tests/            # with coverage
pytest -m "not slow"                            # skip slow-marked tests
```

Markers: `slow`, `integration`, `unit`. CI excludes `tests/integration` from the standard pytest job and runs them separately on `main`/`develop`.

### Lint / format / type-check

```bash
ruff check . --fix       # primary linter (config in pyproject.toml)
black .                  # 88-col, py39-py312
isort .                  # black profile
mypy api dynoai          # type check (mypy.ini + pyproject.toml)
bandit -r api dynoai -ll --skip B101
pre-commit run --all-files
```

Frontend:

```bash
cd frontend
npm run lint             # eslint
npm run test             # vitest run
npm run test:watch
npm run build            # tsc -b --noCheck && vite build
npx tsc --noEmit         # type check only
```

### CLI tools

```bash
# JetDrive auto-tune (simulate / from CSV / live)
python scripts/jetdrive/jetdrive_autotune.py --simulate --run-id test_run
python scripts/jetdrive/jetdrive_autotune.py --csv runs/my_run/data.csv --run-id my_analysis
python scripts/jetdrive/jetdrive_autotune.py --live --duration 60 --run-id dyno_pull

# Standard analysis
python ai_tuner_toolkit_dyno_v1_2.py --csv log.csv --outdir ./output \
  --base_front current_ve_front.csv --base_rear current_ve_rear.csv

# VE apply / rollback (always available as the canonical entry point)
python ve_operations.py apply    --base base.csv --factor factors.csv --output out.csv [--dry-run]
python ve_operations.py rollback --current out.csv --metadata out_meta.json --output restored.csv
```

### Database migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Conventions and Guardrails

- **Version**: bump only `dynoai/version.py`. Validate with `python -c "import dynoai; print(dynoai.__version__)"` and `python -c "import importlib.metadata as m; print(m.version('dynoai'))"`.
- **Determinism is a property to preserve**: same input → bit-identical output. The VE math verification suite enforces apply→rollback→original within ±0.001. Never weaken these assertions to make a test pass.
- **Math-critical files** (require extra care; escalate before structural changes): `ve_operations.py`, `io_contracts.py`, `dynoai/core/ve_math.py`, the kernel modules, and anything under `dynoai_v3/` that influences corrections.
- **Read-only by default**: `archive/` (historical artifacts), `experiments/` (research kernels), `tables/` (calibration base tables — touch only when running VE operations).
- **Default clamp**: deterministic apply/rollback in `ve_operations.py` caps VE correction factors at ±7% by default. The API analysis path uses its own clamp setting and defaults `DYNOAI_CLAMP` / `default_clamp` to `15.0` unless overridden. Dry-run mode (`--dry-run`) previews apply/rollback changes; rollback metadata is a JSON sidecar next to the output CSV.
- **CSV/IO**: always use `io_contracts.sanitize_csv_cell` and `io_contracts.safe_path` when writing user-influenced data.
- **JSON safety**: `api/app.py` installs a `_FiniteJSONProvider` that scrubs non-finite floats (Infinity/NaN → null). Don't reintroduce raw `allow_nan=True` JSON output.
- **AFR target table** (MAP-based) lives in `dynoai/core/afr_targets.py`; refer there before hardcoding numbers.

## Environment

- Python ≥ 3.9 (CI matrix: 3.9, 3.10, 3.11, 3.12). Frontend Node ≥ 18 (CI uses 20).
- Copy `.env.example` → `.env` for local dev. Production needs `API_AUTH_ENABLED=true`, a generated `SECRET_KEY`, `DYNOAI_CORS_ORIGINS`, Redis-backed `RATE_LIMIT_STORAGE`, and `DATABASE_URL` (PostgreSQL).
- Engine Analyzer library defaults to `engineanalyzer/` at repo root; override with `ENALYZER_LIB_DIR`.
- JetDrive defaults: multicast group `224.0.2.10`, UDP port `22344`, interface `0.0.0.0`.

## CI Gates

`.github/workflows/ci.yml` enforces: ruff, black --check, isort --check, mypy on `api dynoai`, pytest across the Python matrix (excluding `tests/integration`), a focused calibration-library rollout gate (`tests/test_calibration_library.py`, `tests/api/test_calibration_library_routes.py`, `tests/api/test_v3_session_seed_metadata.py`), frontend ESLint + `tsc --noEmit` + targeted hook tests + build, plus advisory bandit/safety/npm-audit and integration tests on `main`/`develop` only.
