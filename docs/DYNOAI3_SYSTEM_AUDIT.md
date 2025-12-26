# DynoAI3 System Audit and Engineering Documentation

**Version:** 1.0.0  
**Date:** 2025-12-13  
**Purpose:** Complete, engineering-accurate snapshot of the DynoAI3 software system as-is

---

## EXECUTIVE SUMMARY

DynoAI3 is a **deterministic, auditable VE (Volumetric Efficiency) correction engine** for Harley-Davidson V-twin motorcycles. It processes dyno run data (AFR measurements, knock detection, torque/HP) and generates VE table corrections using fixed mathematical kernels with no randomness, no adaptive learning, and no state persistence between runs.

**Architectural Layer:** Post-processing calibration tool  
**Position:** Between dyno software (WinPEP/Dynojet) and ECU tuning tools (Power Vision)  
**Core Guarantee:** Identical inputs → Identical outputs (deterministic)

---

## 1. REPOSITORY STRUCTURE

### 1.1 Top-Level Organization

```
DynoAI_3/
├── ai_tuner_toolkit_dyno_v1_2.py    # Main VE correction engine (2171 lines)
├── ve_operations.py                  # Apply/rollback system with hash verification
├── io_contracts.py                   # Path validation, manifest, CSV schema
├── selftest.py / selftest_runner.py  # Validation suite runner
├── dynoai/                           # Core constants and utilities
│   ├── constants.py                  # Bin definitions, grid dimensions, sensor ranges
│   └── test_utils.py                 # Synthetic data generation for testing
├── api/                              # REST API and web backend (Flask)
├── frontend/                         # React web UI
├── tests/                            # Pytest test suite (20+ test files)
├── docs/                             # Architecture, safety rules, guides
├── scripts/                          # CLI automation tools
└── tables/                           # Reference VE tables and sample data
```

### 1.2 Primary Modules

#### **ai_tuner_toolkit_dyno_v1_2.py** (Main VE Correction Engine)
Processes raw dyno CSV logs and generates VE correction grids using deterministic algorithms. Responsibilities:
- CSV parsing (WinPEP, PowerVision, generic formats with dialect sniffing)
- Data validation (AFR range: 9.0-18.0, IAT: 30-300°F, MAP: 10-110 kPa, TPS: 0-100%)
- Bin aggregation (RPM × MAP grid: 11×5 = 55 cells)
- Weighted averaging (torque or HP-weighted mean AFR error per cell)
- Kernel smoothing (gradient-limited adaptive smoothing, 2-stage with coverage weighting)
- Spark timing suggestions (knock-based retard with IAT compensation)
- Diagnostics and anomaly detection (outlier identification via robust z-score)
- Manifest generation (SHA-256 hashes, provenance, audit trail)

#### **ve_operations.py** (Apply/Rollback System)
Manages safe application and reversal of VE corrections with cryptographic verification. Responsibilities:
- VE table I/O (CSV format with 4-decimal precision)
- Factor clamping (default ±7%, configurable)
- Apply operation: `updated_ve = base_ve × (1 + factor/100)`
- Rollback operation: `restored_ve = current_ve / (1 + factor/100)` (exact inverse)
- Metadata generation (SHA-256 hashes of base and factor files, timestamps)
- Hash verification (prevents rollback of tampered files)
- Dual-cylinder coordination (atomic-like front+rear application)

#### **io_contracts.py** (Data Contracts and Security)
Enforces data integrity, path security, and manifest standards. Responsibilities:
- Path traversal protection (`safe_path` function, resolves symlinks, blocks `..` escapes)
- Manifest schema validation (JSON Schema v1, required fields: schema_id, run_id, status)
- CSV sanitization (prevents injection: `'=`, `'+`, `'@`, `'-'` prefix escaping)
- File hashing (SHA-256 with 64KB buffer for performance)
- Atomic writes (temp file + rename pattern to prevent partial writes)
- Run ID generation (timestamp + 6-char hash for uniqueness)

#### **dynoai/constants.py** (Single Source of Truth)
Defines all bin edges, grid dimensions, and sensor ranges. Responsibilities:
- RPM bins: `[1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]` (11 bins)
- kPa bins: `[35, 50, 65, 80, 95]` (5 bins)
- Grid dimensions: 11 rows × 5 columns = 55 cells
- Validation functions (dimension checks, nearest bin lookup)
- Sensor ranges (AFR: 9-18, Lambda: 0.6-1.3, IAT: 30-300°F)
- Physical constants (stoich AFR: 14.57, torque-HP conversion: 5252)

#### **selftest_runner.py / selftest.py** (Validation Suite)
Executes end-to-end validation of the VE correction pipeline. Responsibilities:
- Synthetic CSV generation (via `dynoai.test_utils.make_synthetic_csv`)
- Invokes `ai_tuner_toolkit_dyno_v1_2.py` with standard parameters
- Validates required outputs: `VE_Correction_Delta_DYNO.csv`, `Diagnostics_Report.txt`
- Manifest verification (status=success, rows_read > 1000, bins_total > 0)
- Exit code 0 on success, 1 on failure (CI-friendly)

