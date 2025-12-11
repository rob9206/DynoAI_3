# DynoAI Architecture Overview

_Last updated: 2025-11-13_

DynoAI is an intelligent dyno tuning system that transforms WinPEP logs into production-ready VE correction tables for Harley-Davidson ECM calibration. The architecture prioritizes safety, reproducibility, and extensibility.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DynoAI System                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   WinPEP     │      │  Base VE     │                   │
│  │   CSV Log    │      │  Tables      │                   │
│  └──────┬───────┘      └──────┬───────┘                   │
│         │                     │                            │
│         └─────────┬───────────┘                            │
│                   ▼                                        │
│         ┌──────────────────────┐                          │
│         │   Core Engine        │                          │
│         │  (ai_tuner_toolkit)  │                          │
│         └──────────┬───────────┘                          │
│                    │                                       │
│         ┌──────────┴───────────┐                          │
│         ▼                      ▼                           │
│  ┌─────────────┐      ┌─────────────┐                    │
│  │ VE Deltas   │      │ Diagnostics │                    │
│  │ Spark Adj   │      │ Manifest    │                    │
│  └─────────────┘      └─────────────┘                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## JetDrive Integration (KLHDV)

- Transport: UDP multicast `224.0.2.10:22344` using KLHDV frames `[Key][Len][Host][Seq][Dest][Value...]`; keys mirror JetDriveSharp (`0x01` ChannelInfo, `0x02` ChannelValues, `0x03` ClearChannelInfo, `0x04` Ping, `0x05` Pong, `0x06` RequestChannelInfo).
- ChannelInfo payload: provider name (50 bytes, UTF-8, null padded) plus N channel blocks (34 bytes each: `chanId` u16, vendor byte, channelName 30-byte UTF-8, unit byte/JDUnit).
- ChannelValues payload: repeated 10-byte samples (`chanId` u16, `ts_ms` u32, float32 value). Extra trailing bytes are ignored.
- Components:
  - `api.services.jetdrive_client`: joins multicast, sends RequestChannelInfo to ALL_HOSTS, parses ChannelInfo into `JetDriveProviderInfo` with channel metadata, subscribes to ChannelValues and yields `JetDriveSample` records, with optional publish/re-stream helper.
  - `synthetic/winpep8_cli.py` (`jetdrive-run`): discovers providers by name/id, validates required channels (RPM/Torque/AFR default), collects a single run window (auto or button trigger), converts samples to the existing WinPEP-like CSV via `winpep8_synthesizer`.
- Constraints/guarantees: tuning math, kernels (k1/k2/k3), clamp rules, and CSV format remain unchanged; behavior is deterministic for a given input stream; restreaming back onto JetDrive is guarded/experimental.

---

## 1. Core Engine (`core/`)

The heart of DynoAI's tuning intelligence.

### `core/ai_tuner_toolkit_dyno_v1_2.py`
**Role:** Main CLI engine

**Responsibilities:**
- Parse command-line arguments (CSV path, output dir, clamping, smoothing passes)
- Load and validate WinPEP dyno logs
- Bin AFR measurements into RPM/kPa grid
- Calculate VE correction factors from AFR error
- Apply smoothing kernel (default or experimental)
- Enforce clamping limits (±7% to ±15%)
- Generate outputs:
  - `VE_Correction_Delta_DYNO.csv` - Percentage corrections
  - `Diagnostics_Report.txt` - Comprehensive analysis
  - `Spark_Adjust_Suggestion_*.csv` - Timing recommendations
  - `Coverage_*.csv` - Data coverage heatmaps
  - `manifest.json` - Run metadata

**Key Algorithms:**
- AFR error → VE correction mapping
- Multi-pass smoothing with configurable kernel
- Coverage-weighted averaging
- Gradient limiting
- Hot/cold compensation

**Inputs:**
- WinPEP CSV (columns: rpm, map_kpa, afr_cmd_f/r, afr_meas_f/r, ve_f/r, spark_f/r, etc.)
- Optional base VE tables for absolute output

**Outputs:**
- VE correction deltas (apply to base tables)
- Spark timing suggestions
- Diagnostics and coverage reports

### `core/ve_operations.py`
**Role:** VE table apply/rollback with hash verification

