# DynoAI3 System Invariants

**Purpose:** Non-negotiable invariants of tuning math and kernel behavior. What would constitute a breaking change.

---

## Core Mathematical Invariants

### Invariant 1: Grid Dimensions
**Rule:** All VE grids MUST be 11×5 (11 RPM bins × 5 kPa bins = 55 cells)

**RPM Bins (Fixed):**
```python
[1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
# Count: 11
# Range: 1500-6500 RPM
# Step: 500 RPM
```

**kPa Bins (Fixed):**
```python
[35, 50, 65, 80, 95]
# Count: 5
# Range: 35-95 kPa
# Non-uniform spacing: [35→50: +15], [50→65: +15], [65→80: +15], [80→95: +15]
```

**Breaking Change:**
- Changing bin count (e.g., 9×5 or 11×7)
- Changing bin values (e.g., different RPM steps)
- Adding/removing bins

**Rationale:** Grid dimensions tied to H-D ECU VE table structure. Changing breaks compatibility with Power Vision XML export.

---

### Invariant 2: Determinism
**Rule:** Identical inputs MUST produce identical outputs (bit-for-bit reproducible).

**Inputs:**
- CSV file content (SHA-256 hash)
- CLI arguments (`--clamp`, `--smooth-passes`, etc.)

**Outputs:**
- VE correction delta grid
- Spark suggestion grids
- Coverage grids

**Guarantee:**
```
hash(CSV_1) == hash(CSV_2) AND args_1 == args_2
  ⟹ hash(output_1) == hash(output_2)
```

**No Randomness:**
- No `random.random()`
- No `np.random.seed()`
- No time-based seeding
- No adaptive learning from previous runs

**Exception:** Run ID generation uses `os.urandom()` for uniqueness, but this does NOT affect tuning calculations.

**Breaking Change:**
- Introducing randomness in binning, aggregation, or smoothing
- Using non-deterministic algorithms
- Cross-run state dependencies

---

### Invariant 3: Clamping Limits
**Rule:** VE corrections MUST be safety-clamped to prevent dangerous adjustments.

**Preview Mode (CLI):**
- Default: ±12% (`--clamp 12`)
- Configurable: `--clamp` flag (range: 5-20%)
- Applied after smoothing

**Apply Mode (ve_operations.py):**
- Default: ±7% (`DEFAULT_MAX_ADJUST_PCT = 7.0`)
- Hardcoded in `VEApply` class
- Applied before multiplication

**Formula:**
```python
# Preview clamp (percentage deltas)
clamped_delta = max(-12.0, min(12.0, smoothed_delta))

# Apply clamp (correction factors)
clamped_factor = max(-7.0, min(7.0, factor))
updated_ve = base_ve × (1 + clamped_factor / 100)
```

**Multiplier Bounds:**
```python
# ±7% clamp → multiplier ∈ [0.93, 1.07]
min_multiplier = 1 + (-7 / 100) = 0.93
max_multiplier = 1 + (+7 / 100) = 1.07
```

**Breaking Change:**
- Removing clamp limits (unsafe)
- Increasing apply clamp above ±10% without user override
- Changing clamp logic to non-linear function

**Rationale:** Safety first. Large VE changes can cause engine damage. Conservative clamps prevent runaway corrections.

---

### Invariant 4: AFR Error Sign Convention
**Rule:** AFR error MUST follow the convention:

```python
afr_err_pct = (afr_cmd - afr_meas) / afr_meas × 100
```

**Interpretation:**
- **Negative error** (e.g., -5%) → Running RICH (measured AFR < commanded AFR)
  - Too much fuel, need to DECREASE VE
  - VE correction: Negative (e.g., -5%)
  
- **Positive error** (e.g., +5%) → Running LEAN (measured AFR > commanded AFR)
  - Not enough fuel, need to INCREASE VE
  - VE correction: Positive (e.g., +5%)