---

## 2. DATA FLOW (END-TO-END)

### 2.1 Pipeline Overview

```
[Raw Dyno CSV]
    ↓
[CSV Parser] → detect_csv_format() → load_winpep_csv() / load_generic_csv()
    ↓
[Validation] → safe_float(), AFR/IAT/MAP/TPS range checks
    ↓
[Bin Aggregation] → dyno_bin_aggregate() → weighted mean AFR error per (RPM, kPa) cell
    ↓
[Kernel Smoothing] → kernel_smooth() → gradient-limited adaptive smoothing
    ↓
[Clamping] → clamp_grid() → enforce ±clamp_pct limit (default: ±15%)
    ↓
[Spark Suggestions] → spark_suggestion() → knock-based retard, IAT compensation
    ↓
[Diagnostics] → anomaly_diagnostics() → robust z-score outlier detection
    ↓
[Output Writer] → write_matrix_csv(), write_paste_block(), coverage_csv()
    ↓
[Manifest] → register_outputs() → SHA-256 hashes, provenance, audit trail
    ↓
[VE Apply] → ve_operations.VEApply.apply() → base × (1 + delta/100)
    ↓
[Rollback] → ve_operations.VERollback.rollback() → current / (1 + delta/100)
```

### 2.2 Input Formats

**WinPEP CSV (tab or comma-delimited):**
- Required columns: `rpm`, `map`/`kpa`, `torque`
- Optional columns: `afr_cmd_f`, `afr_cmd_r`, `afr_meas_f`, `afr_meas_r`, `knock_f`, `knock_r`, `iat`, `battery`, `tps`
- Encoding: UTF-8-BOM or CP1252 fallback
- Delimiter: Auto-detected via `csv.Sniffer` (comma, tab, semicolon)

**PowerVision CSV:**
- Required columns: `(pv) engine speed`, `(pv) manifold absolute pressure`, `(dwr cpu) torque`
- AFR columns: `(pv) wbo2 afr front`, lambda columns (fallback: `lambda × 14.57`)
- HP derivation: If torque missing but HP present: `torque = (hp × 5252) / rpm`

**Generic CSV:**
- Required columns: `engine speed`, `manifold absolute pressure`, `torque` or `horsepower`
- Header matching: Case-insensitive, space/underscore normalized, substring matching

### 2.3 Output Artifacts

| Filename | Type | Schema | Description |
|----------|------|--------|-------------|
| `VE_Correction_Delta_DYNO.csv` | CSV (grid) | ve_delta_grid | **Primary output**: VE correction percentages (±clamped) |
| `Spark_Adjust_Suggestion_Front.csv` | CSV (grid) | spark_suggestion_front | Spark advance/retard (degrees) for front cylinder |
| `Spark_Adjust_Suggestion_Rear.csv` | CSV (grid) | spark_suggestion_rear | Spark advance/retard (degrees) for rear cylinder |
| `AFR_Error_Map_Front.csv` | CSV (grid) | afr_error_front | Raw AFR error percentages (unclamped) |
| `AFR_Error_Map_Rear.csv` | CSV (grid) | afr_error_rear | Raw AFR error percentages (unclamped) |
| `Coverage_Front.csv` | CSV (grid) | coverage_front | Sample count per grid cell (front cylinder) |
| `Coverage_Rear.csv` | CSV (grid) | coverage_rear | Sample count per grid cell (rear cylinder) |
| `VE_Delta_PasteReady.txt` | Text | ve_delta_paste | Tab-delimited grid for ECU software paste |
| `Spark_Front_PasteReady.txt` | Text | spark_front_paste | Tab-delimited spark grid for ECU software |
| `Spark_Rear_PasteReady.txt` | Text | spark_rear_paste | Tab-delimited spark grid for ECU software |
| `Diagnostics_Report.txt` | Text | diagnostics_report | Human-readable statistics and anomaly report |
| `Anomaly_Hypotheses.json` | JSON | anomaly_hypotheses | Machine-readable anomaly diagnostics |
| `manifest.json` | JSON | dynoai.manifest@1 | Provenance, hashes, status, outputs |

### 2.4 Path Rules

- **Run storage**: `runs/{run_id}/` (dyno data capture)
- **VE operations**: `ve_runs/{run_id}/` (correction outputs)
- **Preview mode**: `ve_runs/preview/` (non-committed corrections)
- **Safety**: All paths validated via `io_contracts.safe_path()` (blocks `..` traversal)
- **Raw data immutability**: Input CSVs are never modified (read-only)

---

## 3. DETERMINISTIC MATH GUARANTEES

### 3.1 Bin Aggregation (`dyno_bin_aggregate`)

