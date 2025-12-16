# DynoAI3 Deterministic Math Specification

**Version:** 1.0.0  
**Last Updated:** 2025-12-13  
**Status:** Production

---

## Executive Summary

DynoAI3 is a **deterministic, automation-first, post-processing calibration engine for dyno data**, with provable math, explicit boundaries, and OEM-inspired discipline.

Despite the "AI" in its name, DynoAI3's core VE calibration pipeline contains **no machine learning**. All tuning operations are deterministic, reproducible, and auditable—designed to match the rigor of world-class OEM and motorsport calibration systems.

---

## 1. What "World-Class" Means

World-class calibration software is not defined by UI polish or algorithmic novelty, but by:

### Core Principles

1. **Deterministic Math** - Same inputs always produce same outputs, provably
2. **Automation & Scripting** - Headless operation, batch processing, CI-style execution
3. **Formal Data Contracts** - Explicit schemas, units, invariants
4. **Auditability & Reproducibility** - Full traceability and verification
5. **Explicit Boundaries** - Clear statement of what the system does and does NOT do

OEM and top-tier motorsport tools (ETAS INCA, Vector CANape, MoTeC, Cosworth) prioritize **trust and repeatability** over constant algorithmic change.

---

## 2. Deterministic Math — Core Principle

### Definition

Deterministic math means:

- **No randomness** - No random number generators, no probabilistic algorithms
- **No adaptive learning** - No state carried between runs
- **No hidden normalization** - All transformations are explicit and documented
- **No cross-run state** - Each analysis is independent
- **Apply/rollback symmetry** - Operations are exact mathematical inverses
- **Bit-reproducible results** - Identical inputs produce identical outputs down to floating-point precision

### Benefits

This enables:
- **Regression testing** - Detect unintended changes immediately
- **Historical comparability** - Compare results across months or years
- **Automation at scale** - Run thousands of analyses with confidence
- **Engineering trust** - Tuners can rely on consistent behavior

### Contractual Obligation

Once a system claims determinism, **math stability becomes a contractual obligation**. Any change to the core algorithms is an engineering event that requires:

1. Version incrementing
2. Algorithm tagging in outputs
3. Test suite updates
4. Documentation updates
5. Communication to users

---

## 3. DynoAI3 Math Components

DynoAI3's calibration engine consists of three deterministic kernels applied in a fixed, documented order:

### K1: Gradient-Limited Smoothing

**Purpose:** Preserve large corrections while smoothing noise

**Algorithm:**
1. Calculate gradient magnitude for each cell (max neighbor difference)
2. Apply adaptive smoothing based on correction magnitude:
   - Corrections ≥3.0%: 0 smoothing passes (preserve large corrections)
   - Corrections ≤1.0%: 2 smoothing passes (smooth noise)
   - Linear taper between thresholds
3. For high-gradient cells, blend back toward original value
4. Gradient threshold: 1.0%

**Parameters:**
- `passes`: Number of smoothing iterations (default: 2)
- `gradient_threshold`: Gradient magnitude threshold (default: 1.0%)

**Location:** `ai_tuner_toolkit_dyno_v1_2.py::kernel_smooth()`

### K2: Coverage-Weighted Smoothing

**Purpose:** Apply neighbor-weighted averaging with configurable bias

**Algorithm:**
1. For each cell, collect neighbor values
2. Apply distance-based weighting
3. Blend with center cell using bias factor
4. Alpha-blend result with original value

**Parameters:**
- `alpha`: 0.20 (smoothing strength)
- `center_bias`: 1.25 (preserve center cell influence)
- `min_hits`: 1 (minimum neighbors required)
- `dist_pow`: 1 (linear distance weighting)

**Location:** `ai_tuner_toolkit_dyno_v1_2.py::kernel_smooth()` (Stage 4)

### K3: Tiered Spark Logic

**Purpose:** Generate spark advance/retard based on knock detection

**Algorithm:**
1. For knock values ≥0.5, calculate retard: `-min(2.0, max(0.5, (knock/3.0) * 2.0))`
2. If IAT ≥ HOT_IAT_THRESHOLD_F and retard active, subtract additional 0.5°
3. For rear cylinder in power band (2800-3600 RPM, 75-95 kPa):
   - Apply base retard of -2.0°
   - If hot IAT, apply additional -1.0°

