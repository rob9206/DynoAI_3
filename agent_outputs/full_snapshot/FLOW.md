# DynoAI3 Data Flow & Pipeline Specification

**Purpose:** Detailed step-by-step data flow from raw CSV to final outputs, including all transformations, artifact naming, and storage layout.

---

## Pipeline Overview (Step-by-Step)

### Step 1: Input Validation & Format Detection

**Entry Point:** `ai_tuner_toolkit_dyno_v1_2.py::main()`

**Process:**
1. User provides CSV path via `--csv` flag
2. `detect_csv_format(csv_path)` reads first line, scores format:
   - WinPEP markers: `timestamp`, `rpm`, `map`, `afr cmd`, `knock`
   - PowerVision markers: `(pv) engine speed`, `(dwr cpu) torque`
   - Generic markers: `engspeed (rpm)`, `afr measured`
3. Returns format string: `"winpep"`, `"powervision"`, or `"generic"`

**Outputs:** Format identifier (string)

---

### Step 2: CSV Parsing & Record Extraction

**Function:** `load_winpep_csv()` or `load_generic_csv()`

**WinPEP Process:**
1. Detect delimiter via `csv.Sniffer` (tab or comma)
2. Open file with UTF-8-sig (BOM-safe) or CP1252 fallback
3. Parse as `DictReader`
4. Map columns via `find_column_by_candidates()`:
   - `rpm` ← `["rpm", "engine rpm"]`
   - `map` ← `["map", "kpa"]`
   - `torque` ← `["torque", "tq"]`
   - `afr_cmd_f` ← `["afr cmd f", "afr target f"]`
   - `afr_meas_f` ← `["afr meas f", "wb afr f"]`
   - (similar for rear cylinder, knock, IAT, TPS, battery)
5. For each row:
   - Convert to floats via `safe_float()`
   - Validate ranges (RPM: 400-8000, MAP: 10-110 kPa)
   - Compute AFR error: `afr_err_pct = (afr_cmd - afr_meas) / afr_meas × 100`
   - Append to records list

**Generic/PowerVision Process:**
1. Similar parsing but different column names
2. Lambda→AFR conversion if AFR is invalid:
   ```python
   if afr_invalid(afr_meas):
       afr_meas = lambda × 14.57  # STOICH_AFR_GASOLINE
   ```
3. Torque from HP if torque missing:
   ```python
   if torque is None and hp is not None:
       torque = (hp × 5252) / rpm
   ```

**Output:** List of records (dicts):
```python
[
    {
        "rpm": 3000.0,
        "kpa": 80.5,
        "tq": 75.2,
        "hp": 42.9,
        "afr_cmd_f": 13.2,
        "afr_meas_f": 13.8,
        "afr_err_f_pct": -4.35,  # (13.2-13.8)/13.8×100
        "afr_cmd_r": 13.2,
        "afr_meas_r": 13.5,
        "afr_err_r_pct": -2.22,
        "knock_f": 0.0,
        "knock_r": 0.5,
        "iat": 95.0,
        "tps": 75.0,
        "batt": 13.2,
    },
    ...
]
```

**Record Count:** Logged to manifest as `stats.rows_read`

---

### Step 3: Binning & Aggregation

**Function:** `dyno_bin_aggregate(recs, cyl="f", use_hp_weight=False)`

**Process:**
1. Initialize accumulators (11×5 grids):
   - `sums[r][k]` - Weighted AFR error sum
   - `weights[r][k]` - Total weight
   - `coverage[r][k]` - Hit count
   - `tq_sums[r][k]`, `hp_sums[r][k]` - Torque/HP for diagnostics
   - `knock_max[r][k]`, `iat_max[r][k]` - Max values per cell
   - `bin_values[r][k]` - List of all AFR errors (for MAD)