**Classes:**
- `VEApply`: Applies correction factors to base VE tables
- `VERollback`: Reverses VE corrections using metadata

**Key Features:**
- SHA-256 hash verification (prevents rollback of tampered files)
- Configurable clamping (±1% to ±15%)
- 4-decimal precision output
- Metadata generation (base_sha, factor_sha, applied_at_utc, max_adjust_pct)
- Dry-run mode for preview

**Safety Mechanisms:**
- Hash mismatch blocks rollback
- Clamping enforced before multiplication
- Grid dimension validation

### `core/io_contracts.py`
**Role:** Path safety and file fingerprinting

**Functions:**
- `compute_sha256()`: Deterministic file hashing
- Path validation: Prevents traversal outside repo root
- Canonical naming: Enforces consistent file naming conventions

**Safety Mechanisms:**
- Rejects `..` in paths
- Validates output directories are within repo
- Provides audit trail via hashes

### `core/dynoai/` Package
**Role:** Shared utilities

**Modules:**
- `api/xai_blueprint.py`: Flask blueprint for xAI Grok chat proxy
- `clients/xai_client.py`: xAI API client wrapper
- `constants.py`: Shared constants

**Status:** Non-critical, optional for web service integration

---

## 2. Test Stack (`tests/`)

Comprehensive test coverage ensuring correctness at every layer.

### Test Layers

```
tests/
├── selftest.py              # Smoke test (synthetic CSV → full pipeline)
├── selftest_runner.py       # Legacy smoke test (alternative harness)
├── acceptance_test.py       # VE operations acceptance (8 scenarios)
├── unit/                    # PyTest unit tests
│   ├── test_bin_alignment.py      # Grid mismatch detection
│   ├── test_delta_floor.py        # Delta flooring (<0.001% → 0.000%)
│   ├── test_fingerprint.py        # Kernel fingerprint generation
│   └── test_runner_paths.py       # Path traversal protection
├── integration/             # PyTest integration tests
│   ├── test_xai_blueprint.py      # Flask blueprint wiring
│   └── test_xai_client.py         # xAI API client
└── kernels/                 # Kernel harness tests
    ├── test_k1.py                 # K1 gradient-limited
    ├── test_k2.py                 # K2 coverage-adaptive
    ├── test_k2_fixed.py           # K2 fixed variant
    └── test_k3.py                 # K3 bilateral
```

### Test Execution

**Quick smoke test:**
```bash
python tests/selftest.py
```

**Full regression:**
```bash
pwsh scripts/dynoai_safety_check.ps1 -RunSelftests -RunKernels -RunPytest
```

**Expected Results:**
- Selftests: 2/2 passing
- Acceptance: 8/8 passing
- Kernel harnesses: 4/4 passing
- PyTest: 15/15 passing (7 unit + 8 integration)

---

## 3. Experimental Framework (`experiments/`)

Research and development environment for new smoothing kernels.

### Structure
```
experiments/
├── run_experiment.py        # Kernel experiment runner
├── protos/                  # Experimental kernels [MATH-CRITICAL]
│   ├── k1_gradient_limit_v1.py
│   ├── k2_coverage_adaptive_v1.py
│   ├── k3_bilateral_v1.py
│   ├── kernel_weighted_v1.py
│   └── kernel_knock_aware_v1.py
├── baseline_test_*/         # Experiment outputs
├── k*_test_*/               # Kernel-specific test runs
└── logs/                    # Experiment logs
```

### Experiment Runner

**Purpose:** Test experimental kernels against baseline without modifying core engine

**Usage:**
```bash
# Run with baseline (no kernel patching)
python experiments/run_experiment.py \
    --idea-id baseline \
    --csv data/sample.csv \
    --outdir experiments/baseline_test

# Run with K2 kernel
python experiments/run_experiment.py \
    --idea-id k2_coverage_adaptive_v1 \
    --csv data/sample.csv \
    --outdir experiments/k2_test

# Dry-run (validation only, no execution)
python experiments/run_experiment.py \
    --idea-id k1 \
    --csv data/sample.csv \
    --outdir experiments/k1_dryrun \
    --dry-run
```

