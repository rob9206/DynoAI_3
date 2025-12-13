# DynoAI3 Data Contracts & I/O Specifications

**Purpose:** Formal specification of all input/output data formats, units, channel requirements, and safe_path rules.

---

## CSV Input Contracts

### WinPEP / WinPEP8 Format

**Format Specification:**
- **Delimiters:** Tab (`\t`) or comma (`,`) - auto-detected via `csv.Sniffer`
- **Encoding:** UTF-8 with BOM (`utf-8-sig`) or Windows CP1252 (fallback)
- **Header Row:** First row contains column names
- **Data Rows:** Numeric values or empty strings (for missing data)

**Required Columns** (matched case-insensitive, substring match):

| Logical Name | Acceptable Column Headers | Type | Unit | Range |
|--------------|---------------------------|------|------|-------|
| `rpm` | `"rpm"`, `"RPM"`, `"engine_rpm"`, `"motor_rpm"` | float | revolutions/minute | 400-8000 |
| `map` / `kpa` | `"map"`, `"kpa"`, `"MAP_kPa"`, `"manifold"`, `"pressure"` | float | kilopascals | 10-110 |
| `torque` | `"torque"`, `"Torque"`, `"tq"`, `"ft-lb"` | float | foot-pounds | >5 (load threshold) |

**Optional Columns:**

| Logical Name | Acceptable Column Headers | Type | Unit | Range |
|--------------|---------------------------|------|------|-------|
| `afr_cmd_f` | `"afr cmd f"`, `"afr_cmd_front"`, `"cmd afr f"`, `"afr target f"` | float | AFR ratio | 9.0-18.0 |
| `afr_cmd_r` | `"afr cmd r"`, `"afr_cmd_rear"`, `"cmd afr r"`, `"afr target r"` | float | AFR ratio | 9.0-18.0 |
| `afr_meas_f` | `"afr meas f"`, `"afr_meas_front"`, `"wb afr f"`, `"o2 f"` | float | AFR ratio | 9.0-18.0 |
| `afr_meas_r` | `"afr meas r"`, `"afr_meas_rear"`, `"wb afr r"`, `"o2 r"` | float | AFR ratio | 9.0-18.0 |
| `knock_f` | `"knock ret f"`, `"knock f"`, `"spark retard f"` | float | degrees | 0-10 |
| `knock_r` | `"knock ret r"`, `"knock r"`, `"spark retard r"` | float | degrees | 0-10 |
| `iat` | `"iat"`, `"intake air"`, `"intake_air_temp"` | float | °F | 30-300 |
| `tps` | `"tps"`, `"throttle"`, `"throttle_position"` | float | percent | 0-100 |
| `vbatt` | `"battery"`, `"vbatt"`, `"voltage"`, `"batt_voltage"` | float | volts | 10-16 |
| `hp` | `"hp"`, `"horsepower"`, `"power"` | float | horsepower | - |

**Column Matching Algorithm:**
1. Normalize: lowercase, replace `_` with space
2. **Exact match** (priority): `"afr cmd f"` matches `"AFR_Cmd_F"`
3. **Substring match** (fallback): `"afr"` in `"Measured_AFR_Front"`

**Example WinPEP CSV:**
```csv
Timestamp,RPM,MAP_kPa,Torque,AFR_Cmd_F,AFR_Meas_F,AFR_Cmd_R,AFR_Meas_R,Knock_Ret_F,Knock_Ret_R,IAT,TPS
0.010,3000.5,80.2,75.3,13.2,13.8,13.2,13.5,0.0,0.5,95.0,75.0
0.020,3020.1,82.5,76.1,13.2,13.9,13.2,13.6,0.0,0.0,95.5,76.0
...
```

**Data Validation (per row):**
- `rpm` ∈ [400, 8000] → skip if outside
- `kpa` ∈ [10, 110] → skip if outside
- `torque` > 5.0 → skip if below (low load)
- `afr_cmd`, `afr_meas` ∈ [9.0, 18.0] → skip if invalid
- `iat` ∈ [30, 300] → skip if outside
- `tps` ∈ [0, 100] → skip if outside