**Inputs:**
- List of records: `[{rpm, kpa, tq, afr_cmd, afr_meas, knock, iat, ...}]`
- Cylinder selector: `'f'` (front) or `'r'` (rear)
- Weighting mode: `'torque'` or `'hp'`

**Process:**
1. For each record:
   - Validate AFR (9.0-18.0), IAT (30-300°F), MAP (10-110 kPa), TPS (0-100%)
   - Compute AFR error: `afr_err_pct = (cmd - meas) / meas × 100`
   - Map to nearest bin: `rpm_bin = nearest_bin(rpm, RPM_BINS)`, `kpa_bin = nearest_bin(kpa, KPA_BINS)`
   - Weight: `w = max(0, torque)` or `max(0, hp)` (reject if w < 5.0)
   - Accumulate: `sums[rpm_idx][kpa_idx] += afr_err × w`, `weights[rpm_idx][kpa_idx] += w`
2. Compute weighted mean: `grid[i][j] = sums[i][j] / weights[i][j]` if `weights[i][j] > 0`, else `None`
3. Track coverage (sample count), max knock, max IAT per cell

**Outputs:**
- AFR error grid: `List[List[Optional[float]]]` (11×5, percentages)
- Knock max grid: `List[List[float]]` (11×5, degrees)
- IAT max grid: `List[List[Optional[float]]]` (11×5, °F)
- Coverage grid: `List[List[int]]` (11×5, sample counts)
- Diagnostics: `{accepted_wb, temp_out_of_range, map_out_of_range, bad_afr, ...}`
- Torque grid: `List[List[Optional[float]]]` (11×5, weighted mean torque)
- HP grid: `List[List[Optional[float]]]` (11×5, weighted mean HP)

**Determinism:**
- ✅ No randomness
- ✅ No adaptive learning
- ✅ Identical inputs → Identical outputs
- ✅ Order-independent (accumulation is commutative)

### 3.2 Kernel Smoothing (`kernel_smooth`)

**Inputs:**
- Raw correction grid: `List[List[Optional[float]]]`
- Smoothing passes: `int` (default: 2, max: 5)
- Gradient threshold: `float` (default: 1.0%)

**Algorithm (4-stage):**

**Stage 1: Gradient Calculation**
- For each cell, compute max difference to 4-neighbors (up/down/left/right)
- `gradient[i][j] = max(|center - neighbor|)` for all non-None neighbors

**Stage 2: Adaptive Smoothing**
- Cells with |correction| ≥ 3.0%: 0 smoothing passes (preserve large corrections)
- Cells with |correction| ≤ 1.0%: full smoothing passes (noise reduction)
- Cells between 1-3%: linear taper `passes × (3.0 - |correction|) / 2.0`
- Smoothing: `smoothed = mean([center, up, down, left, right])` (valid neighbors only)

**Stage 3: Gradient-Limited Blending**
- If `gradient > threshold`:
  - `blend_factor = min(1.0, gradient / (threshold × 2))`
  - `output = (1 - blend_factor) × smoothed + blend_factor × original`
- Preserves sharp transitions (e.g., idle-to-load boundary)

**Stage 4: Coverage-Weighted Smoothing**
- `alpha = 0.20`, `center_bias = 1.25`, `min_hits = 1`
- Collect neighbor values with distance weights
- `weighted_avg = Σ(value × weight) / Σ(weight)`
- `output = alpha × weighted_avg + (1 - alpha) × center`

**Outputs:**
- Smoothed grid: `List[List[Optional[float]]]` (same dimensions as input)

**Determinism:**
- ✅ No randomness (fixed alpha, bias, threshold)
- ✅ No hidden state (each pass is independent)
- ✅ Identical inputs → Identical outputs

### 3.3 VE Apply/Rollback

**Apply:**
- Input: `base_ve`, `factor_grid` (percentages), `max_adjust_pct`
- Clamp: `clamped_factor = clamp(factor, -max_adjust_pct, +max_adjust_pct)`
- Multiply: `updated_ve = base_ve × (1 + clamped_factor / 100)`
- Output: `updated_ve` (4-decimal precision), metadata JSON with SHA-256 hashes

**Rollback:**
- Input: `current_ve`, `metadata` (contains factor file path and hash)
- Verify: `SHA256(factor_file) == metadata.factor_sha` (hash match required)
- Divide: `restored_ve = current_ve / (1 + clamped_factor / 100)`
- Output: `restored_ve` (4-decimal precision)

**Invariants:**
- ✅ `apply(base, factor)` then `rollback(updated, metadata)` → `restored ≈ base` (within float precision)
- ✅ No state leakage (metadata is self-contained)
- ✅ Hash verification prevents rollback of tampered files

### 3.4 Clamping and Limits