**Mechanism:**
1. Imports baseline toolkit (`ai_tuner_toolkit_dyno_v1_2`)
2. Dynamically imports experimental kernel from `protos/`
3. Monkey-patches `kernel_smooth()` function in toolkit
4. Runs analysis with patched kernel
5. Generates fingerprint for reproducibility

**Safety:**
- Path traversal protection (outputs must be within repo)
- Idea-id validation (only known kernels allowed)
- Dry-run mode for testing without execution

---

## 4. Web Service (`web_service/`)

Optional Flask REST API for browser-based analysis.

### Structure
```
web_service/
├── api/
│   └── app.py              # Minimal Flask API
├── start-web.ps1           # Convenience launcher
├── test-api.ps1            # End-to-end API test
└── test-api-only.ps1       # API-only verification
```

### API Architecture

```
Browser (localhost:5173)
    ↓ HTTP
React Frontend (Vite)
    ↓ REST API
Flask Backend (localhost:5000)
    ↓ subprocess
Core Engine (ai_tuner_toolkit_dyno_v1_2.py)
    ↓
Outputs (CSV, JSON, Diagnostics)
```

### Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | Health check |
| `/api/xai/chat` | POST | xAI Grok chat proxy |

**Note:** The web service is minimal in the current version. Full upload/analysis endpoints can be added following the pattern in `DynoAI_2/api/app.py`.

### Dependencies
- Flask
- Flask-CORS
- requests (for xAI client)

---

## 5. Archive (`archive/`)

Historical code and artifacts preserved for reference.

### Contents
```
archive/
├── utilities/          # One-off helper scripts
├── visualizations/     # 3D plotting tools
├── gui/                # Legacy desktop GUI
├── vbnet/              # Parallel VB.NET implementation
├── ai_toolkit/         # Unrelated AI projects
├── docs/               # Legacy documentation
├── test_data/          # Sample CSVs and logs
└── artifacts/          # Historical run outputs
```

**Policy:** Archive is read-only by default. Use for reference or to resurrect old utilities, but do not modify in place.

---

## 6. Calibration Tables (`tables/`)

Reference VE tables and sample data.

### Base Tables
- `FXDLS_Wheelie_VE_Base_Front_fixed.csv` - Front cylinder base VE (corrected)
- `FXDLS_Wheelie_VE_Base_Front.csv` - Front cylinder base VE (original)
- `FXDLS_Wheelie_Spark_Delta.csv` - Spark timing deltas
- `FXDLS_Wheelie_AFR_Targets.csv` - Target AFR by RPM/kPa

### Sample Logs
- `WinPEP_Sample.csv` - Sample dyno log for testing
- `WinPEP_Log_Sample.csv` - Alternative sample format

**Usage:**
- Base tables used with `--base_front` / `--base_rear` CLI flags
- Sample logs used for testing and demonstrations
- Do not overwrite base tables; use VEApply to create updated versions

---

## 7. Scripts & Automation (`scripts/`)

Development and maintenance automation.

| Script | Purpose |
| --- | --- |
| `reorganize_repo.ps1` | Enforces v3 repository layout (dry-run by default) |
| `dynoai_safety_check.ps1` | Runs all safety tests (selftests, kernels, pytest) |
| `upload_to_github.ps1` | Automated GitHub upload script |
| `pre_upload_checklist.ps1` | Pre-upload validation (7 checks) |
| `clean_workspace.py` | Purge generated artifacts |
| `cleanup_outputs.py` | Remove old output directories |

**Principles:**
- Default to safe modes (dry-run, no deletion)
- Require explicit opt-in for destructive actions
- Provide clear logging and summaries

---

## 8. Data Flow

### Typical Workflow

```
1. Collect dyno data
   └─> WinPEP log (CSV)

2. Run DynoAI engine
   └─> python core/ai_tuner_toolkit_dyno_v1_2.py --csv log.csv --outdir outputs/run1

3. Review outputs
   └─> VE_Correction_Delta_DYNO.csv
   └─> Diagnostics_Report.txt
   └─> Spark_Adjust_Suggestion_*.csv

4. Apply VE corrections
   └─> python -c "from core.ve_operations import VEApply; VEApply().apply(...)"

5. Flash updated VE table to ECM
   └─> (external tool, e.g., TunerPro)

6. Test on dyno
   └─> Verify AFR targets met

7. Rollback if needed
   └─> python -c "from core.ve_operations import VERollback; VERollback().rollback(...)"
```