**AFR Error Calculation:**
```python
afr_err_pct = (afr_cmd - afr_meas) / afr_meas * 100.0
# Example: (13.2 - 13.8) / 13.8 * 100 = -4.35%
# Negative = running rich (too much fuel)
# Positive = running lean (not enough fuel)
```

---

### PowerVision CSV Format

**Format Specification:**
- **Delimiter:** Comma (`,`)
- **Encoding:** UTF-8 with BOM
- **Header Markers:**
  - `(PV) Engine Speed` → rpm
  - `(PV) Manifold Absolute Pressure` → kpa
  - `(DWR CPU) Torque` or `(DWRT CPU) Torque` → torque
  - `(PV) WBO2 AFR Front` → afr_meas_f
  - `(Harley - ECU Type 22 SW Level 621) ...` → ECU-specific channels

**Required Columns:**

| Logical Name | PowerVision Column Header | Type | Unit |
|--------------|---------------------------|------|------|
| `rpm` | `(PV) Engine Speed` or `(Harley - ECU...) Engine Speed` | float | RPM |
| `kpa` | `(PV) Manifold Absolute Pressure` | float | kPa |
| `torque` | `(DWR CPU) Torque` or `(DWRT CPU) Torque Drum 1` | float | ft-lb |

**Lambda→AFR Conversion:**
- PowerVision often logs lambda instead of AFR
- If AFR column exists but is invalid (e.g., constant 5.1):
  ```python
  for lambda_col in ["Lambda Measured", "Lambda Commanded", ...]:
      lambda_val = safe_float(row[lambda_col])
      if 0.6 <= lambda_val <= 1.3:
          afr_meas = lambda_val * 14.57  # STOICH_AFR_GASOLINE
          break
  ```

**Torque Derivation (if missing):**
```python
if torque is None and hp is not None and rpm > 0:
    torque = (hp * 5252.0) / rpm
# Formula: HP = (Torque × RPM) / 5252
# Inverse: Torque = (HP × 5252) / RPM
```

**Example PowerVision CSV:**
```csv
Time (s),(PV) Engine Speed,(PV) Manifold Absolute Pressure,(DWR CPU) Torque,(PV) WBO2 AFR Front,(PV) Lambda Measured
0.010,3000,80.5,75.2,13.8,0.947
0.020,3020,82.0,76.0,13.9,0.954
...
```

---

### Generic CSV Format

**Format Specification:**
- **Delimiter:** Comma (`,`)
- **Encoding:** UTF-8
- **Required Columns:** Flexible matching (similar to WinPEP)

**Accepted Column Names:**

| Logical Name | Generic Headers |
|--------------|-----------------|
| `rpm` | `"engine speed"`, `"engspeed (rpm)"`, `"rpm"` |
| `kpa` | `"map (kpa)"`, `"manifold pressure"`, `"map"` |
| `torque` | `"torque"`, `"engine torque"` |
| `afr_meas` | `"afr measured"`, `"wbo2 afr"`, `"measured afr"` |
| `afr_cmd` | `"desired air/fuel"`, `"afr commanded"`, `"afr target"` |
| `iat` | `"intake air temperature"`, `"iat (°f)"` |
| `tps` | `"throttle position"`, `"throttle (%)"` |

**Fallbacks:**
- Lambda→AFR (same as PowerVision)
- HP→Torque (same as PowerVision)

---

## CSV Output Contracts

### VE Correction Delta CSV

**File:** `VE_Correction_Delta_DYNO.csv`

**Format:**
```csv
RPM,35,50,65,80,95
1500,-2.45,-3.12,-4.56,-5.23,-6.01
2000,-1.89,-2.34,-3.78,-4.12,-5.45
2500,-0.56,-1.23,-2.45,-3.67,-4.89
3000,+0.12,+0.89,+1.23,+2.34,+3.45
...
6500,+5.67,+6.78,+7.89,+8.90,+9.12
```

**Specification:**
- **Header Row:** `RPM` followed by kPa bin values (35, 50, 65, 80, 95)
- **Data Rows:** RPM value followed by VE delta percentages
- **Value Format:** `{:+.2f}` (signed, 2 decimal places)
  - Example: `+3.45` = +3.45% VE increase
  - Example: `-2.34` = -2.34% VE decrease