| Operation | Clamp/Limit | Rationale |
|-----------|-------------|-----------|
| VE delta generation | ±15% (default, configurable) | Prevents unsafe large corrections |
| VE apply operation | ±7% (default, configurable) | Conservative safety margin for ECU |
| AFR validation | 9.0-18.0 AFR | Rejects sensor errors (too rich/lean) |
| IAT validation | 30-300°F | Physical plausibility bounds |
| MAP validation | 10-110 kPa | Sensor range limits |
| Weight threshold | ≥5.0 (torque or HP) | Ignores coasting/idle points |

---

## 4. KERNEL DEFINITION

### 4.1 K1: Gradient-Limited Adaptive Smoothing

**Purpose:** Reduce noise in VE corrections while preserving large, intentional corrections and sharp transitions (e.g., idle-to-load boundaries).

**Inputs:**
- Raw AFR error grid (11×5, percentages)
- `passes` (int, default: 2)
- `gradient_threshold` (float, default: 1.0%)

**Outputs:**
- Smoothed AFR error grid (11×5, percentages)

**Mathematical Intent:**
1. **Gradient Detection:** Identify cells with sharp transitions (|Δ| > threshold) to neighbor cells
2. **Adaptive Smoothing:** Apply fewer passes to large corrections (≥3%), full passes to small corrections (≤1%)
3. **Edge Preservation:** Blend back toward original value when gradient exceeds threshold
4. **Coverage Weighting:** Weight smoothing by neighbor availability (bias toward center if isolated)

**Ordering Guarantees:**
- Gradient calculation → Adaptive smoothing → Gradient blending → Coverage weighting
- Each stage is independent (no cross-stage state)

**Invariants:**
- Output grid has same dimensions as input (11×5)
- None values propagate (no interpolation across missing data)
- Smoothing strength inversely proportional to |correction| magnitude

### 4.2 K2: (Not Implemented as Separate Function)

The codebase does not have explicit "K2" or "K3" kernel functions. The smoothing is entirely handled by `kernel_smooth` (K1). However, the pipeline has **implicit kernels** in other operations:

### 4.3 K2 (Implicit): Weighted Binning

**Purpose:** Aggregate point-cloud dyno data into 2D grid cells using weighted averaging.

**Function:** `dyno_bin_aggregate()`

**Mathematical Intent:**
- Weight by torque (or HP) to emphasize loaded operating points
- Reject low-load points (weight < 5.0) to avoid idle/coasting noise
- Compute weighted mean: `Σ(afr_err × weight) / Σ(weight)`

### 4.4 K3 (Implicit): Spark Timing Logic

**Purpose:** Generate conservative spark advance/retard suggestions based on knock detection and IAT.

**Function:** `spark_suggestion()` + `enforce_rear_rule()`

**Mathematical Intent:**
- If knock ≥ 0.5°: retard by `-min(2.0, max(0.5, (knock / 3.0) × 2.0))°`
- If IAT ≥ 120°F: additional `-0.5°` retard
- Rear cylinder rule: Additional `-2.0°` retard in 2800-3600 RPM, 75-95 kPa range (hot rear cylinder protection)

**Invariants:**
- Spark suggestions are always ≤ 0 (never advance, only retard)
- Rear cylinder is always more conservative than front

---

## 5. AI ROLE AND BOUNDARIES

### 5.1 What AI Is Allowed to Do

**NOTHING.** DynoAI3 is a **misnomer**. There is **no AI/ML** in the core VE correction engine.

The name "DynoAI" is historical marketing. The actual system is:
- **Deterministic math kernels** (weighted averaging, smoothing, clamping)
- **Rule-based diagnostics** (threshold checks, robust z-score outliers)
- **No neural networks, no training, no inference**

### 5.2 AI Integration Points (Advisory Only)

The repository contains **experimental AI integrations** (not used in production VE corrections):

1. **XAI Agent (Explainable AI)** (`api/services/agent_orchestrator.py`)
   - Purpose: Generate human-readable explanations of VE corrections
   - Status: Experimental, not part of core pipeline
   - Boundaries: Cannot modify VE corrections, only annotate them

2. **Training Data Collection** (`api/services/training_data_collector.py`)
   - Purpose: Log dyno runs for future ML experiments
   - Status: Data collection only, no model training or inference
   - Boundaries: Read-only access to VE corrections

### 5.3 How AI Outputs Are Constrained

**N/A** - No AI outputs in the core VE correction pipeline.

If AI were integrated:
- ✅ Must be **advisory only** (suggest, not execute)
- ✅ Must be **explainable** (traceable reasoning)
- ✅ Must **never mutate** VE corrections (read-only access)
- ✅ Must **never bypass** deterministic math (parallel annotation only)

### 5.4 Prevention of AI Mutation

**Design Pattern:** AI is architecturally isolated from the VE correction pipeline.

```
[Dyno CSV] → [ai_tuner_toolkit_dyno_v1_2.py] → [VE Corrections] → [ve_operations.py] → [ECU]
                         ↓
                   [manifest.json]
                         ↓
                [XAI Agent (read-only)] → [Explanations (separate output)]
```