**Parameters:**
- `HOT_IAT_THRESHOLD_F`: Temperature threshold for hot compensation
- `extra_rule_deg`: Base retard for rear cylinder power band (default: 2.0°)
- `hot_extra`: Additional retard when hot (default: -1.0°)

**Location:** 
- `ai_tuner_toolkit_dyno_v1_2.py::spark_suggestion()`
- `ai_tuner_toolkit_dyno_v1_2.py::enforce_rear_rule()`

### VE Correction Calculation (NEW in v2.0.0)

**Purpose:** Calculate VE correction factors from AFR measurements

**Math Versions:**

| Version | Formula | Description |
|---------|---------|-------------|
| v1.0.0 | `VE = 1 + (AFR_error × 0.07)` | Linear 7% per AFR point (legacy) |
| v2.0.0 | `VE = AFR_measured / AFR_target` | Ratio model (default, physically accurate) |

**v2.0.0 Ratio Model (Default):**

The ratio model is derived from first principles of fuel mass balance:

```python
VE_correction = AFR_measured / AFR_target
```

**Physical Derivation:**
- AFR = mass_of_air / mass_of_fuel
- If measured AFR is higher than target (lean), we need MORE fuel
- Required fuel multiplier = measured/target directly

**Examples:**

| Scenario | Measured | Target | v1.0.0 | v2.0.0 | Accurate |
|----------|----------|--------|--------|--------|----------|
| Lean | 14.0 | 13.0 | 1.07 | 1.077 | 1.077 |
| Very Lean | 15.0 | 12.5 | 1.175 | 1.200 | 1.200 |
| Rich | 12.0 | 13.0 | 0.93 | 0.923 | 0.923 |
| On Target | 13.0 | 13.0 | 1.00 | 1.000 | 1.000 |

**Why v2.0.0 is Better:**
1. Mathematically exact (not an approximation)
2. Works correctly at all AFR ranges
3. More accurate at large deviations (v1.0.0 underestimates by ~10% at 3 AFR points)
4. Used by OEM calibration systems (Bosch, Delphi, MoTeC)

**Location:** `dynoai/core/ve_math.py::calculate_ve_correction()`

**Parameters:**
- `afr_measured`: Measured AFR from wideband sensor
- `afr_target`: Target/commanded AFR
- `version`: MathVersion.V1_0_0 or MathVersion.V2_0_0 (default)
- `clamp`: Whether to apply safety clamping (default: True)

**Safety Clamping:**
- Default: ±15% maximum correction
- Prevents dangerous lean/rich conditions
- Configurable via MathConfig

---

## 4. Apply/Rollback Guarantees

DynoAI3 provides mathematically exact apply and rollback operations:

### VEApply

**Operation:** `VE_new = VE_base × (1 + factor/100)`

**Guarantees:**
- Clamping enforced before apply (default ±7%)
- Output precision: 4 decimal places
- Metadata generation with SHA-256 hashes
- No factor can exceed configured bounds

**Location:** `ve_operations.py::VEApply`

### VERollback

**Operation:** `VE_restored = VE_current / (1 + factor/100)`

**Guarantees:**
- Hash verification prevents rollback of tampered files
- Exact mathematical inverse of apply
- Bit-identical restoration (within 4-decimal precision)
- Metadata validation before rollback

**Location:** `ve_operations.py::VERollback`

### Symmetry Proof

The acceptance test suite (`acceptance_test.py`) validates:

```python
VE_base → Apply(factor) → VE_new → Rollback(factor) → VE_restored
assert VE_base == VE_restored (within 4-decimal tolerance)
```

---

## 5. Data Contracts

### Input Contract: WinPEP CSV

**Required Columns:**
- `rpm`: Engine speed (integer, 1500-6500)
- `map_kpa`: Manifold pressure (integer, 50-100)
- `afr_cmd_f`, `afr_cmd_r`: Target AFR (float, 11.0-15.0)
- `afr_meas_f`, `afr_meas_r`: Measured AFR (float, 11.0-15.0)
- `iat`: Intake air temperature (float, Fahrenheit)
- `knock`: Knock intensity (float, 0.0-100.0)