**VE Correction Relationship:**
```
VE_correction ≈ AFR_error
# If AFR error is -5%, VE correction should be ≈-5%
# (Simplified; actual correction may differ due to smoothing/clamping)
```

**Breaking Change:**
- Inverting sign convention
- Changing formula to `(meas - cmd) / cmd`
- Applying non-linear transformation to AFR error

**Rationale:** Industry-standard convention. Inverting breaks user intuition and existing calibrations.

---

### Invariant 5: Binning Algorithm (Nearest Neighbor)
**Rule:** Data points MUST be assigned to the nearest bin (minimum absolute difference).

**Algorithm:**
```python
def nearest_bin(val: float, bins: Sequence[int]) -> int:
    min_diff = abs(bins[0] - val)
    nearest = bins[0]
    for b in bins[1:]:
        diff = abs(b - val)
        if diff < min_diff:
            min_diff = diff
            nearest = b
    return nearest
```

**Example:**
```python
nearest_bin(2780, [1500, 2000, 2500, 3000, ...])
# → 3000 (distance: 220 < 280 to 2500)

nearest_bin(2720, [1500, 2000, 2500, 3000, ...])
# → 2500 (distance: 220 < 280 to 3000)

nearest_bin(2750, [1500, 2000, 2500, 3000, ...])
# → 3000 (distance: 250 = 250, tie goes to higher bin due to iteration order)
```

**Tie Behavior:** If two bins are equidistant, the first encountered bin in the list is selected (deterministic).

**Breaking Change:**
- Using different binning (e.g., floor, ceiling, interpolation)
- Introducing probabilistic binning
- Changing tie-breaking rule

**Rationale:** Nearest-neighbor is simple, fast, deterministic, and intuitive.

---

### Invariant 6: Weighted Aggregation
**Rule:** AFR error per bin MUST be computed as weighted average (torque or HP weights).

**Algorithm:**
```python
for each record:
    rpm_bin = nearest_bin(rpm, RPM_BINS)
    kpa_bin = nearest_bin(kpa, KPA_BINS)
    weight = torque  # or HP if --weighting=hp
    
    if weight < 5.0:
        continue  # Skip low-load points
    
    sums[rpm_bin][kpa_bin] += afr_err × weight
    weights[rpm_bin][kpa_bin] += weight

for each bin:
    if weights[r][k] > 0:
        grid[r][k] = sums[r][k] / weights[r][k]
    else:
        grid[r][k] = None  # No data
```

**Weight Threshold:** `weight >= 5.0` (ft-lb or HP)

**Breaking Change:**
- Using unweighted average (treats all points equally, ignores load)
- Changing weight threshold (e.g., < 5.0 allows idle points)
- Using different weighting function (e.g., `weight²`)

**Rationale:** High-load points (WOT) are more important for tuning than low-load (idle/cruise). Weighting emphasizes tuning zones.

---

### Invariant 7: K1 Kernel Smoothing (4-Stage Pipeline)
**Rule:** K1 kernel MUST execute all 4 stages in order: Gradient → Adaptive → Blend → Coverage.

**Stage Order (Immutable):**
1. **Gradient Calculation:** Compute max neighbor difference per cell
2. **Adaptive Smoothing:** Apply 0-N passes based on correction magnitude
3. **Gradient-Limited Blending:** Blend smoothed ← original for high gradients
4. **Coverage-Weighted Smoothing:** Final neighbor smoothing with center bias

**Adaptive Pass Schedule:**
```python
if abs(correction) >= 3.0:
    passes = 0  # Preserve large corrections
elif abs(correction) <= 1.0:
    passes = N  # Full smoothing (N = user arg, default 2)
else:
    # Linear taper between 1% and 3%
    taper = (3.0 - abs(correction)) / 2.0
    passes = int(round(N × taper))
```

**Thresholds (Fixed):**
- Large correction: ≥ 3.0%
- Small correction: ≤ 1.0%
- Gradient threshold: 1.0% (default, configurable)

