# DynoAI3 Full System Snapshot

**Generated:** 2025-12-13T15:03:09Z  
**Repository:** rob9206/DynoAI_3  
**Purpose:** Complete, current, engineering-accurate snapshot of DynoAI3 system

---

## A) REPOSITORY STRUCTURE

### Full Repository Tree (Major Components)

```
DynoAI_3/
├── ai_tuner_toolkit_dyno_v1_2.py     # Core tuning engine (2171 lines)
├── ve_operations.py                   # VE apply/rollback system (731 lines)
├── io_contracts.py                    # I/O validation & manifest (594 lines)
├── selftest_runner.py                 # Test entry point (22 lines)
├── selftest.py                        # Self-test suite (97 lines)
├── preflight_csv.py                   # CSV preflight validation (163 lines)
├── decel_management.py                # Decel fuel management (745 lines)
├── cylinder_balancing.py              # Per-cylinder balancing (579 lines)
├── heat_management.py                 # Thermal management (316 lines)
├── knock_optimization.py              # Spark optimization (221 lines)
├── tuning_wizards.py                  # High-level tuning wizards (750 lines)
├── acceptance_test.py                 # End-to-end acceptance tests (434 lines)
│
├── api/                               # Flask REST API
│   ├── app.py                         # Main Flask application
│   ├── routes/                        # API endpoints
│   │   ├── jetdrive.py                # JetDrive integration endpoints
│   │   ├── powercore.py               # Power Core integration
│   │   ├── wizards.py                 # Tuning wizard endpoints
│   │   └── jetstream/                 # Jetstream protocol endpoints
│   └── services/                      # Business logic layer
│       ├── autotune_workflow.py       # Unified analysis engine (854 lines)
│       ├── agent_orchestrator.py      # AI agent coordinator (626 lines)
│       ├── jetdrive_client.py         # KLHDV multicast protocol (505 lines)
│       ├── powercore_integration.py   # PVV XML generation (609 lines)
│       ├── livelink_client.py         # LiveLink dyno comm (559 lines)
│       ├── session_logger.py          # Session management (478 lines)
│       ├── training_data_collector.py # AI training data (482 lines)
│       ├── run_manager.py             # Run lifecycle (337 lines)
│       └── wp8_parser.py              # WinPEP8 parser (328 lines)
│
├── dynoai/                            # Core library modules
│   ├── constants.py                   # Bin definitions & grid dimensions
│   ├── api/xai_blueprint.py           # XAI chat endpoint
│   └── clients/xai_client.py          # XAI/Grok client
│
├── frontend/                          # React/TypeScript UI
│   └── src/
│       ├── pages/JetDriveAutoTunePage.tsx
│       └── components/
│
├── tests/                             # Test suite
│   ├── test_autotune_workflow.py
│   ├── test_agent_orchestrator.py
│   ├── test_cylinder_balancing.py
│   ├── test_decel_management.py
│   ├── test_bin_alignment.py
│   ├── test_preflight_csv.py
│   └── api/                           # API-specific tests
│
├── experiments/                       # Kernel validation experiments
│   ├── k1_test_dense/                 # K1 kernel dense data tests
│   ├── k1_test_sparse/                # K1 kernel sparse data tests
│   ├── k2_*_test/                     # K2 kernel validation runs
│   └── baseline_test_*/               # Baseline comparison data
│
├── docs/                              # Documentation
├── scripts/                           # CLI automation tools
├── migrations/                        # Database migrations (Alembic)
└── config/                            # Configuration files
```

---

### Major Module Responsibilities

#### **ai_tuner_toolkit_dyno_v1_2.py** (Core Tuning Engine)

**Purpose:** Main CLI entry point for dyno log analysis and VE correction generation.

**Key Functions:**
- `main()` - CLI entry point, orchestrates full pipeline
- `load_winpep_csv()` - Parse WinPEP/WinPEP8 CSV/TXT logs (tab or comma delimited)
- `load_generic_csv()` - Parse PowerVision and generic dyno logs
- `detect_csv_format()` - Auto-detect log format (WinPEP, PowerVision, generic)
- `dyno_bin_aggregate()` - Aggregate AFR error by RPM×MAP bins (11×5 grid)
- `kernel_smooth()` - K1 gradient-limited kernel smoothing (4 stages)
- `combine_front_rear()` - Merge front/rear cylinder data
- `spark_suggestion()` - Generate spark timing adjustments from knock data
- `enforce_rear_rule()` - Apply rear cylinder safety rule (2800-3600 RPM, 75-95 kPa)
- `apply_delta_to_base()` - Apply percentage VE deltas to base VE tables
- `write_matrix_csv()` - Write grid data to CSV with sanitization
- `anomaly_diagnostics()` - Detect outliers, coverage gaps, inconsistencies