### Data Dependencies

```
WinPEP CSV
    ↓
Core Engine
    ├─> VE Correction Delta (percentage adjustments)
    ├─> Diagnostics Report (analysis summary)
    ├─> Spark Suggestions (timing recommendations)
    ├─> Coverage Maps (data quality heatmaps)
    └─> Manifest (run metadata)

Base VE Table + VE Correction Delta
    ↓
VE Apply
    └─> Updated VE Table (ready for ECM)
```

---

## 9. Component Interactions

### Engine ↔ Tests
- Tests invoke engine via subprocess
- Validate outputs (manifest, diagnostics, VE deltas)
- Check invariants (clamping, coverage, bin alignment)

### Engine ↔ Experiments
- Experiment runner imports engine as module
- Monkey-patches `kernel_smooth()` function
- Runs with experimental kernel, generates fingerprint

### Web Service ↔ Engine
- API receives CSV upload
- Invokes engine via subprocess
- Returns manifest and download links
- (Optional) Proxies xAI chat for tuning advice

### Tests ↔ Experiments
- Kernel harnesses import from `experiments/protos/`
- Validate kernel imports and execution
- Ensure experiments/ layout preserved after reorg

---

## 10. Security Architecture

### Path Safety
- All file operations validated by `io_contracts.py`
- Output directories must be within repo root
- Exception: `--dry-run` allows temp dirs for testing

### Hash Verification
- VE tables hashed with SHA-256
- Metadata stores base_sha and factor_sha
- Rollback blocked if hashes don't match

### Clamping Enforcement
- Default ±7% (multipliers in [0.93, 1.07])
- Configurable up to ±15% maximum
- Applied before VE table multiplication

### Input Validation
- CSV parsing rejects malformed data
- Bin alignment checked (no implicit reindexing)
- Idea-id validated against known kernels

---

## 11. Deployment Models

### Local CLI (Primary)
```bash
python core/ai_tuner_toolkit_dyno_v1_2.py --csv log.csv --outdir outputs/
```
- Single-user, local workstation
- Direct file system access
- No authentication required

### Web Service (Optional)
```bash
python web_service/api/app.py
```
- Browser-based UI
- Multi-user capable (with auth added)
- Upload/download via REST API

### CI/CD (Automated Testing)
```yaml
# .github/workflows/dynoai-ci.yml
- run: python tests/selftest.py
- run: python -m pytest tests/unit tests/integration -v
```
- Runs on every push/PR
- Validates on Ubuntu + Windows
- Blocks merge if tests fail

---

## 12. Extension Points

### Adding a New Kernel
1. Create `experiments/protos/kN_description_v1.py`
2. Implement `kernel_smooth(grid, passes=2, ...)` function
3. Add to `experiments/run_experiment.py` IDEAS dict
4. Create `tests/kernels/test_kN.py` harness
5. Document in experiment notes

### Adding a New CLI Flag
1. Update argparse in `core/ai_tuner_toolkit_dyno_v1_2.py`
2. Implement logic in main processing loop
3. Add test coverage in `tests/selftest.py` or new unit test
4. Update `docs/DYNOAI_CORE_REFERENCE.md`

### Adding a New API Endpoint
1. Add route to `web_service/api/app.py`
2. Implement handler function
3. Add integration test in `tests/integration/`
4. Update API documentation

---

## 13. Performance Characteristics

### Typical Run Times
- **Small dataset** (1000 rows): 1-2 seconds
- **Medium dataset** (5000 rows): 3-5 seconds
- **Large dataset** (20000 rows): 10-15 seconds

### Memory Usage
- **Baseline:** ~50 MB
- **Large dataset:** ~200 MB
- **Peak:** During smoothing kernel execution

### Bottlenecks
- CSV parsing (I/O bound)
- Multi-pass smoothing (CPU bound)
- Coverage map generation (memory bound for large grids)

---

## 14. Technology Stack

### Core
- **Language:** Python 3.11+
- **Key Libraries:** csv (stdlib), json (stdlib), math (stdlib), pathlib (stdlib)
- **Optional:** jsonschema (for VE metadata validation)