- **Empty Cells:** Empty string (no quotes) for bins with no data
- **Dimensions:** 11 rows (RPM) × 5 cols (kPa) = 55 cells
- **Clamping:** All values ∈ [-12.0, +12.0] (configurable via `--clamp`)

**CSV Sanitization:**
- Numeric values prepended with `'` for Excel safety
- Example cell: `'3000` (RPM value)
- Prevents Excel from auto-formatting scientific notation

---

### VE Table CSV (Base / Updated)

**Files:** `VE_Front_Updated.csv`, `VE_Rear_Updated.csv`

**Format:**
```csv
RPM,35,50,65,80,95
1500,85.1234,87.5678,89.1234,91.2345,93.4567
2000,86.2345,88.6789,90.2345,92.3456,94.5678
...
6500,95.6789,97.8901,99.1234,100.2345,101.3456
```

**Specification:**
- **Header Row:** Same as VE delta CSV
- **Value Format:** `{:.4f}` (4 decimal precision for absolute VE values)
- **Dimensions:** 11 rows × 5 cols
- **Units:** Percentage (0-100+ range, typically 80-105)
- **Precision:** 4 decimals to preserve accuracy through multiple apply operations

**Updated VE Calculation:**
```python
updated_ve = base_ve * (1 + clamped_factor / 100.0)
# Example: 90.0 * (1 + 5.0/100) = 90.0 * 1.05 = 94.5000
```

---

### Coverage CSV

**File:** `Coverage_Front.csv`, `Coverage_Rear.csv`

**Format:**
```csv
RPM,35,50,65,80,95
1500,0,5,12,8,0
2000,3,15,45,32,10
2500,8,32,67,54,15
...
6500,0,2,8,5,0
```

**Specification:**
- **Header Row:** Same as VE delta CSV
- **Value Format:** Integer sample counts
- **Meaning:** Number of data points binned to each cell
- **Minimum Recommended:** ≥10 samples per cell for reliable correction

---

### Spark Suggestion CSV

**Files:** `Spark_Adjust_Suggestion_Front.csv`, `Spark_Adjust_Suggestion_Rear.csv`

**Format:**
```csv
RPM,35,50,65,80,95
1500,0.00,0.00,0.00,0.00,0.00
2000,0.00,-0.50,-1.00,-0.50,0.00
2500,0.00,-1.00,-2.00,-1.50,0.00
...
3000,0.00,-1.50,-2.50,-2.00,-1.00  (rear cylinder: -2.0° extra if 2800-3600 RPM, 75-95 kPa)
...
6500,0.00,0.00,0.00,0.00,0.00
```

**Specification:**
- **Value Format:** `{:+.2f}` (signed degrees)
- **Meaning:** Recommended spark timing adjustment
  - Negative values = retard timing (safer, less knock)
  - Positive values = advance timing (more aggressive, not recommended by default)
- **Range:** Typically -2.0° to 0.0° (retard only for safety)

**Rear Cylinder Rule:**
- **Zone:** RPM ∈ [2800, 3600], kPa ∈ [75, 95]
- **Base Retard:** -2.0° (configurable via `--rear-rule-deg`)
- **Hot IAT Extra:** -1.0° if IAT ≥ 120°F (configurable via `--hot-extra`)

---

### Paste-Ready TXT Format

**Files:** `VE_Delta_PasteReady.txt`, `Spark_Front_PasteReady.txt`, etc.

**Format:**
```
-2.45	-3.12	-4.56	-5.23	-6.01
-1.89	-2.34	-3.78	-4.12	-5.45
-0.56	-1.23	-2.45	-3.67	-4.89
+0.12	+0.89	+1.23	+2.34	+3.45
...
+5.67	+6.78	+7.89	+8.90	+9.12
```

**Specification:**
- **Delimiter:** Tab (`\t`)
- **No Headers:** Data only, 11 rows × 5 columns
- **Purpose:** Direct paste into tuner software grids
- **Format:** Same as corresponding CSV (e.g., `{:+.2f}` for VE delta)

---

### Manifest JSON

**File:** `manifest.json`

**Schema ID:** `dynoai.manifest@1`