**Validation:**
- AFR values outside [11.0, 15.0] are rejected
- IAT outside reasonable range triggers warnings
- Missing required columns cause immediate failure

**Location:** `ai_tuner_toolkit_dyno_v1_2.py::parse_winpep_log()`

### Output Contract: Manifest

**Schema Version:** 1.1.0

**Required Fields:**
- `run_id`: Unique run identifier
- `timestamp_utc`: ISO 8601 UTC timestamp
- `input_csv`: Source data filename
- `max_clamp_pct`: Clamping limit used
- `smooth_passes`: Smoothing passes applied
- `app_version`: DynoAI version
- `total_rows`: Row count from input
- `valid_afr_samples`: Samples passing validation

**Optional Fields:**
- `kernel_alpha`: K2 alpha parameter (0.20)
- `kernel_center_bias`: K2 center bias (1.25)
- `kernel_min_hits`: K2 minimum neighbors (1)
- `kernel_dist_pow`: K2 distance power (1)

**Location:** `io_contracts.py::validate_manifest_schema()`

### Output Contract: VE Correction Delta

**Format:** CSV with RPM rows and MAP columns

**Header Row:** `RPM,50,65,80,95,100`

**Data Rows:** 
```
RPM_value,correction_50kpa,correction_65kpa,...
```

**Guarantees:**
- All corrections clamped to ±max_clamp_pct
- Empty cells for bins with no data
- 2 decimal precision for percentages

### Output Contract: Apply Metadata

**Filename:** `{output_name}_meta.json`

**Required Fields:**
- `base_sha256`: Hash of base VE table
- `factor_sha256`: Hash of correction factors
- `applied_at_utc`: ISO 8601 UTC timestamp
- `max_adjust_pct`: Clamping limit used
- `app_version`: DynoAI version

**Purpose:** Enable verified rollback

**Location:** `ve_operations.py::VEApply.apply()`

---

## 6. Artifact Layout

All outputs follow a deterministic directory structure:

```
runs/{run_id}/
├── manifest.json                          # Run metadata
├── data.csv                               # Source WinPEP log
├── VE_Correction_Delta_DYNO.csv          # Main output
├── Diagnostics_Report.txt                 # Analysis summary
├── Spark_Adjust_Suggestion_Front.csv     # Spark timing
├── Spark_Adjust_Suggestion_Rear.csv
├── Coverage_Front.csv                     # Data coverage
└── Coverage_Rear.csv

ve_runs/{run_id}/
├── ve_updated.csv                         # Applied VE table
├── ve_updated_meta.json                   # Rollback metadata
└── apply_log.txt                          # Operation log

ve_runs/preview/
├── preview_{timestamp}.csv                # Dry-run preview
└── preview_{timestamp}_meta.json          # Preview metadata
```

**Guarantees:**
- SHA-256 hashing for provenance
- Path traversal protection via `safe_path()`
- Immutable raw data (source CSV never modified)
- Deterministic artifact naming

**Location:** `io_contracts.py::safe_path()`

---

## 7. Automation & Scripting

DynoAI3 is designed for automation:

### Headless CLI

```bash
# Full analysis pipeline
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv dyno_log.csv \
  --outdir ./runs/run_001 \
  --base_front base_ve_front.csv \
  --base_rear base_ve_rear.csv \
  --clamp 7.0 \
  --smooth-passes 2
```

### Batch Processing

```bash
# Process multiple runs
for log in logs/*.csv; do
  run_id=$(basename "$log" .csv)
  python ai_tuner_toolkit_dyno_v1_2.py \
    --csv "$log" \
    --outdir "./runs/$run_id" \
    --clamp 7.0
done
```

### Apply/Rollback CLI

```bash
# Apply corrections (dry-run)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv \
  --dry-run

# Apply corrections (commit)
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction_factors.csv \
  --output ve_updated.csv

# Rollback if needed
python ve_operations.py rollback \
  --current ve_updated.csv \
  --metadata ve_updated_meta.json \
  --output ve_restored.csv
```

### CI/CD Integration

DynoAI3's deterministic nature enables:
- Regression test suites that detect math changes
- Automated validation of tuning runs
- Historical result comparison
- Golden file testing