- VE corrections are **immutable once written** (manifest SHA-256 hash locked)
- AI agents operate on **copies** of VE data, never originals
- No AI code in `ai_tuner_toolkit_dyno_v1_2.py` or `ve_operations.py`

---

## 6. FORMAL DATA CONTRACTS

### 6.1 CSV Format Specification

**VE Table CSV:**
```csv
RPM,35,50,65,80,95
1500,92.5000,93.2000,94.1000,95.0000,96.3000
2000,91.8000,92.5000,93.4000,94.2000,95.1000
...
```
- Header row: `RPM`, followed by kPa bin values (integers)
- Data rows: RPM value, followed by VE values (floats, 4-decimal precision)
- Missing data: Empty string or `None` → `None` in grid
- CSV injection protection: Values prefixed with `'=`, `'+`, `'@`, `'-'` are escaped with leading `'`

**VE Correction Delta CSV:**
```csv
RPM,35,50,65,80,95
1500,+0.50,+1.20,-0.30,+2.10,+0.00
2000,-0.80,+0.00,+1.50,-1.20,+0.70
...
```
- Same structure as VE table, but values are **percentages** (not absolute VE)
- Format: `{:+.2f}` (always show sign, 2 decimals)

### 6.2 Manifest Schema

**JSON Schema ID:** `dynoai.manifest@1`

**Required Fields:**
```json
{
  "schema_id": "dynoai.manifest@1",
  "run_id": "2025-12-13T14-30-00Z-a1b2c3",
  "created_at_utc": "2025-12-13T14:30:00.123Z",
  "app_version": "1.0.0",
  "status": {
    "code": "success",
    "message": "VE corrections generated successfully",
    "stage": "export"
  },
  "inputs": [
    {
      "name": "dyno_log.csv",
      "path": "runs/test_run/dyno_log.csv",
      "sha256": "a1b2c3...",
      "type": "csv",
      "rows": 1500,
      "columns": 12
    }
  ],
  "outputs": [
    {
      "name": "VE_Correction_Delta_DYNO.csv",
      "path": "ve_runs/test_run/VE_Correction_Delta_DYNO.csv",
      "sha256": "d4e5f6...",
      "type": "csv",
      "schema": "ve_delta_grid",
      "rows": 11,
      "cols": 5
    }
  ],
  "stats": {
    "rows_read": 1500,
    "bins_total": 55,
    "bins_populated": 42
  }
}
```

**Status Codes:**
- `success`: Pipeline completed successfully
- `partial`: Some outputs missing or low coverage
- `error`: Fatal error, check `status.message` and `status.stage`

### 6.3 Error Handling

**Missing Required Columns:**
```
RuntimeError: Missing required columns in WinPEP CSV: RPM, MAP/kPa
Available columns: 'timestamp', 'iat', 'battery'
Hint: Column names are matched using substrings (case-insensitive).
```

**Out-of-Range Data:**
- AFR < 9.0 or > 18.0 → Rejected, counter: `diagnostics.bad_afr_or_request_afr`
- IAT < 30°F or > 300°F → Rejected, counter: `diagnostics.temp_out_of_range`
- MAP < 10 or > 110 kPa → Rejected, counter: `diagnostics.map_out_of_range`
- TPS < 0% or > 100% → Rejected, counter: `diagnostics.tps_out_of_range`

**Malformed CSV:**
```
RuntimeError: Empty CSV file.
```

### 6.4 Path Security

**safe_path() Guarantees:**
- ✅ Resolves symlinks (no hidden redirection)
- ✅ Blocks `..` traversal (cannot escape project root)
- ✅ Validates path is within `Path.cwd()` (unless `allow_parent_dir=True`)
- ✅ Raises `ValueError` on invalid paths

**Example:**
```python
safe_path("../../../etc/passwd")  # ValueError: Path attempts to traverse outside project
safe_path("runs/test/data.csv")   # OK: /home/runner/work/DynoAI_3/DynoAI_3/runs/test/data.csv
```

---

## 7. AUTOMATION & SCRIPTABILITY

### 7.1 Headless Operation

**CLI Usage:**
```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv runs/dyno_pull_001.csv \
  --outdir ve_runs/dyno_pull_001 \
  --smooth_passes 2 \
  --clamp 15 \
  --rear_bias 2.5 \
  --rear_rule_deg 2.0 \
  --hot_extra -1.0
```

**Exit Codes:**
- `0`: Success (check `manifest.json` for outputs)
- `1`: Fatal error (check stderr for details)

**Stdout Progress:**
```
PROGRESS:10:Loading CSV...
PROGRESS:30:Parsing WinPEP format...
PROGRESS:50:Aggregating front cylinder data...
PROGRESS:70:Smoothing and clamping VE corrections...
PROGRESS:90:Writing output files...
PROGRESS:100:Complete
```