**Structure:**
```json
{
  "schema_id": "dynoai.manifest@1",
  "run_id": "2025-11-19T21-47-29Z-6060bf",
  "created_at": "2025-11-19T21:47:29.123456Z",
  "input": {
    "path": "/absolute/path/to/data.csv",
    "sha256": "abc123...",
    "rows": 1234,
    "format": "winpep"
  },
  "args": {
    "clamp": 12.0,
    "smooth_passes": 2,
    "weighting": "torque",
    "rear_bias": 0.0,
    "rear_rule_deg": 2.0,
    "hot_extra": -1.0,
    "decel_management": false,
    "balance_cylinders": false
  },
  "timing": {
    "start": "2025-11-19T21:47:29.123456Z",
    "end": "2025-11-19T21:47:33.456789Z",
    "elapsed_s": 4.333333
  },
  "outputs": [
    {
      "file": "VE_Correction_Delta_DYNO.csv",
      "path": "VE_Correction_Delta_DYNO.csv",
      "type": "csv",
      "schema": "ve_delta_grid",
      "rows": 11,
      "cols": 5,
      "sha256": "def456..."
    }
  ],
  "ok": true,
  "last_stage": "export",
  "message": null,
  "stats": {
    "rows_read": 1234,
    "bins_total": 55,
    "bins_covered": 45,
    "front_accepted": 617,
    "rear_accepted": 617
  },
  "diagnostics": {
    "front": {
      "accepted_wb": 617,
      "temp_out_of_range": 5,
      "map_out_of_range": 2,
      "tps_out_of_range": 0,
      "bad_afr_or_request_afr": 10,
      "no_requested_afr": 0,
      "total_records_processed": 634,
      "per_bin_stats": {
        "mad": [[...], ...],
        "hits": [[...], ...]
      }
    },
    "rear": {...}
  }
}
```

**Required Fields:**
- `schema_id`: Must be `"dynoai.manifest@1"`
- `run_id`: Unique run identifier
- `created_at`: ISO 8601 timestamp with milliseconds (UTC, trailing 'Z')
- `input.path`: Absolute path to input CSV
- `input.sha256`: SHA-256 hash of input file
- `timing.start`, `timing.end`, `timing.elapsed_s`: Run timing
- `ok`: Boolean (true = success, false = error)
- `last_stage`: Last completed stage (`"parse"`, `"aggregate"`, `"export"`, etc.)

---

### VE Apply Metadata JSON

**File:** `VE_Front_Updated_meta.json`, `VE_Rear_Updated_meta.json`

**Structure:**
```json
{
  "operation": "apply",
  "base_sha": "abc123...",
  "factor_sha": "def456...",
  "applied_at_utc": "2025-11-20T14:30:00.123456Z",
  "max_adjust_pct": 7.0,
  "app_version": "1.0.0",
  "base_file": "/path/to/base_ve.csv",
  "factor_file": "/path/to/correction.csv",
  "output_file": "/path/to/updated_ve.csv",
  "comment": "Rollback = divide by last factor (or multiply by reciprocal of applied multipliers)"
}
```

**Required Fields:**
- `operation`: Must be `"apply"`
- `base_sha`: SHA-256 of base VE file (for integrity verification)
- `factor_sha`: SHA-256 of factor file (for rollback verification)
- `applied_at_utc`: ISO timestamp
- `max_adjust_pct`: Clamp limit used (default 7.0)

**Rollback Usage:**
1. Read metadata to get `factor_file`
2. Verify `factor_sha` matches current factor file hash
3. If match, apply inverse: `restored_ve = current_ve / (1 + factor/100)`

---

## Units & Scaling Reference

### Engine Parameters

| Parameter | Symbol | Unit | Typical Range | Notes |
|-----------|--------|------|---------------|-------|
| Engine Speed | RPM | revolutions/minute | 800-6500 | Idle: 800-1000, Redline: 5500-6500 |
| Manifold Pressure | MAP | kilopascals (kPa) | 35-95 | 35=vacuum (cruise), 95=WOT |
| Torque | Tq | foot-pounds (ft-lb) | 50-110 | V-twin: 70-100 typical |
| Horsepower | HP | horsepower | 30-100 | Calculated: (Tq × RPM) / 5252 |
| Throttle Position | TPS | percent (%) | 0-100 | 0=closed, 100=WOT |