**Example CI Workflow:**
1. Run analysis on known-good CSV
2. Compare output against golden manifest
3. Verify SHA-256 hashes match
4. Fail build if math has changed

---

## 8. Explicit Boundaries

### What DynoAI3 IS

- **Deterministic post-processing VE calibration engine**
- Analyzes dyno data (CSV input)
- Generates VE correction factors
- Provides spark timing suggestions
- Offers apply/rollback with hash verification
- Supports headless automation

### What DynoAI3 is NOT

- **NOT a dyno controller** - Does not control dynamometers
- **NOT an ECU communication tool** - Does not flash or read ECUs directly
- **NOT real-time** - Post-processing only, not closed-loop
- **NOT adaptive** - No learning across runs
- **NOT ML-based** - Despite the name, core math is deterministic

These boundaries are intentional and allow DynoAI3 to excel in its domain.

---

## 9. Math Versioning Policy

### Current Versions

**Kernel Math Version:** 1.0.0 (FROZEN)  
**VE Correction Math Version:** 2.0.0 (DEFAULT as of 2025-12-15)

**Kernel Configuration (v1.0.0):**
- K1: Gradient-limited smoothing (passes=2, gradient_threshold=1.0)
- K2: Coverage-weighted smoothing (alpha=0.20, center_bias=1.25, min_hits=1, dist_pow=1)
- K3: Tiered spark logic (extra_rule_deg=2.0, hot_extra=-1.0)

**VE Correction Configuration:**

| Version | Status | Formula | Use Case |
|---------|--------|---------|----------|
| v1.0.0 | Available | `1 + (AFR_error × 0.07)` | Legacy compatibility |
| v2.0.0 | **Default** | `AFR_measured / AFR_target` | Production (physically accurate) |

**How to Select VE Math Version:**

```python
from dynoai.core.ve_math import calculate_ve_correction, MathVersion

# v2.0.0 (default)
correction = calculate_ve_correction(14.0, 13.0)

# v1.0.0 (legacy)
correction = calculate_ve_correction(14.0, 13.0, version=MathVersion.V1_0_0)
```

**CLI:**
```bash
python scripts/jetdrive_autotune.py --math-version 2.0.0  # default
python scripts/jetdrive_autotune.py --math-version 1.0.0  # legacy
```

### Version Stability Guarantee

> **The math described in this document will not change without a major version increment.**

Any change to kernel algorithms, parameters, or calculation methods constitutes a **new math generation** and requires:

1. New major version number (1.0.0 → 2.0.0)
2. Algorithm version tag in all outputs
3. Ability to run old math versions alongside new
4. Full regression test suite for new version
5. Documentation update and user notification
6. Migration guide if automatic conversion is possible

### What Can Change Without Version Increment

- Bug fixes that restore documented behavior
- Output format improvements (CSV → JSON, etc.)
- Performance optimizations that don't affect results
- UI/UX enhancements
- Documentation clarifications
- Additional validation checks
- New optional features that don't affect core math

### What CANNOT Change Without Version Increment

- Kernel algorithms (K1, K2, K3)
- Default parameters (alpha, center_bias, etc.)
- Clamping logic
- Apply/rollback formulas
- Binning strategy (RPM/MAP grid)
- AFR error calculation
- Coverage weighting formulas

---

## 10. Comparison with OEM Systems

| System | Deterministic Math | Automation | Formal Contracts | Domain |
|--------|-------------------|------------|------------------|---------|
| **ETAS INCA** | High | High (COM + MATLAB) | ASAM A2L/MDF | ECU calibration |
| **Vector CANape** | High | High (API/COM/MATLAB) | ASAM A2L/MDF | ECU calibration |
| **MoTeC M1** | High (strategy-dependent) | In-ECU scripting | Package-defined | Motorsport ECU |
| **Cosworth Pi Toolbox** | Medium–High | Varies | Telemetry-centric | Motorsport analysis |
| **HP Tuners** | Medium–High (config-dependent) | Low–Medium | Tool-specific | Aftermarket tuning |
| **DynoAI3** | **High (test-proven)** | **High (headless, batch)** | **High (dyno-domain)** | **Dyno post-processing** |

### Key Differences