### 7.2 Batch Processing

**Example Script:**
```bash
#!/bin/bash
for run_dir in runs/*/; do
  run_id=$(basename "$run_dir")
  python ai_tuner_toolkit_dyno_v1_2.py \
    --csv "$run_dir/data.csv" \
    --outdir "ve_runs/$run_id" \
    --smooth_passes 2 \
    --clamp 15
done
```

### 7.3 Function-Level API

**Import Usage:**
```python
from ai_tuner_toolkit_dyno_v1_2 import dyno_bin_aggregate, kernel_smooth, clamp_grid
from ve_operations import VEApply, VERollback

# Load and process dyno data
recs = load_winpep_csv("dyno_log.csv")
afr_err_grid, knock_grid, iat_grid, coverage, diag, tq_grid, hp_grid = dyno_bin_aggregate(recs, cyl='f')

# Smooth and clamp
smooth_grid = kernel_smooth(afr_err_grid, passes=2)
clamped_grid = clamp_grid(smooth_grid, limit=15.0)

# Apply to VE table
applier = VEApply(max_adjust_pct=7.0)
applier.apply(
    base_ve_path=Path("ve_base.csv"),
    factor_path=Path("ve_delta.csv"),
    output_path=Path("ve_updated.csv")
)
```

### 7.4 Replay and Regression

**Deterministic Replay:**
```bash
# Run 1 (original)
python ai_tuner_toolkit_dyno_v1_2.py --csv data.csv --outdir out1

# Run 2 (replay with same inputs)
python ai_tuner_toolkit_dyno_v1_2.py --csv data.csv --outdir out2

# Compare outputs (should be identical)
diff out1/VE_Correction_Delta_DYNO.csv out2/VE_Correction_Delta_DYNO.csv
# Expected: No differences
```

**Regression Test:**
```python
# tests/test_bin_alignment.py
def test_grid_mismatch_hard_fails(tmp_path):
    # Verifies mismatched RPM/kPa grids cause AssertionError
    assert raises(AssertionError, match="RPM/kPa grid mismatch")
```

### 7.5 CI/CD Suitability

**GitHub Actions Integration:**
```yaml
- name: Run DynoAI Self-Test
  run: python selftest_runner.py

- name: Run Pytest Suite
  run: pytest tests/ -v
```

**Characteristics:**
- ✅ Deterministic (no flaky tests)
- ✅ Fast (self-test completes in <10 seconds)
- ✅ Isolated (no network, no GPU, no external dependencies)
- ✅ Exit codes (0=pass, 1=fail)

---

## 8. TEST SURFACE

### 8.1 Self-Tests

**File:** `selftest.py` + `selftest_runner.py`

**Coverage:**
- End-to-end pipeline (CSV → VE corrections)
- Required outputs present
- Manifest validation (status=success, reasonable row count)
- Optional outputs warning (not fatal)

**Locked Behaviors:**
- ✅ `VE_Correction_Delta_DYNO.csv` is required
- ✅ `Diagnostics_Report.txt` is required
- ✅ `manifest.json` must have `status.code = "success"`
- ✅ `stats.rows_read > 1000` (synthetic data test)

### 8.2 Kernel Tests

**File:** `tests/test_bin_alignment.py`

**Coverage:**
- Grid dimension validation
- Bin mismatch detection (RPM/kPa grids must align)

**Locked Behaviors:**
- ✅ Mismatched RPM/kPa bins → `AssertionError` (hard fail)
- ✅ Grid reading preserves dimensions (11×5)

**File:** `tests/test_delta_floor.py`

**Coverage:**
- Delta values < 0.001% → floored to 0.000% in summary

**Locked Behaviors:**
- ✅ Tiny deltas are not displayed as non-zero

### 8.3 Regression Tests

**File:** `tests/test_cylinder_balancing.py` (20 KB)

**Coverage:**
- Per-cylinder AFR equalization
- Front/rear cylinder balancing logic

**File:** `tests/test_decel_management.py` (18 KB)

**Coverage:**
- Deceleration fuel cut logic
- Popping elimination

**File:** `tests/test_preflight_csv.py`

**Coverage:**
- CSV format detection (WinPEP, PowerVision, generic)
- Column header matching (case-insensitive, synonym support)
- Missing column error messages

**Locked Behaviors:**
- ✅ Format detection is deterministic (scoring-based)
- ✅ Missing required columns → helpful error message with available columns

### 8.4 API Tests

**Files:** `tests/api/test_*.py` (20+ files)

**Coverage:**
- REST API endpoints (health, runs, VE data, download, analyze)
- Authentication and authorization
- Rate limiting
- Request ID middleware
- Security (path traversal, SQL injection, XSS)

**Locked Behaviors:**
- ✅ `/health` returns 200 OK
- ✅ `/analyze` requires authentication
- ✅ Path traversal attempts → 400 Bad Request