2. For each record:
   - Skip if missing AFR command or measurement
   - Validate AFR in range (9.0-18.0)
   - Validate IAT (30-300°F), MAP (10-110 kPa), TPS (0-100%)
   - Find nearest bin:
     ```python
     rpm_bin = nearest_bin(rpm, RPM_BINS)  # [1500, 2000, ..., 6500]
     kpa_bin = nearest_bin(kpa, KPA_BINS)  # [35, 50, 65, 80, 95]
     rpm_index = RPM_INDEX[rpm_bin]  # O(1) dict lookup
     kpa_index = KPA_INDEX[kpa_bin]
     ```
   - Compute weight:
     ```python
     if use_hp_weight:
         weight = max(0.0, hp)
     else:
         weight = max(0.0, torque)
     if weight < 5.0:
         continue  # Skip low-load points
     ```
   - Accumulate:
     ```python
     sums[r][k] += afr_err × weight
     weights[r][k] += weight
     coverage[r][k] += 1
     bin_values[r][k].append(afr_err)
     knock_max[r][k] = max(knock_max[r][k], knock)
     iat_max[r][k] = max(iat_max[r][k] or 0, iat)
     ```

3. Compute weighted averages:
   ```python
   for r in range(11):
       for k in range(5):
           if weights[r][k] > 0:
               grid[r][k] = sums[r][k] / weights[r][k]
               tq_grid[r][k] = tq_sums[r][k] / weights[r][k]
               hp_grid[r][k] = hp_sums[r][k] / weights[r][k]
               mad_grid[r][k] = mad(bin_values[r][k])  # Median absolute deviation
           else:
               grid[r][k] = None  # No data
   ```

**Outputs:**
- `afr_err_grid` (11×5) - Average AFR error % per bin
- `knock_max` (11×5) - Max knock retard per bin
- `iat_max` (11×5) - Max IAT per bin
- `coverage` (11×5) - Sample count per bin
- `diagnostics` (dict) - Accepted/rejected counts
- `tq_grid` (11×5) - Average torque per bin
- `hp_grid` (11×5) - Average HP per bin

**Diagnostics Counters:**
```python
{
    "accepted_wb": 1234,
    "temp_out_of_range": 5,
    "map_out_of_range": 2,
    "tps_out_of_range": 0,
    "bad_afr_or_request_afr": 10,
    "no_requested_afr": 3,
    "total_records_processed": 1254,
    "per_bin_stats": {"mad": mad_grid, "hits": coverage}
}
```

---

### Step 4: Cylinder Combination

**Function:** `combine_front_rear(f_grid, r_grid)`

**Process:**
```python
for r in range(11):
    for k in range(5):
        f_val = f_grid[r][k]
        r_val = r_grid[r][k]
        if f_val is None and r_val is None:
            combined[r][k] = None
        elif f_val is None:
            combined[r][k] = r_val  # Rear only
        elif r_val is None:
            combined[r][k] = f_val  # Front only
        else:
            combined[r][k] = (f_val + r_val) / 2.0  # Average both
```

**Output:** Combined VE delta grid (11×5)

---

### Step 5: K1 Kernel Smoothing

**Function:** `kernel_smooth(grid, passes=2, gradient_threshold=1.0)`

**Stage 1: Gradient Calculation**
```python
for r in range(11):
    for k in range(5):
        if grid[r][k] is None:
            continue
        max_diff = 0.0
        # Check 4 neighbors (up, down, left, right)
        neighbors = []
        if r > 0 and grid[r-1][k] is not None:
            neighbors.append(grid[r-1][k])
        # ... (similar for other 3 neighbors)
        for n in neighbors:
            max_diff = max(max_diff, abs(grid[r][k] - n))
        gradients[r][k] = max_diff
```

**Stage 2: Adaptive Smoothing**
```python
for r in range(11):
    for k in range(5):
        val = grid[r][k]
        if val is None:
            continue
        
        # Determine adaptive passes based on magnitude
        abs_val = abs(val)
        if abs_val >= 3.0:
            adaptive_passes = 0  # Preserve large corrections
        elif abs_val <= 1.0:
            adaptive_passes = passes  # Full smoothing
        else:
            # Linear taper: 1% → full passes, 3% → 0 passes
            taper = (3.0 - abs_val) / 2.0
            adaptive_passes = int(round(passes × taper))
        
        # Apply smoothing passes
        smoothed = val
        for _ in range(adaptive_passes):
            neighbors = [smoothed]  # Include center
            # Add valid neighbors
            if r > 0 and grid[r-1][k] is not None:
                neighbors.append(grid[r-1][k])
            # ... (similar for other neighbors)
            smoothed = sum(neighbors) / len(neighbors)
        
        adaptive_grid[r][k] = smoothed
```

