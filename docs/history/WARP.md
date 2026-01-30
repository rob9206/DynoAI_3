# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## 1. Local setup & dependencies

DynoAI_3 is a Python + Flask backend with a React/Vite frontend and a CLI toolkit. The expected flow is local-only; core tuning does not require internet.

### Python environment

On Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r api\requirements.txt
```

On Unix-like systems:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r api/requirements.txt
```

### Frontend dependencies

From the repo root:

```bash
cd frontend
npm install
cd ..
```

The frontend uses Vite + React/TypeScript (see `frontend/package.json`).

## 2. Common commands

### 2.1 Run the full web app

Recommended on Windows (one-command startup):

```powershell
.\start-web.ps1
```

This:
- Activates `.venv`
- Ensures `api/requirements.txt` is installed
- Installs `frontend` dependencies if needed
- Starts Flask on `http://localhost:5001` and Vite on `http://localhost:5173`

Unix-like alternative (two background processes):

```bash
./start-dev.sh
```

Windows batch alternative:

```cmd
start-dev.bat
```

Then open `http://localhost:5173` and use the upload UI.

### 2.2 Run backend only (Flask API)

From repo root with venv activated:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r api\requirements.txt
python api\app.py
```

Backend health check:

```bash
curl http://localhost:5001/api/health
```

Key endpoints (served from `api/app.py`):
- `GET  /api/health` – health check
- `POST /api/analyze` – upload CSV and start async analysis
- `GET  /api/status/<run_id>` – poll analysis status
- `GET  /api/download/<run_id>/<filename>` – download an output file
- `GET  /api/ve-data/<run_id>` – VE grid data for 3D visualization
- `GET  /api/diagnostics/<run_id>` – diagnostics/anomalies
- `GET  /api/coverage/<run_id>` – coverage heatmaps

Jetstream integration endpoints live under `/api/jetstream/*` and are wired via `api/routes/jetstream` and `api/jetstream` libs when enabled.

### 2.3 Run frontend only

With backend already running (or pointed at a remote API):

```bash
cd frontend
npm run dev        # start dev server on http://localhost:5173
npm run build      # production build
npm run lint       # eslint
npm run preview    # preview built app
```

The frontend expects an API base URL via `VITE_API_URL` in `frontend/.env` (see `QUICK_START_WEB.md`).

### 2.4 Core CLI analysis (no web UI)

From repo root with venv activated and dependencies installed:

#### Standard dyno analysis

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv path/to/your_winpep_log.csv \
  --outdir ./output/run1 \
  --base_front path/to/current_ve_front.csv \
  --base_rear  path/to/current_ve_rear.csv
```

Key flags (see `ai_tuner_toolkit_dyno_v1_2.py` for full list):
- `--smooth_passes` – kernel passes (default often 2)
- `--clamp` – max +/- % correction (default 7–15 depending on context)
- `--rear_bias`, `--rear_rule_deg`, `--hot_extra` – spark/thermal behavior modifiers

Outputs go under `--outdir` and include at least:
- `VE_Correction_Delta_DYNO.csv`
- `Diagnostics_Report.txt`
- `manifest.json`
- Optional coverage and spark suggestion CSVs

#### VE apply / rollback

```bash
# Preview VE correction application (no file written)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv \
  --dry-run

# Apply with metadata
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv

# Roll back using metadata
python ve_operations.py rollback \
  --current ve_updated.csv \
  --metadata ve_updated_meta.json \
  --output ve_restored.csv
```

The acceptance suite (`acceptance_test.py`) encodes the safety contract for this flow (clamping, precision, metadata, hash-verified rollback).

### 2.5 Experiments: kernel runner

The `experiments/` package provides an isolated runner for experimental smoothing kernels without changing production math.

Typical usage (see `experiments/README.md` and `experiments/run_experiment.py`):

```bash
# Baseline run
python experiments/run_experiment.py \
  --idea-id baseline \
  --csv path/to/data.csv \
  --outdir experiments/baseline

# Experimental kernel (e.g., K2 coverage-adaptive)
python experiments/run_experiment.py \
  --idea-id k2_coverage_adaptive_v1 \
  --csv path/to/data.csv \
  --outdir experiments/k2_test

# Dry-run to validate configuration only
python experiments/run_experiment.py \
  --idea-id k3 \
  --csv path/to/data.csv \
  --outdir experiments/k3_dryrun \
  --dry-run
```

`experiments/kernel_registry.py` maps `idea-id` values to kernel implementations in `experiments/protos/` and writes `kernel_fingerprint.txt` for auditability.

### 2.6 Tests

#### Fast smoke test

```bash
python selftest.py
```

This generates a synthetic CSV (`dynoai.test_utils.make_synthetic_csv`), runs the main toolkit, checks required outputs, and validates the manifest.

#### VE operations acceptance

```bash
python acceptance_test.py
```

Covers clamping, precision, metadata, rollback, dry-run behavior, multiplier bounds, round-trip tolerance, and deterministic hashes.

#### Unittests (Python stdlib `unittest`)

Quick xAI-only tests (no network):

```bash
python -m unittest -v tests/test_xai_client.py tests/test_xai_blueprint.py
```

Discover all `tests/test_*.py`:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

#### Pytest-style runs (if `pytest` is installed)

Some docs and experiment guides assume `pytest` is available. Example selective runs:

```bash
python -m pytest tests/test_runner_paths.py -v
python -m pytest tests/test_fingerprint.py -v
python -m pytest tests/test_bin_alignment.py -v
python -m pytest tests/test_delta_floor.py -v
```

#### Comprehensive safety check (when scripts are present)

There is a PowerShell harness intended to wrap selftests, kernel harnesses, and pytest:

```powershell
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest
```

If you modify math-critical code (see below), prefer this full suite.

### 2.7 Linting, formatting, type checking

Python tooling is pinned in `requirements.txt`:
- `ruff` – linting
- `black` – formatting
- `mypy` – type checking

Typical invocation from repo root (with venv active):

```bash
ruff check --fix .
black .
mypy .
```

## 3. Security & Snyk expectations

There is an always-on Snyk rule in `.cursor/rules/snyk_rules.mdc` and additional guidance in `docs/COPILOT_SETUP.md` and `docs/SECURITY_TRIAGE.md`:

- For any **new or significantly modified Python/TypeScript code or dependency updates**, run Snyk where the CLI is available.
- Typical commands (if `snyk` is installed and authenticated):

```bash
snyk auth
snyk code test .
snyk test --file=requirements.txt
snyk test --file=api/requirements.txt
```

- Iterate: fix reported high/critical issues, rescan until clean or explicitly documented.

Warp should **not** assume Snyk is present; if it is missing, propose these commands instead of running them.

## 4. Safety & "math-critical" code

The most important project-specific rules are captured in `docs/DYNOAI_SAFETY_RULES.md` and `.cursorrules.md`. Warp should align with them:

### 4.1 Math-critical modules (protected)

The tuning math and table operations are safety-sensitive:

- `ai_tuner_toolkit_dyno_v1_2.py` – main dyno analysis engine (AFR → VE deltas, smoothing, clamping, diagnostics)
- `ve_operations.py` – VE apply/rollback, clamping, metadata, SHA-256 verification
- `io_contracts.py` – path safety, hashing, repo-root enforcement
- `experiments/protos/*.py` – experimental kernels (K1/K2/K3, weighted, knock-aware)

In older docs these may be referenced under `core/`; in this v3 repo they live at the top level and under `experiments/`.

**Rules when touching these files:**
- Treat any change as high-risk. Prefer not to modify unless the user explicitly requests a math change.
- Never weaken safety checks (clamping, bin alignment, hash validation, coverage thresholds) or test assertions to “make tests pass”.
- When modification is required:
  - Keep changes minimal and locally scoped.
  - Maintain existing numerical behavior unless the change is explicitly about altering that behavior.
  - Run at least: `python selftest.py`, `python acceptance_test.py`, relevant `tests/test_*.py`, and (if available) the full safety script.
  - Preserve data format invariants described in `DYNOAI_SAFETY_RULES` (VE table grid, manifest fields, diagnostics content, fingerprint format).

### 4.2 Test harnesses with fixed semantics

Several tests encode the **contract** for safe operation and should not have their expectations relaxed:

- `selftest.py`, `selftest_runner.py`
- `acceptance_test.py`
- `tests/test_bin_alignment.py`, `tests/test_delta_floor.py`, `tests/test_fingerprint.py`, `tests/test_runner_paths.py`
- Any kernel tests under `tests/kernels/` (if present in this tree)

Warp may:
- Update imports and paths after refactors.
- Extend coverage with new test cases.

Warp should **not**:
- Loosen tolerances or remove checks without an equivalent or stronger safety justification.

### 4.3 Path, table, and data safety

Key invariants (see `DYNOAI_SAFETY_RULES.md`):
- All output paths must resolve **inside the repo root**; path helpers in `io_contracts.py` enforce this.
- VE tables and factor tables must share identical RPM/kPa grids; no implicit reindexing.
- VE tables are 4-decimal CSVs; factor tables are percentage deltas (e.g., `+3.5000`).
- Base tables under `tables/` and real dyno logs should be treated as **read-only reference data**; use `VEApply` to generate new tables instead of editing originals in place.

Warp should preserve these properties when editing code or scripts.

## 5. High-level architecture

This section is a **big-picture map** so Warp can navigate quickly without enumerating every file.

### 5.1 Core engine & data flow

The core of DynoAI is a batch pipeline:

1. **Input**: WinPEP-style dyno logs (CSV) plus optional base VE tables.
2. **Engine**: `ai_tuner_toolkit_dyno_v1_2.py` parses CSV, bins data into an RPM/kPa grid, computes AFR error, converts to VE correction percentages, applies a configurable smoothing kernel, and enforces clamping.
3. **Outputs**: VE correction deltas, diagnostics, spark suggestions, coverage maps, manifest.
4. **VE operations**: `ve_operations.py` consumes base VE + correction factors to produce updated VE tables with rollback metadata.

The same engine is used by:
- Direct CLI invocations.
- The Flask API (`api/app.py`) via `subprocess.run`.
- The experimental runner (`experiments/run_experiment.py`) via monkey-patched kernels.

### 5.2 Packages and modules

- **Top-level engine modules**
  - `ai_tuner_toolkit_dyno_v1_2.py` – CLI entry point for analysis; includes argument parsing and coordination of kernel, clamping, and report generation.
  - `ve_operations.py` – VE apply/rollback logic and associated file I/O helpers.
  - `io_contracts.py` – shared utilities for safe path resolution and content hashing.

- **`dynoai/` package**
  - `dynoai/constants.py` – shared constants for tests and tooling.
  - `dynoai/test_utils.py` – synthesis utilities like `make_synthetic_csv` used by `selftest.py`.
  - `dynoai/api/xai_blueprint.py` – a Flask blueprint that exposes `/api/xai/chat` for xAI Grok integration.
  - `dynoai/clients/xai_client.py` – HTTP client wrapper for xAI, with tests in `tests/test_xai_client.py`.

- **Flask API (`api/`)**
  - `api/app.py` – single-process Flask server that:
    - Accepts file uploads and tuning parameters via `/api/analyze`.
    - Writes inputs to `uploads/<run_id>/` and outputs to `outputs/<run_id>/`.
    - Spawns the CLI engine in a background thread using `subprocess.run`.
    - Tracks job state in an in-memory `active_jobs` dict.
    - Normalizes `manifest.json` into a frontend-friendly shape (`convert_manifest_to_frontend_format`).
    - Serves derived data (VE grids, coverage, diagnostics) for visualization.
  - `api/services/run_manager.py`, `api/services/progress_broadcaster.py` – helpers for orchestration and status/progress (Jetstream and UI integration).
  - `api/routes/jetstream/*` plus `api/jetstream` libs – optional integration with an external “Jetstream” source of runs; initialized if environment variables are set.

- **Frontend (`frontend/`)**
  - A Vite-based React/TypeScript app built on `@github/spark` and Radix UI libraries.
  - Talks to the Flask API via `VITE_API_URL` (see `QUICK_START_WEB.md`).
  - Provides flows for uploading CSVs, tracking analysis progress, listing runs, downloading outputs, and rendering 3D VE surfaces (with `three`, `d3`, and related visualization libs).

- **Experiments (`experiments/`)**
  - `experiments/run_experiment.py` and `experiments/kernel_registry.py` implement a separate path for experimenting with new smoothing kernels.
  - Kernels in `experiments/protos/` are **math-critical** and can be evaluated against baseline runs without altering production code.
  - Tests in `tests/test_*` (bin alignment, delta floor, fingerprints, path safety) exercise pieces of this stack as well.

- **Tests (`tests/`)**
  - Core behavior tests: `test_bin_alignment.py`, `test_delta_floor.py`, `test_fingerprint.py`, `test_runner_paths.py`, `test_file_not_found_handling.py`.
  - xAI integration tests: `test_xai_client.py`, `test_xai_blueprint.py` (mocked HTTP, no real network).
  - Agent-related tests live under `tests/agent/` and may be minimal stubs; check before relying on them.

- **Automation & scripts (`scripts/`)**
  - PowerShell helpers for running the full safety suite, performing repo reorganizations, and cleaning generated artifacts (see `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md` for intent and `scripts/` contents for details).

- **Config & themes**
  - `config/themes/pg27aqdm-palette.json` and `extensions/pg27aqdm-low-strain/` define a low-strain color palette and VS Code/Cursor themes tuned for a specific WOLED display. They are orthogonal to tuning math but relevant for local ergonomics.

## 6. Existing AI/assistant rules to respect

There are several existing instruction sets for other AI tools; Warp should mirror their **spirit**:

- `.cursorrules.md` – defines file criticality, model selection, and expectations:
  - Use stronger models / more caution for math-critical files and large refactors.
  - Require confirmation for deleting directories, modifying many files, or changing `requirements.txt`.
  - Treat `archive/`, `experiments/`, and `tables/` as read-only by default unless explicitly asked.
- `docs/CLAUDE_RAILS.md` – describes a preferred working style:
  - Short status updates, small incremental edits, and always running lint + tests for significant changes.
  - One-command startup `.\start-web.ps1` and standard lint/test commands (mirrored above).
- `docs/COPILOT_SETUP.md` and related `.github` config – indicate that AI tools should:
  - Follow project-specific patterns and safety rules.
  - Integrate Snyk scanning into workflows when available.

Warp should:
- Default to small, reversible changes and keep diffs focused.
- Prefer enhancing tests over loosening them.
- When asked to change math-critical behavior, explicitly call out the impact and suggest additional validation runs.

## 7. When in doubt

- Use `docs/README.md` and `docs/DYNOAI_ARCHITECTURE_OVERVIEW.md` as the authoritative map of subsystems.
- Use `docs/DYNOAI_SAFETY_RULES.md` whenever a change touches tuning math, file formats, or VE/spark behavior.
- When behavior changes in CLI flags or API endpoints, update `README.md`, `QUICK_START_WEB.md`, and any relevant docs under `docs/` instead of duplicating explanations elsewhere.

If Warp is unsure about a change that might affect real-world tuning behavior, err on the side of **proposing** a plan and tests rather than directly modifying math-critical code.