### Testing
- **Framework:** pytest
- **Coverage:** pytest-cov (optional)
- **Mocking:** unittest.mock

### Web Service
- **Framework:** Flask
- **CORS:** Flask-CORS
- **HTTP Client:** requests (for xAI)

### CI/CD
- **Platform:** GitHub Actions
- **Security:** Snyk, CodeQL
- **Automation:** PowerShell 7+

---

## 15. Maintenance and Evolution

### Version Strategy
- **Major:** Breaking changes to CLI or output formats
- **Minor:** New features, experimental kernels
- **Patch:** Bug fixes, documentation updates

### Backward Compatibility
- VE table format is stable (CSV with RPM/kPa grid)
- Manifest schema versioned (`app_version` field)
- Metadata includes version for rollback compatibility

### Deprecation Policy
- Old kernels moved to `archive/` but not deleted
- Legacy test harnesses retained for compatibility
- Breaking changes announced in CHANGELOG.md

---

## 16. Future Architecture Considerations

### Potential Enhancements
- Real-time dyno streaming (WebSocket support)
- Multi-cylinder support (V-twin → inline-4, V4)
- Cloud deployment (containerized API)
- Machine learning kernel (data-driven smoothing)
- Mobile app (iOS/Android)

### Constraints
- Must preserve math-critical file stability
- Must maintain test coverage ≥80%
- Must support offline/local operation
- Must not require internet for core functionality

---

## 17. v3 Minimal Repo Cutover

This section documents the migration process from DynoAI v2 to v3.

### Overview
DynoAI v3 is a **minimal, production-focused repository** that includes only code actively referenced by v2's pipeline, tests, and selftests. Unused and legacy modules are not included in v3.

### Migration Steps

**Step 1: Check out DynoAI v2**
```bash
git clone https://github.com/your-org/DynoAI_2.git
cd DynoAI_2
```

**Step 2: Run the materialization script**
```bash
python scripts/materialize_v3_minimal_tree.py \
    --source-root <path-to-v2> \
    --target-root <path-to-new-v3>
```

This script:
- Analyzes v2's import graph, test references, and selftest dependencies
- Copies only the files actively used by the production pipeline
- Excludes legacy, experimental, and unused modules
- Preserves directory structure for active components

**Step 3: Change into the v3 directory**
```bash
cd <path-to-new-v3>
```

**Step 4: Validate the v3 installation**

Run the selftest runner:
```bash
python selftest_runner.py
```

Run all pytest tests:
```bash
python -m pytest tests/ -v
```

Expected results:
- All selftests passing (2/2)
- All pytest tests passing (15/15)
- No import errors or missing dependencies

**Step 5: Initialize new git repository**
```bash
git init
git add .
git commit -m "Initial commit: DynoAI v3 minimal cutover"
git remote add origin https://github.com/your-org/DynoAI_3.git
git push -u origin main
```

### What's Included in v3
- ✅ Core engine (`core/ai_tuner_toolkit_dyno_v1_2.py`)
- ✅ VE operations (`core/ve_operations.py`)
- ✅ I/O contracts and safety (`core/io_contracts.py`)
- ✅ Full test suite (`tests/`)
- ✅ Active experimental kernels (`experiments/protos/`)
- ✅ Production scripts (`scripts/`)
- ✅ Reference tables and templates (`tables/`, `templates/`)
- ✅ Essential documentation (`docs/`)

### What's Excluded from v3
- ❌ Archive directory (legacy GUI, VB.NET implementations, old utilities)
- ❌ Unused web service prototypes
- ❌ Dead code identified by static analysis
- ❌ Duplicate or superseded implementations
- ❌ Historical test data not referenced by current tests

### Key Principle
**v3 only includes code referenced by v2 pipeline/tests/selftests. Unused or legacy modules are not included.**

This ensures:
- Reduced maintenance burden
- Clear dependency graph
- Faster CI/CD execution
- Easier onboarding for new developers
- Production-ready baseline for future enhancements

---

**For implementation details, see:**
- `docs/DYNOAI_CORE_REFERENCE.md` - Minimal runnable examples
- `docs/DYNOAI_SAFETY_RULES.md` - Safety policies and invariants
- `README.md` - Quick start and troubleshooting