**Stage 3: Gradient-Limited Blending**
```python
for r in range(11):
    for k in range(5):
        original = grid[r][k]
        smoothed = adaptive_grid[r][k]
        gradient_mag = gradients[r][k]
        
        if gradient_mag > gradient_threshold:
            # Blend back toward original for high gradients
            blend_factor = min(1.0, gradient_mag / (gradient_threshold × 2))
            result = (1 - blend_factor) × smoothed + blend_factor × original
        else:
            result = smoothed
        
        gradient_limited_grid[r][k] = result
```

**Stage 4: Coverage-Weighted Smoothing**
```python
alpha = 0.20  # Blend factor
center_bias = 1.25  # Extra weight for center cell
min_hits = 1

for r in range(11):
    for k in range(5):
        center = gradient_limited_grid[r][k]
        if center is None:
            continue
        
        # Weighted neighbor average
        values = [center]
        weights = [center_bias]
        
        # Add neighbors with distance weighting
        neighbors = [(r-1, k), (r+1, k), (r, k-1), (r, k+1)]
        for nr, nk in neighbors:
            if 0 <= nr < 11 and 0 <= nk < 5:
                n_val = gradient_limited_grid[nr][nk]
                if n_val is not None:
                    values.append(n_val)
                    weights.append(1.0)  # Distance weight
        
        if len(values) >= min_hits:
            weighted_avg = sum(v × w for v, w in zip(values, weights)) / sum(weights)
            final_grid[r][k] = alpha × weighted_avg + (1 - alpha) × center
        else:
            final_grid[r][k] = center  # Insufficient neighbors
```

**Output:** Smoothed VE delta grid (11×5)

---

### Step 6: Clamping

**Function:** `clamp_grid(grid, limit=12.0)`

```python
for r in range(11):
    for k in range(5):
        if grid[r][k] is not None:
            clamped[r][k] = max(-limit, min(limit, grid[r][k]))
        else:
            clamped[r][k] = None
```

**Output:** VE correction delta grid (11×5), clamped to ±12%

---

### Step 7: Spark Suggestions

**Function:** `spark_suggestion(knock_grid, iat_grid)`

```python
for r in range(11):
    for k in range(5):
        knock = knock_grid[r][k] or 0.0
        iat = iat_grid[r][k]
        
        pull = 0.0
        if knock >= 0.5:
            # Retard spark based on knock
            pull = -min(2.0, max(0.5, (knock / 3.0) × 2.0))
        
        if iat is not None and iat >= 120.0 and pull < 0.0:
            # Extra retard for hot IAT
            pull -= 0.5
        
        spark_grid[r][k] = pull
```

**Rear Cylinder Rule:** `enforce_rear_rule(spark_grid, rear_rule_deg=2.0, hot_extra=-1.0)`

```python
for r in range(11):
    rpm = RPM_BINS[r]
    if 2800 <= rpm <= 3600:
        for k in range(5):
            kpa = KPA_BINS[k]
            if 75 <= kpa <= 95:
                # Apply rear safety rule
                spark_grid[r][k] += -abs(rear_rule_deg)  # -2.0°
                
                iat = iat_grid[r][k]
                if iat is not None and iat >= 120.0:
                    spark_grid[r][k] += hot_extra  # Additional -1.0°
```

**Outputs:**
- `spark_front` (11×5) - Spark adjustment suggestions (degrees)
- `spark_rear` (11×5) - Spark adjustment with rear rule applied

---

### Step 8: Output File Generation