**Coverage Smoothing Parameters:**
- `alpha = 0.20` (blend factor)
- `center_bias = 1.25` (center cell weight)
- `dist_pow = 1` (distance weighting exponent)
- `min_hits = 1` (minimum neighbors required)

**Breaking Change:**
- Reordering stages
- Skipping stages
- Changing adaptive thresholds (3%, 1%) without user override
- Changing coverage parameters (alpha, center_bias)

**Rationale:** 4-stage pipeline is validated through experiments/ directory. Changing order or parameters invalidates regression baselines.

---

### Invariant 8: Rollback Symmetry
**Rule:** VE apply followed by rollback MUST restore original values (within floating-point precision).

**Apply Operation:**
```python
updated_ve = base_ve × (1 + factor / 100)
```

**Rollback Operation:**
```python
restored_ve = current_ve / (1 + factor / 100)
```

**Symmetry Proof:**
```python
# Given:
base_ve = 90.0
factor = 5.0  # +5%

# Apply:
updated_ve = 90.0 × (1 + 5/100) = 90.0 × 1.05 = 94.5

# Rollback:
restored_ve = 94.5 / (1 + 5/100) = 94.5 / 1.05 = 90.0

# Verify:
assert abs(restored_ve - base_ve) < 1e-6  # Floating-point tolerance
```

**Hash Verification:**
- Factor file hash MUST match metadata before rollback
- Prevents rollback with different factor file

**Breaking Change:**
- Non-invertible apply operation
- Asymmetric rollback formula
- Skipping hash verification

**Rationale:** Rollback is a safety net. Must be mathematically precise to restore pre-apply state.

---

### Invariant 9: Spark Suggestions (Advisory Only)
**Rule:** Spark timing suggestions MUST remain advisory, never auto-applied.

**Output:** CSV files (`Spark_Adjust_Suggestion_*.csv`)

**Application:** Manual copy to tuner software by human operator

**Safety Rules:**
- Max retard: -2.0° (configurable via `--rear-rule-deg`)
- No advance: Never suggest positive timing (unsafe)
- Rear cylinder extra: -2.0° for 2800-3600 RPM, 75-95 kPa zone

**Breaking Change:**
- Auto-applying spark suggestions to ECU
- Suggesting spark advance (positive values)
- Removing rear cylinder safety zone

**Rationale:** Spark timing is safety-critical. Incorrect timing can cause detonation, engine damage. Human review required.

---

### Invariant 10: Rear Cylinder Safety Zone
**Rule:** Rear cylinder spark timing MUST have extra retard in specified zone.

**Zone Definition:**
- RPM: [2800, 3600] (inclusive)
- kPa: [75, 95] (inclusive)

**Safety Retard:**
- Base: -2.0° (configurable via `--rear-rule-deg`)
- Hot IAT extra: -1.0° if IAT ≥ 120°F (configurable via `--hot-extra`)

**Application:**
```python
for r in range(11):
    rpm = RPM_BINS[r]
    if 2800 <= rpm <= 3600:
        for k in range(5):
            kpa = KPA_BINS[k]
            if 75 <= kpa <= 95:
                spark_rear[r][k] += -abs(rear_rule_deg)  # -2.0°
                
                if iat_rear[r][k] >= 120.0:
                    spark_rear[r][k] += hot_extra  # -1.0°
```

**Breaking Change:**
- Removing rear cylinder rule
- Changing RPM/kPa zone boundaries
- Applying rule to front cylinder

**Rationale:** Harley V-twin rear cylinder runs hotter, more prone to detonation. Extra retard prevents knock.

---

## Data Integrity Invariants

### Invariant 11: Manifest Completeness
**Rule:** Every run MUST produce a complete manifest with:

**Required Fields:**
- `schema_id` = `"dynoai.manifest@1"`
- `run_id` (unique)
- `input.path`, `input.sha256`, `input.rows`
- `timing.start`, `timing.end`, `timing.elapsed_s`
- `ok` (boolean: true = success, false = error)
- `last_stage` (string: last completed stage)
- `outputs[]` (array of output files with SHA-256 hashes)

**Breaking Change:**
- Omitting required fields
- Changing `schema_id` without version bump
- Missing SHA-256 hashes for outputs

**Rationale:** Manifests enable determinism verification, debugging, and audit trails.

---

### Invariant 12: SHA-256 Integrity
**Rule:** All input/output files MUST have SHA-256 hashes recorded in manifest/metadata.

**Hash Computation:**
```python
def file_sha256(path: str, bufsize: int = 65536) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
```

**Usage:**
- Input CSV: Hash stored in `manifest.input.sha256`
- Output files: Hash stored in `manifest.outputs[].sha256`
- VE apply: Base/factor hashes in metadata JSON

**Breaking Change:**
- Omitting hashes
- Using weaker hash (MD5, CRC32)
- Skipping hash verification in rollback

**Rationale:** Hashes detect file tampering, corrupted downloads, and accidental edits.

---

### Invariant 13: safe_path() for All I/O
**Rule:** All file operations MUST go through `io_contracts.safe_path()`.

**Purpose:** Prevent directory traversal attacks (`../../../etc/passwd`)

**Implementation:**
```python
safe_path = io_contracts.safe_path(user_input, allow_parent_dir=True)
with open(safe_path, ...) as f:
    ...
```

**Breaking Change:**
- Direct `open(user_input)` without `safe_path()`
- Bypassing security checks

**Rationale:** Security. Prevents malicious CSV paths from reading sensitive files.

---

## Workflow Invariants

### Invariant 14: Preview Before Apply
**Rule:** VE corrections default to preview mode (CSV output only). Apply requires explicit action.

**Preview (Default):**
- `python ai_tuner_toolkit_dyno_v1_2.py --csv data.csv`
- Outputs: CSV files in `runs/{run_id}/`
- No VE table modification

**Apply (Explicit):**
- `python ve_operations.py apply --base base_ve.csv --factor correction.csv`
- Modifies VE tables
- Generates rollback metadata

**Breaking Change:**
- Auto-applying VE corrections without user confirmation
- Changing default to apply mode

**Rationale:** Safety. Forces user review before committing changes to ECU.

---

### Invariant 15: Run Isolation
**Rule:** Each run MUST be isolated by unique `run_id`. No cross-run state sharing.

**Run ID Format:** `YYYY-MM-DDTHH-MM-SSZ-{6-hex}` (timestamp + random suffix)

**Isolation:**
- Outputs: `runs/{run_id}/`
- Manifest: `runs/{run_id}/manifest.json`
- No shared files between runs

**Breaking Change:**
- Using fixed run IDs (causes overwrites)
- Sharing state between runs (cache, temp files)

**Rationale:** Reproducibility. Each run is an independent experiment.

---

## Performance Invariants

### Invariant 16: O(1) Bin Lookups
**Rule:** Bin index lookups MUST use O(1) dict access, not O(n) list.index().

**Implementation:**
```python
# Precomputed index dictionaries
RPM_INDEX = {rpm: i for i, rpm in enumerate(RPM_BINS)}
KPA_INDEX = {kpa: i for i, kpa in enumerate(KPA_BINS)}

# Usage in hot loop
rpm_index = RPM_INDEX[rpm_bin]  # O(1)
kpa_index = KPA_INDEX[kpa_bin]  # O(1)
```

**Breaking Change:**
- Reverting to `RPM_BINS.index(rpm_bin)` (O(n) lookup)

**Rationale:** Performance. Aggregation loop processes thousands of records. O(n) lookups add ~10% overhead.

---

### Invariant 17: Minimal Logging in Hot Loops
**Rule:** Debug logging in hot loops MUST be gated by `logger.isEnabledFor(logging.DEBUG)`.