**DynoAI3 vs. INCA/CANape:**
- DynoAI3: Dyno-centric CSV contracts instead of ASAM
- DynoAI3: Post-processing only, no ECU communication
- Similar: Deterministic math, automation focus, hash verification

**DynoAI3 vs. MoTeC M1:**
- DynoAI3: External post-processing vs. in-ECU strategies
- DynoAI3: CSV-based vs. package-based
- Similar: Deterministic when configured correctly

**DynoAI3 vs. HP Tuners:**
- DynoAI3: Stronger automation and CLI support
- DynoAI3: Formal contracts and versioning
- DynoAI3: Built-in apply/rollback with verification
- Similar: Aftermarket focus, user-accessible

### Philosophical Alignment

DynoAI3 aligns philosophically with **ETAS INCA and Vector CANape** on:
- Determinism as a contractual obligation
- Automation and scripting as first-class features
- Formal data contracts with versioning
- Math stability over constant innovation

---

## 11. Trust Through Testing

DynoAI3's deterministic claims are validated by:

### Acceptance Test Suite

**File:** `acceptance_test.py`

**Tests:**
1. Clamping enforcement (±7% default)
2. Apply routine with 4-decimal precision
3. Metadata generation with SHA-256 hashes
4. Rollback routine verification
5. Dry-run mode validation
6. Factor bounds validation
7. Apply→Rollback symmetry proof
8. Deterministic hash validation

**Run:** `python acceptance_test.py`

### Self-Test Suite

**File:** `selftest.py`

**Tests:**
- Synthetic data generation
- Kernel smoothing validation
- Coverage calculation
- Manifest schema validation

**Run:** `python selftest.py`

### Continuous Integration

DynoAI3 uses regression testing to ensure math stability:
- Golden file comparisons
- Hash verification
- Manifest schema validation
- Apply/rollback symmetry

Any unintended math change will immediately fail CI.

---

## 12. How to Extend DynoAI3 Safely

If you need to modify DynoAI3's behavior:

### ✅ SAFE Extensions

**Add new features that don't affect core math:**
- New output formats (PVV, JSON, etc.)
- Additional diagnostics
- Enhanced coverage reporting
- UI improvements
- New validation checks
- Performance optimizations (same results)

**Example:** Adding JSON manifest output
- Keep CSV as primary format
- Add `--manifest-format json` flag
- Don't change manifest content

### ⚠️ REQUIRES VERSIONING

**Changes that affect calculation results:**
- New kernel algorithm
- Changed kernel parameters
- Different binning strategy
- Modified AFR error formula
- New clamping logic

**Required steps:**
1. Create new math version (e.g., `ve_math_v2/`)
2. Add `--math-version` flag to select
3. Tag outputs with `math_version: "2.0.0"`
4. Keep v1 runnable alongside v2
5. Update tests and documentation
6. Never cross-compare v1 and v2 results

### ❌ NEVER DO

**Silent math changes:**
- Changing kernel parameters without versioning
- "Improving" algorithms without documentation
- Adding randomness or adaptive behavior
- Breaking apply/rollback symmetry
- Removing hash verification

---

## 13. Auditability Features

DynoAI3 provides complete audit trails:

### Hash Verification

**SHA-256 hashing on:**
- Input CSV files
- Base VE tables
- Correction factor tables
- Applied VE tables

**Purpose:** Detect tampering, ensure rollback safety

**Location:** `ve_operations.py::compute_sha256()`

### Metadata Tracking

**Every operation records:**
- Timestamp (UTC, ISO 8601)
- Input file hashes
- Output file hashes
- Parameters used
- Application version
- User (if available)

### Immutable Raw Data

**Guarantee:** Source CSV files are **never modified**

All operations:
- Read from immutable source
- Write to new output files
- Preserve complete input history

### Path Safety

**Protection against:**
- Path traversal attacks
- Arbitrary file access
- Symbolic link exploits

**Implementation:** `io_contracts.safe_path()`

---

## 14. Production Safety

### Default Clamping

**Conservative ±7% limit** prevents dangerous corrections:
- Protects engine from extreme lean/rich conditions
- Allows gradual tuning refinement
- Can be increased if needed (use with caution)

### Dry-Run Mode

**Always preview before applying:**