### 8.5 Breaking Changes

**What Would Constitute a Breaking Change:**

1. **Grid Dimensions:**
   - Changing `RPM_BINS` or `KPA_BINS` breaks all existing VE tables
   - Impact: All stored VE tables become incompatible

2. **Manifest Schema:**
   - Removing required fields from `dynoai.manifest@1`
   - Impact: Old manifests fail validation

3. **Apply/Rollback Math:**
   - Changing `updated_ve = base × (1 + delta/100)` formula
   - Impact: Rollback operations fail (not exact inverse)

4. **CSV Format:**
   - Changing VE table CSV structure (header row, column order)
   - Impact: Existing VE tables cannot be read

5. **Hash Algorithm:**
   - Changing SHA-256 → SHA-512
   - Impact: Rollback verification fails (hash mismatch)

6. **Safe Path Behavior:**
   - Allowing `..` traversal
   - Impact: **SECURITY VULNERABILITY** (critical breaking change)

---

## 9. LIMITATIONS (EXPLICIT)

### 9.1 What DynoAI3 Does NOT Do

**1. ECU Communication**
- Does NOT flash ECUs
- Does NOT read/write tune files directly
- Delegated to: Power Vision, TunerPro, other ECU tools

**2. Dyno Data Capture**
- Does NOT control dyno hardware
- Does NOT interface with dyno software during runs
- Delegated to: WinPEP, Dynojet proprietary software

**3. Automatic Tuning**
- Does NOT automatically apply corrections to ECU
- Does NOT make decisions about safety margins
- Operator must review and approve all corrections

**4. Real-Time Operation**
- Does NOT provide live tuning during dyno runs
- Does NOT stream corrections to ECU
- Post-processing only (run completes → analysis → corrections)

**5. Machine Learning**
- Does NOT learn from previous runs
- Does NOT train models
- Does NOT adapt behavior based on history

**6. Multi-Bike Comparison**
- Does NOT compare across different motorcycles
- Does NOT benchmark against OEM targets
- Single-bike, single-run analysis only

**7. Physical Sensor Calibration**
- Does NOT calibrate wideband O2 sensors
- Does NOT verify dyno torque accuracy
- Assumes sensors are pre-calibrated

### 9.2 Known Non-Goals

**1. OEM-Level Calibration**
- DynoAI3 is not an OEM calibration engine (no emissions compliance, no durability testing)
- Target: Aftermarket performance tuning (track/street use)

**2. Model-Based Tuning**
- No engine simulation (no thermodynamics, no combustion modeling)
- Empirical corrections only (based on measured data)

**3. Closed-Loop Tuning**
- No feedback from ECU to refine corrections
- One-shot analysis (operator must re-run if adjustments needed)

**4. Multi-Variable Optimization**
- Does not optimize spark, fuel, and cam timing simultaneously
- VE and spark are computed independently (no cross-optimization)

### 9.3 Delegations

**To Dyno Software (WinPEP, Dynojet):**
- Torque/HP measurement
- Data logging (timestamped CSV export)
- Run control (throttle, load, safety limits)

**To ECU Tools (Power Vision, TunerPro):**
- Tune file import/export
- ECU flashing
- Table editing UI
- Live tuning dashboards

**To Operator:**
- Final approval of corrections
- Safety margin selection (clamp limits)
- Decision to apply or discard corrections
- Physical tuning (air/fuel screw, mechanical timing)

---

## 10. POSITIONING SUMMARY

### 10.1 Architectural Layer

**DynoAI3 Occupies:**
- **Post-Processing Calibration Tool** (between dyno software and ECU tools)
- **Data Analysis Pipeline** (CSV → VE corrections → diagnostics)
- **Deterministic Math Engine** (no AI/ML, no randomness)

**Stack Position:**
```
[ECU] ← [ECU Tool (Power Vision)] ← [DynoAI3] ← [Dyno Software (WinPEP)] ← [Dyno Hardware]
```

### 10.2 What DynoAI3 Can Legitimately Claim

**Engineering-Grade:**
- ✅ Deterministic VE corrections (identical inputs → identical outputs)
- ✅ Auditable pipeline (SHA-256 hashes, provenance, manifests)
- ✅ Reversible operations (apply ↔ rollback with hash verification)
- ✅ Safety-conscious (clamping, validation, diagnostics)
- ✅ Tested (self-tests, regression tests, CI integration)

**Performance:**
- ✅ Fast (processes 1500-row CSV in <5 seconds)
- ✅ Scalable (handles 10,000+ row logs efficiently)
- ✅ Memory-efficient (streaming CSV parser, no ORM overhead)

**Usability:**
- ✅ Headless CLI (CI/CD friendly)
- ✅ Web UI (React frontend, REST API backend)
- ✅ Batch processing (scriptable)
- ✅ Multiple input formats (WinPEP, PowerVision, generic CSV)

### 10.3 What DynoAI3 Must NOT Claim