### Air-Fuel Ratio (AFR)

| Parameter | Symbol | Unit | Typical Range | Notes |
|-----------|--------|------|---------------|-------|
| AFR (Gasoline) | AFR | ratio | 9.0-18.0 | Stoich=14.57:1 |
| Lambda | λ | ratio | 0.6-1.3 | λ=1.0=stoich, <1.0=rich, >1.0=lean |
| Commanded AFR | AFR_cmd | ratio | 12.2-14.7 | Target: WOT=12.2, Cruise=14.7 |
| Measured AFR | AFR_meas | ratio | - | Wideband O2 sensor reading |
| AFR Error | AFR_err | percent (%) | -20 to +20 | (cmd - meas) / meas × 100 |

**AFR Targets (MAP-based):**
| MAP Range (kPa) | Target AFR | Use Case |
|-----------------|------------|----------|
| < 50 | 14.7 | Cruise/light load (stoichiometric) |
| 50-70 | 13.8 | Part throttle |
| 70-85 | 13.2 | Acceleration |
| > 85 | 12.2 | WOT/power (rich for cooling) |

**Lambda Conversion:**
```python
AFR = λ × 14.57  # For gasoline
λ = AFR / 14.57
```

### Environmental Conditions

| Parameter | Symbol | Unit | Range | Notes |
|-----------|--------|------|-------|-------|
| Intake Air Temp | IAT | °F | 30-300 | Hot threshold: 120°F |
| Battery Voltage | Vbatt | volts | 10-16 | Typical: 12-14V |

### Ignition Timing

| Parameter | Symbol | Unit | Range | Notes |
|-----------|--------|------|-------|-------|
| Knock Retard | Knock | degrees | 0-10 | 0=no knock, >0=retard applied |
| Spark Adjustment | Spark_Δ | degrees | -2.0 to 0.0 | Negative=retard (safer) |

---

## Channel Requirements

### Minimal Required Channels (for basic VE correction)

1. **RPM** - Engine speed
2. **MAP/kPa** - Manifold pressure
3. **Torque** OR **Horsepower** - Load weighting

**Result:** VE correction grid (no AFR data → zero corrections, coverage map only)

### Standard Required Channels (for AFR-based VE correction)

1. **RPM**
2. **MAP/kPa**
3. **Torque** (or HP for derivation)
4. **AFR Commanded** (front or rear)
5. **AFR Measured** (front or rear)

**Result:** VE correction grid based on AFR error

### Full-Featured Channels (for advanced analysis)

All standard channels PLUS:
- **AFR Commanded Front/Rear** - Per-cylinder targets
- **AFR Measured Front/Rear** - Per-cylinder O2 readings
- **Knock Front/Rear** - Spark retard per cylinder
- **IAT** - Intake air temperature
- **TPS** - Throttle position (for load validation)
- **Battery Voltage** - Electrical system health

**Result:** VE corrections + spark suggestions + diagnostics + cylinder balancing

---

## Error Handling for Malformed CSVs

### Preflight Validation (`preflight_csv.py`)

**Checks Performed:**
1. File exists and is readable
2. Delimiter detection (tab vs comma)
3. Encoding detection (UTF-8, CP1252)
4. BOM presence
5. Required column existence
6. Minimum row count (>10 recommended)

**Example Error Message:**
```
[ERROR] Missing required columns in WinPEP CSV: RPM, Torque

Available columns: 'Timestamp', 'Engine_Speed', 'MAP', 'AFR_Front', ...

Hint: Column names are matched using substrings (case-insensitive).
For example, 'rpm', 'RPM', 'Engine_RPM' will all match.
Expected column patterns:
  - RPM: 'rpm', 'engine rpm', 'motor rpm'
  - MAP: 'map', 'kpa', 'manifold', 'pressure'
  - Torque: 'torque', 'tq', 'ft-lb'
```

### Runtime Row Validation