```bash
python ve_operations.py apply \
  --base base_ve.csv \
  --factor correction.csv \
  --output preview.csv \
  --dry-run
```

Generates metadata and preview without committing changes.

### Rollback Safety

**Hash verification prevents rollback of:**
- Manually edited files
- Tampered corrections
- Wrong metadata

Ensures rollback is only possible on verified apply operations.

### Validation Layers

1. **Input validation** - CSV schema, value ranges
2. **Calculation validation** - Clamping, bounds checking
3. **Output validation** - Format, precision, completeness
4. **Metadata validation** - Schema compliance, hash verification

---

## 15. Future-Proofing

### Designed for Evolution

DynoAI3's architecture supports future enhancements:

- **New output formats** - Add exports without changing math
- **Enhanced diagnostics** - Improve analysis without affecting results
- **Coverage modeling** - Better confidence intervals, same corrections
- **Safety envelopes** - Additional validation, same core math
- **Tooling improvements** - Better automation, same determinism

### Non-Goals

DynoAI3 will **never** become:
- A machine learning system (despite the name)
- An adaptive tuning system
- A real-time controller
- An ECU flashing tool

These boundaries allow focus and excellence in the defined domain.

---

## 16. Summary

DynoAI3 is best described as:

> **A deterministic, automation-first, post-processing calibration engine for dyno data, with provable math, explicit boundaries, and OEM-inspired discipline.**

This positioning is defensible with:

✅ **Code** - Production-ready implementation  
✅ **Tests** - Comprehensive validation suite  
✅ **Documentation** - This specification  
✅ **Clear Limits** - Explicit boundaries  
✅ **Math Versioning** - Stability guarantees  
✅ **Audit Trail** - Complete traceability  
✅ **Apply/Rollback** - Exact mathematical inverses  
✅ **Automation** - Headless, batch, CI-ready  

**DynoAI3 achieves world-class calibration software status through discipline, not novelty.**

---

## Appendix A: Algorithm Details

### K1 Kernel Implementation

```python
def kernel_smooth(
    grid: List[List[Optional[float]]], 
    passes: int = 2, 
    gradient_threshold: float = 1.0
) -> List[List[Optional[float]]]:
    # Stage 1: Calculate gradients
    gradients = calculate_gradient_magnitudes(grid)
    
    # Stage 2: Adaptive smoothing
    adaptive_grid = apply_adaptive_smoothing(grid, passes)
    
    # Stage 3: Gradient-limited blending
    gradient_limited_grid = blend_by_gradient(
        grid, adaptive_grid, gradients, gradient_threshold
    )
    
    # Stage 4: Coverage-weighted smoothing
    final_grid = coverage_weighted_smooth(
        gradient_limited_grid,
        alpha=0.20,
        center_bias=1.25,
        min_hits=1,
        dist_pow=1
    )
    
    return final_grid
```

### Adaptive Smoothing Logic

```python
abs_correction = abs(center_val)
if abs_correction >= 3.0:
    adaptive_passes = 0  # Preserve large corrections
elif abs_correction <= 1.0:
    adaptive_passes = passes  # Smooth small corrections
else:
    # Linear taper
    taper_factor = (3.0 - abs_correction) / (3.0 - 1.0)
    adaptive_passes = int(round(passes * taper_factor))
```

### Gradient Blending

```python
if gradient_magnitude > gradient_threshold:
    blend_factor = min(1.0, gradient_magnitude / (gradient_threshold * 2))
    result = (1 - blend_factor) * smoothed_val + blend_factor * original_val
```

---

## Appendix B: Validation Checklist

Before releasing any code that affects tuning math:

- [ ] All acceptance tests pass
- [ ] Self-tests pass
- [ ] Apply→Rollback symmetry verified
- [ ] Hash verification works
- [ ] Clamping enforced correctly
- [ ] Metadata schema valid
- [ ] Output precision correct (4 decimals)
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Version incremented if math changed
- [ ] No randomness introduced
- [ ] No adaptive behavior added
- [ ] No hidden state between runs

---

**Document Version:** 1.1.0  
**Kernel Math Version:** 1.0.0 (FROZEN)  
**VE Correction Math Version:** 2.0.0 (DEFAULT)  
**Last Review:** 2025-12-15  
**Next Review:** Before any math modification