**Implementation:**
```python
# CORRECT (guards expensive string formatting)
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(
        "AGG (%s): Accepted row #%d. RPM=%.0f, KPA=%.1f, ...",
        cyl, count, rpm, kpa, ...
    )

# INCORRECT (formats string even if debug disabled)
logger.debug(f"AGG: RPM={rpm}, KPA={kpa}")  # Avoid in hot loops
```

**Breaking Change:**
- Unconditional debug logging in aggregation loop

**Rationale:** Performance. String formatting is expensive. Gating reduces overhead when debug disabled.

---

## What Constitutes a Breaking Change

### Critical Breaking Changes (Require Major Version Bump)
1. Changing grid dimensions (11×5)
2. Inverting AFR error sign convention
3. Removing clamp limits
4. Introducing randomness in tuning math
5. Changing binning algorithm (nearest neighbor)
6. Reordering K1 kernel stages
7. Non-invertible apply/rollback

### Major Breaking Changes (Require Minor Version Bump)
1. Changing K1 kernel thresholds (3%, 1%)
2. Changing default clamp limits
3. Changing rear cylinder safety zone
4. Changing manifest schema (`schema_id`)
5. Removing SHA-256 hashes

### Non-Breaking Changes (Patch Version OK)
1. Adding optional CLI flags
2. Improving error messages
3. Optimizing performance (preserving behavior)
4. Adding new output files (preserving existing)
5. Bug fixes (correcting unintended behavior)

---

## Invariant Validation (Regression Tests)

**Location:** `experiments/` directory

**Baseline Runs:**
- `baseline_test_dense/` - Dense coverage (all bins)
- `baseline_test_sparse/` - Sparse coverage (partial bins)
- `k1_test_dense/` - K1 kernel validation (dense)
- `k1_test_sparse/` - K1 kernel validation (sparse)

**Validation Procedure:**
1. Run with same CSV + args as baseline
2. Compare outputs via SHA-256 hash
3. Verify manifests match (except timestamps, run_id)

**Example:**
```bash
# Regenerate baseline
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv experiments/baseline_dense.csv \
  --outdir /tmp/new_baseline \
  --clamp 12 --smooth-passes 2

# Compare hashes
sha256sum experiments/baseline_test_dense/VE_Correction_Delta_DYNO.csv
sha256sum /tmp/new_baseline/VE_Correction_Delta_DYNO.csv
# Must match (determinism invariant)
```

**Test Harness:** `TIME_MACHINE_TEST_CHECKLIST.md`

---

## Summary Table

| Invariant | Rule | Breaking Change |
|-----------|------|-----------------|
| Grid Dimensions | 11×5 (RPM×kPa) | Changing bin count/values |
| Determinism | Same input → same output | Introducing randomness |
| Clamping | ±12% preview, ±7% apply | Removing/increasing limits |
| AFR Error Sign | (cmd - meas) / meas | Inverting convention |
| Binning | Nearest neighbor | Different algorithm |
| Aggregation | Torque/HP weighted | Unweighted average |
| K1 Kernel | 4-stage pipeline | Reordering stages |
| Rollback Symmetry | Apply ↔ Rollback inverse | Non-invertible operations |
| Spark Advisory | Manual apply only | Auto-applying timing |
| Rear Safety Zone | 2800-3600 RPM, 75-95 kPa | Removing rule |
| Manifest | Complete metadata | Omitting fields |
| SHA-256 | All files hashed | Skipping hashes |
| safe_path() | All I/O validated | Bypassing security |
| Preview Default | No auto-apply | Changing default |
| Run Isolation | Unique run_id | Shared state |
| O(1) Lookups | Dict-based indexing | O(n) list.index() |
| Gated Logging | Debug checks enabled | Unconditional logging |

**Total Invariants:** 15 core + 2 performance = 17

**Verification:** All invariants tested in `experiments/` regression suite.