**Directory Structure:**
```
runs/{run_id}/
├── VE_Correction_Delta_DYNO.csv      # Primary VE delta grid (±12% clamped)
├── VE_Delta_PasteReady.txt           # Tab-delimited for tuner software
├── AFR_Error_Map_Front.csv           # Front cylinder AFR error % (pre-smoothing)
├── AFR_Error_Map_Rear.csv            # Rear cylinder AFR error %
├── Spark_Adjust_Suggestion_Front.csv # Front spark timing adjustments (degrees)
├── Spark_Adjust_Suggestion_Rear.csv  # Rear spark timing (with rear rule)
├── Spark_Front_PasteReady.txt        # Tab-delimited spark front
├── Spark_Rear_PasteReady.txt         # Tab-delimited spark rear
├── Coverage_Front.csv                # Sample count per bin (front)
├── Coverage_Rear.csv                 # Sample count per bin (rear)
├── Coverage_Front_Enhanced.csv       # Coverage with MAD statistics
├── Coverage_Front_Heatmap.png        # Visual coverage map
├── Coverage_Front_Table.html         # HTML coverage report
├── Torque_Map_Front.csv              # Average torque per bin (front)
├── Torque_Map_Rear.csv               # Average torque per bin (rear)
├── Torque_Map_Combined.csv           # Combined front+rear torque
├── HP_Map_Front.csv                  # Average HP per bin (front)
├── HP_Map_Rear.csv                   # Average HP per bin (rear)
├── HP_Map_Combined.csv               # Combined front+rear HP
├── Diagnostics_Report.txt            # Text summary of run diagnostics
├── Anomaly_Hypotheses.json           # Outlier detection results
├── manifest.json                     # Full run metadata
└── README.txt                        # Human-readable summary
```

**Optional Outputs (if --base-front/--base-rear provided):**
```
runs/{run_id}/
├── VE_Front_Updated.csv              # Absolute VE table (base × (1+delta/100))
├── VE_Rear_Updated.csv               # Absolute VE table (rear)
├── VE_Front_Absolute_PasteReady.txt  # Tab-delimited absolute VE
└── VE_Rear_Absolute_PasteReady.txt   # Tab-delimited absolute VE
```

**Optional Outputs (if --decel-management):**
```
runs/{run_id}/
├── Decel_Fuel_Overlay.csv            # Decel fuel cut recommendations
└── Decel_Analysis_Report.json        # Decel event diagnostics
```

**Optional Outputs (if --balance-cylinders):**
```
runs/{run_id}/
├── Front_Balance_Factor.csv          # Per-cylinder balance corrections
├── Rear_Balance_Factor.csv           # Per-cylinder balance corrections
└── Cylinder_Balance_Report.json      # Balance analysis results
```

---

### Step 9: Manifest Finalization

**Function:** `io_contracts.write_manifest_pair(manifest, outdir, run_id)`

**Manifest Content:**
```json
{
  "schema_id": "dynoai.manifest@1",
  "run_id": "2025-11-19T21-47-29Z-6060bf",
  "created_at": "2025-11-19T21:47:29.123Z",
  "input": {
    "path": "/path/to/data.csv",
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
    "start": "2025-11-19T21:47:29.123Z",
    "end": "2025-11-19T21:47:33.456Z",
    "elapsed_s": 4.333
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
    },
    ...
  ],
  "ok": true,
  "last_stage": "export",
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
      "bad_afr_or_request_afr": 10,
      "no_requested_afr": 0,
      "total_records_processed": 634
    },
    "rear": { ... }
  }
}
```

**README.txt Content:**
```
DynoAI v1.2 Run Summary
=======================

Run ID: 2025-11-19T21-47-29Z-6060bf
Created: 2025-11-19T21:47:29.123Z
Status: OK

Input:
- File: /path/to/data.csv
- Format: winpep
- Rows: 1234

Analysis:
- Bins covered: 45 / 55 (81.8%)
- Front cylinder: 617 accepted samples
- Rear cylinder: 617 accepted samples
- Clamp: ±12.0%
- Smoothing: 2 passes

Primary Outputs:
- VE_Correction_Delta_DYNO.csv  (VE correction %, ready for apply)
- Spark_Adjust_Suggestion_*.csv (Timing suggestions)
- Coverage_*.csv                (Sample distribution)
- Diagnostics_Report.txt        (Detailed diagnostics)

See manifest.json for full run metadata.
```

---

## Artifact Naming Conventions