**Per-Row Checks:**
```python
# Skip row if any validation fails (silent skip, counted in diagnostics)

# 1. Required fields present
if rpm is None or kpa is None or torque is None:
    continue

# 2. Range validation
if not (400 <= rpm <= 8000):
    diagnostics["map_out_of_range"] += 1
    continue

if not (10 <= kpa <= 110):
    diagnostics["map_out_of_range"] += 1
    continue

# 3. Load threshold
if torque < 5.0:
    continue  # Skip low-load points

# 4. AFR validation
if afr_cmd is not None and not (9.0 <= afr_cmd <= 18.0):
    diagnostics["bad_afr_or_request_afr"] += 1
    continue

if afr_meas is not None and not (9.0 <= afr_meas <= 18.0):
    diagnostics["bad_afr_or_request_afr"] += 1
    continue

# 5. Temperature validation
if iat is not None and not (30 <= iat <= 300):
    diagnostics["temp_out_of_range"] += 1
    continue

# 6. TPS validation
if tps is not None and not (0 <= tps <= 100):
    diagnostics["tps_out_of_range"] += 1
    continue
```

**Diagnostic Counters (in manifest):**
- `accepted_wb`: Rows accepted for analysis
- `temp_out_of_range`: Rows skipped (invalid IAT)
- `map_out_of_range`: Rows skipped (invalid MAP)
- `tps_out_of_range`: Rows skipped (invalid TPS)
- `bad_afr_or_request_afr`: Rows skipped (invalid AFR)
- `no_requested_afr`: Rows skipped (missing AFR_cmd)
- `total_records_processed`: Total rows attempted

---

## io_contracts.safe_path Usage Rules

### Purpose
Prevent directory traversal attacks and ensure file I/O stays within allowed boundaries.

### Function Signature
```python
def safe_path(path: str, allow_parent_dir: bool = False) -> Path:
    """
    Args:
        path: Path to validate (relative or absolute)
        allow_parent_dir: If True, allows paths outside project root
                          (use with extreme caution, e.g., for user-provided CSVs)
    
    Returns:
        Resolved Path object (symlinks resolved, '..' normalized)
    
    Raises:
        ValueError: If path attempts to escape project root (when allow_parent_dir=False)
    """
```

### Usage Patterns

**1. Reading User-Provided CSVs (outside project):**
```python
# User provides CSV path via CLI
csv_path = args.csv  # e.g., "/home/user/dyno_logs/run_001.csv"
safe_csv = io_contracts.safe_path(str(csv_path), allow_parent_dir=True)
with open(safe_csv, newline="") as f:
    ...
```

**2. Writing Outputs (inside project):**
```python
# Write to runs/ directory
outdir = Path("runs") / run_id
target = io_contracts.safe_path(str(outdir / "VE_Correction_Delta_DYNO.csv"))
with open(target, "w", newline="") as f:
    ...
```

**3. Reading Base VE Tables (user-provided):**
```python
# Base VE tables often outside project
base_ve_path = args.base_front
safe_base = io_contracts.safe_path(str(base_ve_path), allow_parent_dir=True)
with open(safe_base, newline="") as f:
    ...
```

**4. Writing VE Apply Outputs (inside project):**
```python
# VE apply outputs in ve_runs/ directory
output_path = Path("ve_runs") / run_id / "VE_Front_Updated.csv"
safe_out = io_contracts.safe_path(str(output_path), allow_parent_dir=True)
with open(safe_out, "w", newline="") as f:
    ...
```

### Security Invariants

**✅ ALWAYS use `safe_path()` for:**
- All file reads
- All file writes
- All file existence checks

**✅ NEVER:**
- Construct file paths with user input via string concatenation
- Use `open()` directly without `safe_path()`
- Assume paths are safe

**Example Attack (prevented):**
```python
# UNSAFE (hypothetical malicious input):
csv_path = "../../../etc/passwd"
# safe_path() will detect '..' traversal and raise ValueError
# (if allow_parent_dir=False)

# SAFE:
safe_path = io_contracts.safe_path(csv_path, allow_parent_dir=True)
# Resolves to absolute path, verifies it exists, prevents symlink attacks
```

---

## SHA-256 Hash Usage

### Purpose
- **Integrity Verification:** Ensure files haven't been tampered with
- **Determinism Validation:** Confirm identical outputs from identical inputs
- **Rollback Safety:** Verify factor files match metadata before rollback

### Hash Computation
```python
def file_sha256(path: str, bufsize: int = 65536) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            hasher.update(chunk)
    return hasher.hexdigest()  # 64-character hex string
```