**Key Classes:** None (functional design)

**Data Flow:**
1. CSV → format detection → parser selection
2. Parser → validated records (rpm, kpa, torque, AFR_cmd, AFR_meas, knock, IAT)
3. Records → binning by RPM×MAP → weighted aggregation (torque or HP weighted)
4. AFR error % → K1 kernel smoothing → clamping (±12% default)
5. Knock + IAT → spark suggestions
6. Outputs → CSV, paste-ready TXT, HTML, PNG, JSON manifest

**Invariants:**
- Grid: 11 RPM bins × 5 kPa bins = 55 cells
- RPM bins: [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
- kPa bins: [35, 50, 65, 80, 95]
- VE delta clamp: ±12% (configurable via `--clamp`)
- Spark suggestions: -2.0° max retard for knock

---

#### **ve_operations.py** (VE Apply/Rollback System)

**Purpose:** Safe, auditable VE table modification with full rollback capability.

**Key Classes:**
- `VEApply` - Apply correction factors to base VE table
  - `apply()` - Multiply base VE by (1 + factor/100), clamped to ±7%
  - Writes updated VE + metadata JSON with SHA-256 hashes
  
- `VERollback` - Reverse VE corrections
  - `rollback()` - Divide by previous factors to restore original VE
  - Verifies factor file hash before rollback
  
- `DualCylinderVEApply` - Atomic-like apply for both cylinders
  - Validates all inputs before writing
  - Best-effort atomicity (no true transactions)

**Key Functions:**
- `read_ve_table()` - Parse VE CSV (RPM, kPa headers + grid)
- `write_ve_table()` - Write VE CSV with 4-decimal precision
- `clamp_factor_grid()` - Clamp correction factors to ±7% default
- `compute_sha256()` - Hash files for integrity verification
- `analyze_cylinder_delta()` - Compare front/rear VE tables

**Invariants:**
- VE factors clamped to ±7% (DEFAULT_MAX_ADJUST_PCT)
- Updated VE = base_ve × (1 + factor/100)
- Rollback VE = current_ve / (1 + factor/100)
- Metadata includes: base_sha, factor_sha, timestamp, app_version
- All paths validated via `io_contracts.safe_path()`

**Data Contracts:**
- Input: VE CSV with header `RPM, kPa1, kPa2, ...`
- Factor CSV: Percentage values (e.g., +5.0 = +5%)
- Output: 4-decimal precision VE values

---

#### **io_contracts.py** (I/O Validation & Manifest System)

**Purpose:** Centralized I/O safety, manifest generation, and schema validation.

**Key Functions:**
- `safe_path(path, allow_parent_dir=False)` - Prevent directory traversal attacks
  - Resolves symlinks, validates against project root
  - Returns resolved Path object
  
- `make_run_id(prefix="")` - Generate unique run IDs (timestamp + random suffix)
- `file_sha256(path)` - Compute SHA-256 hash (64KB buffer)
- `utc_now_iso()` - ISO timestamp with milliseconds
- `sanitize_csv_cell(value)` - Prepend `'` to numeric strings for Excel safety
- `create_manifest(run_id, input_csv, args)` - Initialize run manifest
- `add_output_entry(manifest, filename, path, type, schema)` - Register output file
- `finish_manifest(manifest, ok, last_stage, stats)` - Finalize with timing/status
- `write_manifest_pair(manifest, outdir, run_id)` - Write JSON manifest + README
- `validate_outputs_against_manifest(outdir, manifest)` - Verify outputs exist

**Manifest Schema (JSON):**
```json
{
  "schema_id": "dynoai.manifest@1",
  "run_id": "2025-11-19T21-47-29Z-6060bf",
  "input": {"path": "data.csv", "sha256": "abc123...", "rows": 1234},
  "args": {"clamp": 12.0, "smooth_passes": 2, ...},
  "timing": {"start": "...", "end": "...", "elapsed_s": 4.2},
  "outputs": [
    {"file": "VE_Correction_Delta_DYNO.csv", "type": "csv", "schema": "ve_delta_grid", "rows": 11, "cols": 5, "sha256": "..."}
  ],
  "ok": true,
  "last_stage": "export",
  "stats": {"rows_read": 1234, "bins_covered": 45}
}
```

**Invariants:**
- All file I/O goes through `safe_path()`
- Manifests written atomically (temp file + rename)
- SHA-256 hashes for all inputs/outputs
- REQUIRED_COLUMNS: ("rpm", "map_kpa", "torque")

---

#### **selftest_runner.py** (Test Entry Point)

**Purpose:** Stable entry point for self-test suite.

**Key Functions:**
- `main()` - Imports and executes `selftest.main()`

**Usage:**
```bash
python selftest_runner.py
```

---

#### **tests/** (Test Infrastructure)

**Test Coverage:**
- `test_autotune_workflow.py` - End-to-end workflow validation
- `test_agent_orchestrator.py` - Agent task delegation
- `test_cylinder_balancing.py` - Per-cylinder AFR balancing
- `test_decel_management.py` - Decel fuel cut logic
- `test_bin_alignment.py` - RPM/MAP binning accuracy
- `test_preflight_csv.py` - CSV validation rules
- `test_file_not_found_handling.py` - Error handling
- `test_delta_floor.py` - Delta clamping behavior
- `test_fingerprint.py` - Determinism verification
- `api/` - API endpoint tests

**Test Strategy:**
- Unit tests for core math (binning, aggregation, kernel smoothing)
- Integration tests for workflows (CSV → VE delta → PVV XML)
- Determinism tests (same input → same output)
- Error handling tests (malformed CSV, missing columns)

---

## B) END-TO-END DATA FLOW

### Pipeline Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: INPUT & PARSING                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
           WinPEP/Dynojet CSV ──────┤
           PowerVision CSV ─────────┤
           Generic CSV ─────────────┤
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │ detect_csv_format()  │
                        │  • WinPEP markers    │
                        │  • PowerVision cols  │
                        │  • Generic fallback  │
                        └──────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌─────────────────────┐       ┌─────────────────────┐
        │ load_winpep_csv()   │       │ load_generic_csv()  │
        │  • Tab/comma sniff  │       │  • PowerVision AFR  │
        │  • Front/rear AFR   │       │  • Lambda→AFR conv  │
        │  • Knock channels   │       │  • Torque from HP   │
        └─────────────────────┘       └─────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Validated Record Stream      │
                    │  • rpm, kpa, torque          │
                    │  • afr_cmd_f/r, afr_meas_f/r │
                    │  • knock_f/r, iat, tps       │
                    └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: SIGNAL ALIGNMENT & PREPROCESSING                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Validation & Filtering       │
                    │  • AFR range: 9.0-18.0       │
                    │  • IAT range: 30-300°F       │
                    │  • MAP range: 10-110 kPa     │
                    │  • TPS range: 0-100%         │
                    │  • Torque > 5 ft-lb (load)   │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ AFR Error Calculation        │
                    │  afr_err_pct =               │
                    │    (afr_cmd - afr_meas)      │
                    │    / afr_meas × 100          │
                    └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: KERNEL EXECUTION (K1)                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ dyno_bin_aggregate()         │
                    │  • nearest_bin(rpm, kpa)     │
                    │  • Torque/HP weighting       │
                    │  • Per-bin accumulation:     │
                    │    - sums[r][k] += err × w   │
                    │    - weights[r][k] += w      │
                    │  • Coverage tracking         │
                    │  • MAD (outlier detection)   │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Grid Calculation             │
                    │  grid[r][k] =                │
                    │    sums[r][k] / weights[r][k]│
                    │  if weights[r][k] > 0        │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ combine_front_rear()         │
                    │  • Average F+R cylinders     │
                    │  • Single-cylinder fallback  │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ kernel_smooth() - K1 Kernel  │
                    │ ┌──────────────────────────┐ │
                    │ │ Stage 1: Gradient Calc   │ │
                    │ │  • Max neighbor diff     │ │
                    │ │  • Per-cell gradient map │ │
                    │ └──────────────────────────┘ │
                    │ ┌──────────────────────────┐ │
                    │ │ Stage 2: Adaptive Smooth │ │
                    │ │  • ≥3%: 0 passes         │ │
                    │ │  • ≤1%: full passes      │ │
                    │ │  • 1-3%: linear taper    │ │
                    │ └──────────────────────────┘ │
                    │ ┌──────────────────────────┐ │
                    │ │ Stage 3: Gradient Blend  │ │
                    │ │  • High gradient → orig  │ │
                    │ │  • Low gradient → smooth │ │
                    │ └──────────────────────────┘ │
                    │ ┌──────────────────────────┐ │
                    │ │ Stage 4: Coverage Weight │ │
                    │ │  • α=0.20 blend factor   │ │
                    │ │  • Center bias 1.25      │ │
                    │ └──────────────────────────┘ │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ clamp_grid(±12%)             │
                    │  • Safety clamp for VE delta │
                    └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: VE DELTA COMPUTATION                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ VE Correction Delta Grid     │
                    │  • 11×5 grid (55 cells)      │
                    │  • Percentage values         │
                    │  • Clamped to ±12%           │
                    └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: PREVIEW vs APPLY                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌────────────────────┐        ┌────────────────────┐
        │ PREVIEW (Default)  │        │ APPLY (ve_ops)     │
        │  • CSV output      │        │  VEApply.apply()   │
        │  • Paste-ready TXT │        │  • Read base VE    │
        │  • No VE mods      │        │  • Clamp factors   │
        └────────────────────┘        │  • Multiply:       │
                                      │    VE × (1+Δ/100)  │
                                      │  • Write updated   │
                                      │  • Generate meta   │
                                      └────────────────────┘
                                                │
                                                ▼
                                      ┌────────────────────┐
                                      │ ROLLBACK (ve_ops)  │
                                      │  VERollback.rollback()│
                                      │  • Verify hash     │
                                      │  • Divide:         │
                                      │    VE / (1+Δ/100)  │
                                      └────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 6: OUTPUT ARTIFACTS                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Output Directory Structure   │
                    │                              │
                    │ runs/{run_id}/               │
                    │  ├── VE_Correction_Delta_DYNO.csv
                    │  ├── VE_Delta_PasteReady.txt│
                    │  ├── AFR_Error_Map_Front.csv│
                    │  ├── AFR_Error_Map_Rear.csv │
                    │  ├── Spark_Adjust_*_Front.csv│
                    │  ├── Spark_Adjust_*_Rear.csv│
                    │  ├── Coverage_Front.csv     │
                    │  ├── Coverage_Rear.csv      │
                    │  ├── Torque_Map_*.csv       │
                    │  ├── HP_Map_*.csv           │
                    │  ├── Diagnostics_Report.txt │
                    │  ├── Anomaly_Hypotheses.json│
                    │  ├── manifest.json          │
                    │  └── README.txt             │
                    │                              │
                    │ ve_runs/{run_id}/            │
                    │  ├── VE_Front_Updated.csv   │
                    │  ├── VE_Rear_Updated.csv    │
                    │  ├── VE_Front_Updated_meta.json│
                    │  └── VE_Rear_Updated_meta.json│
                    │                              │
                    │ ve_runs/preview/             │
                    │  └── (dry-run outputs)       │
                    └──────────────────────────────┘
```

### Kernel Ordering & Guarantees

**K1 Kernel (kernel_smooth):**
- **Purpose:** Gradient-limited smoothing preserving large corrections
- **Stages:** Always executed in order: Gradient → Adaptive → Blend → Coverage
- **Determinism:** Pure function, no randomness, no cross-run state
- **Inputs:** Grid (11×5), passes (int), gradient_threshold (float)
- **Outputs:** Smoothed grid (same dimensions)

**No K2/K3:** Current implementation uses only K1 kernel. Historical references in `experiments/` suggest K2 was tested but not deployed.

### Preview vs Apply Parity

**Preview Mode (Default):**
- Writes CSV/TXT files to `runs/{run_id}/`
- No VE table modification
- User reviews, manually copies to tuner

**Apply Mode (ve_operations.py):**
- Uses `VEApply.apply()` or `DualCylinderVEApply.apply()`
- Applies same clamping (±7% vs ±12% for preview)
- Writes to `ve_runs/{run_id}/`
- **Parity guarantee:** Apply uses identical clamping logic to preview

**Rollback:**
- `VERollback.rollback()` reverses apply
- Verifies factor file hash unchanged
- Mathematical inverse: `VE / (1 + factor/100)`

---

## C) DETERMINISTIC MATH GUARANTEES

### Tuning Stage Invariants

#### **Stage 1: Binning**
- **Inputs:** rpm (float), kpa (float), RPM_BINS (list), KPA_BINS (list)
- **Outputs:** rpm_bin (int), kpa_bin (int)
- **Algorithm:** `nearest_bin()` - find minimum absolute difference
- **Determinism:** Pure function, no randomness
- **Invariants:**
  - Same input → same bin
  - RPM_BINS = [1500, 2000, ..., 6500] (11 bins)
  - KPA_BINS = [35, 50, 65, 80, 95] (5 bins)

#### **Stage 2: Aggregation**
- **Inputs:** Records (list), weight_mode (torque or HP)
- **Outputs:** Grid (11×5), coverage (11×5), MAD (11×5)
- **Algorithm:** Weighted sum / total weight
  ```python
  sums[r][k] += afr_err × weight
  weights[r][k] += weight
  grid[r][k] = sums[r][k] / weights[r][k]
  ```
- **Determinism:** Deterministic for same input order (floating-point stable)
- **Invariants:**
  - Weight > 0 required for inclusion
  - AFR error clamped to validation range
  - Division by zero → None (no data)

#### **Stage 3: K1 Kernel Smoothing**
- **Inputs:** Grid (11×5), passes (int), gradient_threshold (float)
- **Outputs:** Smoothed grid (11×5)
- **Algorithm:** 4-stage gradient-limited smoothing
  - Stage 1: Gradient = max(|center - neighbor|) for 4 neighbors
  - Stage 2: Adaptive passes = f(correction magnitude)
    - ≥3%: 0 passes (preserve large corrections)
    - ≤1%: full passes (smooth noise)
    - 1-3%: linear taper
  - Stage 3: Blend = gradient > threshold ? original : smoothed
  - Stage 4: Coverage-weighted smoothing (α=0.20, center_bias=1.25)
- **Determinism:** Pure function, no randomness, deterministic rounding
- **Invariants:**
  - Grid dimensions unchanged
  - None cells remain None
  - No cross-cell state leakage

#### **Stage 4: Clamping**
- **Inputs:** Grid (11×5), clamp (float, default 12.0)
- **Outputs:** Clamped grid (11×5)
- **Algorithm:** `max(-clamp, min(clamp, value))`
- **Determinism:** Pure function
- **Invariants:**
  - All values ∈ [-clamp, +clamp]
  - Preview clamp (12%) != Apply clamp (7%)

#### **Stage 5: VE Apply**
- **Inputs:** base_ve (11×5), factor (11×5), max_adjust_pct (7.0)
- **Outputs:** updated_ve (11×5)
- **Algorithm:**
  ```python
  clamped_factor = clamp(factor, -7, +7)
  updated_ve = base_ve × (1 + clamped_factor / 100)
  ```
- **Determinism:** Pure function, IEEE 754 floating-point stable
- **Invariants:**
  - Factor clamped to ±7%
  - Multiplier ∈ [0.93, 1.07]
  - Base VE unchanged (file integrity verified via SHA-256)

### No Randomness Confirmation

**Sources checked:**
- `ai_tuner_toolkit_dyno_v1_2.py`: No `random`, no `np.random`, no `secrets`
- `ve_operations.py`: No `random`
- `dyno_bin_aggregate()`: Deterministic weighted sum
- `kernel_smooth()`: Deterministic neighbor averaging
- `make_run_id()`: Uses `os.urandom()` for ID generation ONLY (not in math)

**Verdict:** ✅ All tuning math is deterministic. Same CSV → Same VE delta.

### No Adaptive Learning

**Confirmation:**
- No model persistence (`*.pkl`, `*.h5`, `*.pt`)
- No cross-run state files
- Each run isolated by `run_id`
- No feedback loop from previous runs

**Verdict:** ✅ No adaptive learning. Each run is independent.

### No Hidden Smoothing

**All smoothing is explicit:**
- K1 kernel: 4 stages documented above
- No post-processing smoothing
- No automatic smoothing beyond user-controlled `--smooth-passes`

**Verdict:** ✅ No hidden smoothing.

### No Cross-Run State Leakage

**Run isolation:**
- Each run gets unique `run_id` (timestamp + random suffix)
- Outputs written to `runs/{run_id}/`
- No shared state files
- No global caches persisted to disk

**Verdict:** ✅ No cross-run state leakage.

---

## D) AI ROLE AND BOUNDARIES

### Where AI is Invoked

**1. XAI/Grok Chat Endpoint** (`dynoai/api/xai_blueprint.py`)
- **Route:** `POST /api/xai/chat`
- **Purpose:** Conversational AI for tuning advice, diagnostics interpretation
- **Inputs:** User messages (JSON)
- **Outputs:** Grok response (text)
- **Boundaries:** Cannot modify code, cannot access filesystem, cannot change tuning math

**2. Agent Orchestrator** (`api/services/agent_orchestrator.py`)
- **Purpose:** Route tasks to specialized agents (Reorg, BugFix, Guardian, PowerCore)
- **Agents:**
  - **Reorg Agent:** Folder structure, CI/CD, docs (forbidden: tuning math)
  - **BugFix Agent:** Import errors, CSV robustness (forbidden: VE formulas, kernels)
  - **Guardian Agent:** Math review ONLY (forbidden: code changes)
  - **PowerCore Agent:** Log parsing, PVV generation (forbidden: VE formulas, kernels)
- **Boundaries:** Each agent has explicit `forbidden` list preventing tuning math changes

**3. Training Data Collector** (`api/services/training_data_collector.py`)
- **Purpose:** Collect dyno run data for future model training
- **Current Use:** Data collection only, no trained models deployed
- **Boundaries:** Read-only, does not influence tuning calculations

### What AI Can See

**XAI Chat:**
- User-provided context (tuning questions, diagnostic reports)
- No direct access to run files, CSV data, or VE tables

**Agent Orchestrator:**
- Task descriptions, file paths affected
- No direct execution of tuning code

**Training Data Collector:**
- Run manifests, CSV logs, AFR error grids
- Used for offline analysis, not real-time tuning

### What AI Can Output

**XAI Chat:**
- Text responses (explanations, suggestions)
- No code execution, no file writes

**Agent Orchestrator:**
- Task assignments, workflow coordination
- No direct code edits (agents execute changes)

### Hard Boundaries Preventing AI from Modifying Tuning Math

**1. Forbidden Lists:**
```python
# From agent_orchestrator.py
"forbidden": [
    "tuning_math",
    "ve_operations",
    "afr_calculations",
    "kernel_behavior",
    "ve_formulas",
    "kernel_algorithms",
]
```

**2. Code Isolation:**
- Tuning math in `ai_tuner_toolkit_dyno_v1_2.py` and `ve_operations.py`
- AI agents limited to infrastructure, docs, log parsing

**3. Guardian Agent:**
- Reviews changes for safety
- Cannot edit code, only approve/reject

**4. No Model Deployment:**
- No trained models (`*.pkl`, `*.h5`) in production pipeline
- No ML inference in tuning calculations

### Advisory & Explainability

**AI suggestions remain advisory:**
- XAI chat provides explanations, not commands
- User must manually review and apply
- No auto-apply of AI recommendations

**Explainability:**
- All tuning math is deterministic, inspectable
- Manifest includes full provenance (input CSV, args, timing)
- Diagnostics report explains outliers, coverage gaps

**Verdict:** ✅ AI is advisory only, hard boundaries prevent tuning math modification.

---

## E) FORMAL DATA CONTRACTS

### CSV Input Formats

#### **WinPEP/WinPEP8 Format**
- **Delimiters:** Tab or comma (auto-detected via `csv.Sniffer`)
- **Encoding:** UTF-8-sig (BOM-safe) or CP1252 (fallback)
- **Required Columns:**
  - `rpm` or `RPM` or `engine_rpm`
  - `map` or `kpa` or `MAP_kPa`
  - `torque` or `Torque` or `tq`
- **Optional Columns:**
  - `afr_cmd_f` / `afr_cmd_r` - Commanded AFR (front/rear)
  - `afr_meas_f` / `afr_meas_r` - Measured AFR (front/rear)
  - `knock_f` / `knock_r` - Knock retard (degrees)
  - `iat` - Intake air temperature (°F)
  - `vbatt` - Battery voltage
  - `tps` - Throttle position (%)
  - `hp` - Horsepower

**Column Matching:** Case-insensitive substring match
- Example: `"AFR Cmd F"`, `"afr_cmd_front"`, `"cmd_afr_f"` all match `afr_cmd_f`

#### **PowerVision Format**
- **Markers:**
  - `(PV) Engine Speed`
  - `(PV) Manifold Absolute Pressure`
  - `(PV) WBO2 AFR Front`
  - `(Harley - ECU Type 22 SW Level 621) ...`
- **Lambda Conversion:** If AFR column is invalid (e.g., constant 5.1), derive from lambda:
  ```python
  afr_meas = lambda × STOICH_AFR_GASOLINE  # 14.57
  ```
- **Torque Derivation:** If torque missing but HP present:
  ```python
  torque = (HP × 5252) / RPM
  ```

#### **Generic CSV Format**
- **Required Columns:** `rpm`, `map_kpa`, `torque` (or `hp` for derivation)
- **Fallbacks:** Same lambda→AFR and HP→torque conversions as PowerVision

### Units & Scaling

| Channel | Unit | Range | Notes |
|---------|------|-------|-------|
| RPM | revolutions/min | 400-8000 | Idle to redline |
| MAP/kPa | kilopascals | 10-110 | 35=cruise, 95=WOT |
| Torque | ft-lb | >5 | Minimum 5 ft-lb for load filtering |
| Horsepower | HP | - | Converted to torque if needed |
| AFR | ratio | 9.0-18.0 | Stoich=14.57, 12.2=WOT |
| Lambda | ratio | 0.6-1.3 | λ=1.0=stoich |
| IAT | °F | 30-300 | 120°F = hot threshold |
| TPS | % | 0-100 | Throttle position |
| Knock | degrees | 0-10 | Spark retard |
| Battery | volts | 10-16 | Typical 12V system |

### Error Handling for Malformed CSVs

**Preflight Validation** (`preflight_csv.py`):
- Checks for required columns before main processing
- Validates delimiter (tab vs comma)
- Detects BOM, encoding issues
- Reports missing columns with helpful hints

**Graceful Degradation:**
- Missing optional columns → Skipped (e.g., no knock → no spark suggestions)
- Invalid AFR → Lambda fallback
- Missing torque → HP derivation
- Rows with missing required fields → Skipped with diagnostic counter

**Error Messages:**
```python
raise RuntimeError(
    f"Missing required columns in WinPEP CSV: {', '.join(missing)}\n\n"
    f"Available columns: {available_cols}\n\n"
    f"Hint: Column names are matched using substrings (case-insensitive).\n"
    f"Expected column patterns:\n"
    f"  - RPM: 'rpm', 'engine rpm', 'motor rpm'\n"
    f"  - MAP: 'map', 'kpa', 'manifold', 'pressure'\n"
    f"  - Torque: 'torque', 'tq', 'ft-lb'"
)
```

### io_contracts.safe_path Usage

**All New I/O:**
- **File reads:** `safe_path(path, allow_parent_dir=True)` for CSVs outside project root
- **File writes:** `safe_path(path)` for outputs within project
- **Security:** Prevents `../` traversal, resolves symlinks

**Examples:**
```python
# VE operations
safe_csv = io_contracts.safe_path(str(csv_path), allow_parent_dir=True)
with open(safe_csv, newline="") as f:
    ...

# Main toolkit
target = io_contracts.safe_path(str(path))
with open(target, "w", newline="") as f:
    ...
```

**Invariant:** ✅ All file I/O goes through `safe_path()`.

---

## F) AUTOMATION & HEADLESS OPERATION

### Headless Entry Points

**1. CLI (Primary)**
```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv data.csv \
  --outdir ./results \
  --base-front base_ve_f.csv \
  --base-rear base_ve_r.csv
```

**2. VE Apply (CLI)**
```bash
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction.csv \
  --output updated_ve.csv \
  --dry-run  # Preview mode
```

**3. API (Headless HTTP)**
```bash
curl -X POST http://localhost:5000/api/analyze \
  -F "csv=@data.csv" \
  -F "run_id=headless_001"
```

**4. Self-Test (CI)**
```bash
python selftest_runner.py  # Exit code 0=pass, 1=fail
```

### Batch Processing Support

**Run ID Generation:**
- `make_run_id()` ensures unique IDs per run
- Output dirs isolated: `runs/{run_id}/`

**Scripting Example:**
```bash
#!/bin/bash
for csv in data_dir/*.csv; do
    run_id="batch_$(basename $csv .csv)"
    python ai_tuner_toolkit_dyno_v1_2.py \
      --csv "$csv" \
      --outdir "batch_results/$run_id"
done
```

**No User Interaction:**
- All args via CLI flags or API params
- No interactive prompts
- Progress to stdout (parseable: `PROGRESS:50:...`)

### Replay/Regression Reprocessing

**Manifest-Based Replay:**
1. Read `manifest.json` from previous run
2. Extract `input.path`, `args`
3. Re-run with identical args
4. Compare outputs via SHA-256

**Example:**
```bash
# Original run
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv data.csv --outdir run1 --clamp 12

# Replay from manifest
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv data.csv --outdir run2 --clamp 12

# Compare
diff run1/VE_Correction_Delta_DYNO.csv run2/VE_Correction_Delta_DYNO.csv
# Should be identical (deterministic)
```

**Time Machine Testing:**
- `experiments/` contains baseline runs for regression
- `TIME_MACHINE_TEST_CHECKLIST.md` documents validation procedure

### CI-Style Execution

**GitHub Actions Integration:**
- `.github/workflows/` contains CI configs
- `pytest` for unit/integration tests
- `selftest_runner.py` for full validation
- Exit codes propagate to CI

**Docker Support:**
```bash
docker build -t dynoai3 .
docker run -v $(pwd)/data:/data dynoai3 \
  python ai_tuner_toolkit_dyno_v1_2.py \
  --csv /data/run.csv \
  --outdir /data/output
```

### UI-Only Dependencies

**None.** All core functionality is CLI/API accessible.

**Web UI** (`frontend/`) is optional:
- Wraps API endpoints
- Provides visualization (heatmaps, charts)
- Not required for headless operation

**Verdict:** ✅ Fully headless-capable, CI-ready, batch-processable.

---

## G) LIMITS AND NON-GOALS

### What DynoAI3 Does NOT Do

**1. Dyno Control**
- **Not in scope:** DynoAI does not control dyno hardware
- **Delegated to:** WinPEP8, Dynojet control software
- **DynoAI role:** Post-processing of dyno logs

**2. Real-Time Tuning**
- **Not in scope:** Live AFR feedback during dyno run
- **Delegated to:** ECU tuner software (Power Vision, TuneLab)
- **DynoAI role:** Offline analysis, correction generation

**3. ECU Flashing**
- **Not in scope:** Writing tune files to ECU
- **Delegated to:** Power Vision tuner, Dynojet hardware
- **DynoAI role:** Generate PVV XML exports for manual import

**4. Human Operator Decisions**
- **Not in scope:** Automatic tune application without review
- **Delegated to:** Tuner judgment, safety validation
- **DynoAI role:** Advisory corrections, diagnostic reports

**5. Hardware Interfacing**
- **Not in scope:** Direct USB/serial to dyno or ECU
- **Delegated to:** WinPEP8, LiveLink, Power Core
- **DynoAI role:** Parse exported CSV/XML logs

**6. Arbitrary ECU Support**
- **Scope:** Harley-Davidson ECUs (Delphi/Magneti Marelli)
- **Not supported:** Automotive ECUs, other motorcycle brands
- **Reason:** VE table structure, AFR targeting specific to H-D

**7. Closed-Loop Tuning**
- **Not in scope:** Iterative tune → test → retune loops
- **Delegated to:** Human tuner with dyno
- **DynoAI role:** Single-pass correction from one log

**8. Fuel Pressure Correction**
- **Not in scope:** Compensating for fuel pressure variations
- **Delegated to:** Mechanical fuel system adjustments
- **DynoAI role:** Assumes stable fuel pressure during run

**9. Ignition Timing Auto-Apply**
- **Not in scope:** Automatic spark table updates
- **Delegated to:** Manual review, tuner applies spark suggestions
- **DynoAI role:** Suggestions only, based on knock data

**10. Multi-Bike Fleet Management**
- **Not in scope:** Database of bikes, tune tracking
- **Delegated to:** External shop management software
- **DynoAI role:** Per-run analysis, no persistent bike DB

### Intentional Design Boundaries

**Safety First:**
- All corrections clamped (±7% apply, ±12% preview)
- No auto-apply without user intervention
- Dry-run mode enforced for preview

**Single Responsibility:**
- DynoAI = AFR analysis + VE correction
- Does not replace ECU tuner, dyno operator, or shop software

**Modular Integration:**
- Accepts CSV from any dyno software
- Exports to standard formats (CSV, PVV XML)
- No vendor lock-in

**Operator Expertise Required:**
- Tuner must understand AFR targets, VE tables, spark timing
- DynoAI assists, does not replace knowledge

**Verdict:** ✅ Clear scope, well-defined delegation boundaries.