### Run ID Format
- **Pattern:** `YYYY-MM-DDTHH-MM-SSZ-{6-char-hex}`
- **Example:** `2025-11-19T21-47-29Z-6060bf`
- **Components:**
  - Timestamp: UTC ISO 8601 (colons → hyphens for filename safety)
  - Random suffix: First 6 chars of SHA-256(os.urandom(16))

### Output File Naming
- **Primary VE Delta:** `VE_Correction_Delta_DYNO.csv` (fixed name)
- **Paste-Ready:** `{DescriptiveName}_PasteReady.txt` (tab-delimited)
- **Cylinder-Specific:** `{Metric}_Map_{Front|Rear|Combined}.csv`
- **Diagnostics:** `{Feature}_Report.{txt|json}`

### Storage Layout

**Runs Directory:**
```
runs/
├── 2025-11-19T21-47-29Z-6060bf/   # Run ID as directory name
│   ├── manifest.json
│   ├── README.txt
│   └── *.csv, *.txt, *.json
├── 2025-11-20T10-15-00Z-abc123/
└── ...
```

**VE Apply Directory (separate from runs):**
```
ve_runs/
├── 2025-11-20T14-30-00Z-def456/   # Apply operation run ID
│   ├── VE_Front_Updated.csv
│   ├── VE_Rear_Updated.csv
│   ├── VE_Front_Updated_meta.json
│   └── VE_Rear_Updated_meta.json
├── preview/                        # Dry-run outputs
│   └── (temporary preview files)
└── ...
```

**Experiments Directory (regression baselines):**
```
experiments/
├── baseline_test_dense/            # Dense coverage baseline
│   ├── manifest.json
│   └── *.csv
├── k1_test_dense/                  # K1 kernel validation (dense)
├── k1_test_sparse/                 # K1 kernel validation (sparse)
└── experiment_summary.json         # Metrics comparison
```

---

## Data Transformation Summary

| Stage | Input | Transformation | Output |
|-------|-------|----------------|--------|
| 1. Parse | CSV file | `load_winpep_csv()` | List of records (dicts) |
| 2. Bin | Records | `nearest_bin()` + accumulate | AFR error grids (F/R) |
| 3. Combine | F+R grids | Average or fallback | Single VE delta grid |
| 4. Smooth | VE delta | K1 kernel (4 stages) | Smoothed VE delta |
| 5. Clamp | Smoothed VE | `max(-12, min(12, x))` | Clamped VE delta (±12%) |
| 6. Spark | Knock + IAT | Retard formula | Spark suggestions (F/R) |
| 7. Apply | Base VE + delta | `VE × (1 + Δ/100)` | Updated VE (±7% clamp) |
| 8. Export | All grids | `write_matrix_csv()` | CSV files |

---

## Progress Reporting

**Console Output (parseable):**
```
PROGRESS:0:Starting DynoAI Tuner v1.2...
PROGRESS:10:Loading CSV: data.csv (format: winpep)
PROGRESS:30:Parsing 1234 rows...
PROGRESS:50:Aggregating front cylinder data...
PROGRESS:60:Aggregating rear cylinder data...
PROGRESS:70:Smoothing and clamping VE corrections...
PROGRESS:80:Generating spark advance suggestions...
PROGRESS:90:Writing output files...
PROGRESS:95:Running anomaly diagnostics...
PROGRESS:100:Done.

Dyno AI Tuner v1.2 outputs written to: runs/2025-11-19T21-47-29Z-6060bf
```

**Parsing Pattern:** `PROGRESS:(\d+):(.+)` for external monitoring

---

## Determinism Verification

**Replay Test:**
1. Run with same CSV + args → `run1/`
2. Run again with identical params → `run2/`
3. Compare outputs:
   ```bash
   diff -r run1/ run2/
   # Should be identical except:
   # - manifest.json (timestamps, run_id differ)
   # - README.txt (timestamps differ)
   ```
4. SHA-256 verification:
   ```bash
   sha256sum run1/VE_Correction_Delta_DYNO.csv
   sha256sum run2/VE_Correction_Delta_DYNO.csv
   # Hashes MUST match (deterministic)
   ```

**Verdict:** ✅ Same input → same VE delta (bit-for-bit reproducible, modulo floating-point variance on different CPUs).