**Buffer Size:** 64KB (optimal for most filesystems)

### Hash Storage Locations

**1. Input CSV Hash (manifest.json):**
```json
{
  "input": {
    "path": "/path/to/data.csv",
    "sha256": "abc123...def456"  # 64 hex chars
  }
}
```

**2. Output File Hashes (manifest.json):**
```json
{
  "outputs": [
    {
      "file": "VE_Correction_Delta_DYNO.csv",
      "sha256": "789abc...012def"
    }
  ]
}
```

**3. VE Apply Hashes (metadata JSON):**
```json
{
  "base_sha": "base_ve_file_hash",
  "factor_sha": "correction_factor_hash",
  ...
}
```

### Hash Verification Workflow

**VE Rollback Example:**
```python
# 1. Read metadata
metadata = json.load(open("VE_Front_Updated_meta.json"))

# 2. Get expected factor hash
expected_sha = metadata["factor_sha"]

# 3. Compute current factor file hash
factor_path = Path(metadata["factor_file"])
actual_sha = compute_sha256(factor_path)

# 4. Verify match
if actual_sha != expected_sha:
    raise RuntimeError(
        f"Factor file hash mismatch!\n"
        f"  Expected: {expected_sha}\n"
        f"  Got: {actual_sha}\n"
        f"  Factor file may have been modified. Cannot safely rollback."
    )

# 5. Proceed with rollback (hash verified)
```

---

## CSV Sanitization Rules

### Excel Formula Injection Prevention

**Problem:** CSV cells starting with `=`, `+`, `-`, `@` can be interpreted as formulas by Excel.

**Solution:** Prepend `'` (single quote) to all numeric cells and cells starting with special chars.

**Function:** `sanitize_csv_cell(value)`

```python
def sanitize_csv_cell(value: Any) -> str:
    """
    Sanitize a CSV cell to prevent Excel formula injection.
    
    Rules:
    - Prepend ' to numeric strings
    - Prepend ' to strings starting with =, +, -, @
    - Convert None to empty string
    """
    if value is None:
        return ""
    
    s = str(value)
    
    # If starts with special chars, prepend '
    if s and s[0] in ('=', '+', '-', '@'):
        return f"'{s}"
    
    # If numeric, prepend '
    try:
        float(s)
        return f"'{s}"
    except ValueError:
        return s
```

**Example:**
```python
sanitize_csv_cell(3000)       # → '3000
sanitize_csv_cell(-2.45)      # → '-2.45
sanitize_csv_cell("RPM")      # → RPM
sanitize_csv_cell("=SUM(A1)") # → '=SUM(A1)
```

**Usage:**
```python
writer.writerow(["RPM"] + [sanitize_csv_cell(k) for k in KPA_BINS])
# Output: RPM,'35,'50,'65,'80,'95
```

**Note:** Excel will display `'3000` as `3000` (quote is hidden formatting).

---

## Summary of Contracts

| Contract Type | Specification | Enforced By |
|---------------|---------------|-------------|
| **CSV Input Format** | Required columns, delimiters, encoding | `detect_csv_format()`, `load_*_csv()` |
| **CSV Value Ranges** | AFR: 9-18, RPM: 400-8000, etc. | `dyno_bin_aggregate()` validation |
| **Grid Dimensions** | 11×5 (RPM×kPa) | `dynoai.constants.RPM_BINS`, `KPA_BINS` |
| **VE Delta Clamp** | ±12% (preview), ±7% (apply) | `clamp_grid()`, `clamp_factor_grid()` |
| **CSV Sanitization** | `'` prefix for numbers/special chars | `sanitize_csv_cell()` |
| **File I/O Security** | All paths via `safe_path()` | `io_contracts.safe_path()` |
| **Hash Integrity** | SHA-256 for inputs/outputs | `file_sha256()`, `compute_sha256()` |
| **Manifest Schema** | JSON with `schema_id: dynoai.manifest@1` | `create_manifest()`, `finish_manifest()` |
| **Timestamp Format** | ISO 8601 with milliseconds, UTC | `utc_now_iso()` |

**Verdict:** ✅ All I/O contracts are formally specified and enforced.