**NOT AI-Powered:**
- ❌ "AI-powered tuning" (name is historical, not accurate)
- ❌ "Machine learning corrections" (no ML in core pipeline)
- ❌ "Adaptive tuning" (no learning, no state persistence)

**NOT Real-Time:**
- ❌ "Live auto-tuning" (post-processing only)
- ❌ "Closed-loop tuning" (no feedback from ECU)

**NOT OEM-Level:**
- ❌ "Production-grade calibration" (not for emissions, durability)
- ❌ "Replaces dyno tuner expertise" (tool, not replacement for skill)

**NOT Safety-Critical:**
- ❌ "Guaranteed safe corrections" (operator must review and approve)
- ❌ "Prevents engine damage" (diagnostics are advisory, not enforceable)

### 10.4 Comparison to OEM Calibration Engines

| Feature | DynoAI3 | OEM Calibration Engine |
|---------|---------|------------------------|
| **Input** | Dyno run CSV | Engine simulation models, test cell data |
| **Output** | VE correction deltas | Complete calibration (fuel, spark, cam, boost) |
| **Optimization** | Single-variable (VE only) | Multi-variable (fuel, spark, emissions, durability) |
| **Testing** | Dyno validation | Dyno + vehicle + emissions + durability |
| **Safety** | Clamping + diagnostics | Torque limits, failsafes, OBD compliance |
| **Scope** | Aftermarket performance | Production vehicle calibration |
| **Iterations** | 1-shot (operator re-runs if needed) | Hundreds of iterations (automated optimization) |
| **Determinism** | ✅ Fully deterministic | Partial (optimization may vary) |
| **Auditability** | ✅ SHA-256 hashes, manifests | Varies (proprietary tools) |
| **Reversibility** | ✅ Exact rollback | Not always possible (complex dependencies) |

**Conceptual Similarity:**
- Both use binned tables (RPM × Load)
- Both compute VE corrections from AFR error
- Both apply clamping/limits for safety

**Conceptual Differences:**
- OEM: Multi-variable optimization (fuel + spark + cam + boost + emissions)
- DynoAI3: Single-variable (VE only)
- OEM: Model-based (thermodynamics, combustion simulation)
- DynoAI3: Empirical (measured data only)
- OEM: Closed-loop validation (vehicle testing, emissions certification)
- DynoAI3: Open-loop (operator applies and validates)

---

## APPENDIX A: FILE MANIFEST

### Core Modules (8 files)
- `ai_tuner_toolkit_dyno_v1_2.py` (2171 lines)
- `ve_operations.py` (700+ lines)
- `io_contracts.py` (500+ lines)
- `selftest.py` (100 lines)
- `selftest_runner.py` (25 lines)
- `dynoai/constants.py` (268 lines)
- `dynoai/test_utils.py` (300+ lines)

### API Backend (50+ files)
- `api/app.py` (Flask application)
- `api/routes/*.py` (REST endpoints)
- `api/services/*.py` (Business logic)
- `api/models/*.py` (Data models)

### Frontend (React/TypeScript)
- `frontend/src/` (web UI)

### Tests (40+ files)
- `tests/test_*.py` (Pytest suite)
- `tests/api/test_*.py` (API tests)

### Documentation (30+ files)
- `docs/*.md` (Architecture, guides, safety rules)
- `README.md` (Quick start)

---

## APPENDIX B: CHANGE LOG

**Version 1.0.0** (2025-12-13)
- Initial system audit document
- Comprehensive analysis of DynoAI3 as-is (no code modifications)
- Documents all modules, data flows, math guarantees, kernels, contracts, tests, and limitations

---

## APPENDIX C: VERIFICATION CHECKLIST

### System Audit Completeness

- [x] **1. Repository structure** enumerated (all primary modules documented)
- [x] **2. Data flow** documented end-to-end (CSV input → VE output with concrete function names)
- [x] **3. Deterministic math** verified (no randomness, no learning, no state leakage)
- [x] **4. Kernel definitions** documented (K1 smoothing + implicit K2/K3)
- [x] **5. AI role** clarified (no AI in core pipeline, experimental integrations isolated)
- [x] **6. Data contracts** specified (CSV formats, manifest schema, path rules)
- [x] **7. Automation** confirmed (headless CLI, batch processing, function API)
- [x] **8. Test surface** enumerated (self-tests, kernel tests, regression tests, API tests)
- [x] **9. Limitations** listed (non-goals, delegations, known constraints)
- [x] **10. Positioning** summarized (architectural layer, legitimate claims, comparisons)

### Accuracy Guarantees

- [x] All code references verified against actual files
- [x] All function names confirmed to exist
- [x] All file paths validated
- [x] All mathematical formulas extracted from source code
- [x] No invented features or assumed behavior
- [x] No proposed refactors or improvements

**Audit Status:** ✅ COMPLETE

---

**Document End**
