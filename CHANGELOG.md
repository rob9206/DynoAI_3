# Changelog

## v1.0.0 - Deterministic Math Freeze (December 13, 2025)

### 🎯 World-Class Calibration System

DynoAI3 is now formally positioned as a **deterministic, automation-first, post-processing calibration engine** with provable math and OEM-inspired discipline.

### Major Documentation

#### New Documentation
- **[DETERMINISTIC_MATH_SPECIFICATION.md](docs/DETERMINISTIC_MATH_SPECIFICATION.md)** - Complete mathematical specification
  - Formal definition of deterministic math
  - Apply/rollback guarantees with proofs
  - Data contract specifications
  - Math versioning policy
  - Comparison with OEM systems (ETAS INCA, Vector CANape, MoTeC, HP Tuners)
  
- **[KERNEL_SPECIFICATION.md](docs/KERNEL_SPECIFICATION.md)** - Detailed kernel algorithms
  - K1: Gradient-limited adaptive smoothing (frozen)
  - K2: Coverage-weighted smoothing (frozen)
  - K3: Tiered spark logic (frozen)
  - Mathematical formulas and proofs
  - Determinism guarantees
  
- **[AUTOMATION_SCRIPTING_GUIDE.md](docs/AUTOMATION_SCRIPTING_GUIDE.md)** - Automation workflows
  - Headless CLI operations
  - Batch processing examples
  - CI/CD integration patterns
  - Function-level APIs
  - Best practices

#### Updated Documentation
- **README.md** - Emphasizes world-class positioning and deterministic math
- **DYNOAI_ARCHITECTURE_OVERVIEW.md** - Updated with core philosophy

### Math Version Freeze

**Math Version: 1.0.0**

The following algorithms are now **frozen** and will not change without a major version increment:

**K1 Parameters (Frozen):**
- `passes = 2`
- `gradient_threshold = 1.0`
- Large correction threshold: 3.0%
- Small correction threshold: 1.0%

**K2 Parameters (Frozen):**
- `alpha = 0.20`
- `center_bias = 1.25`
- `min_hits = 1`
- `dist_pow = 1`

**K3 Parameters (Frozen):**
- `extra_rule_deg = 2.0`
- `hot_extra = -1.0`
- Power band RPM: 2800-3600
- Power band MAP: 75-95 kPa

**Core Operations (Frozen):**
- VEApply formula: `VE_new = VE_base × (1 + factor/100)`
- VERollback formula: `VE_restored = VE_current / (1 + factor/100)`
- Default clamping: ±7%
- SHA-256 hash verification

### Explicit Boundaries

**What DynoAI3 IS:**
- Deterministic post-processing VE calibration engine
- Dyno data analyzer (CSV input)
- VE correction factor generator
- Spark timing suggestion system
- Apply/rollback with hash verification
- Automation-first with headless CLI

**What DynoAI3 is NOT:**
- NOT a dyno controller
- NOT an ECU communication tool
- NOT real-time or closed-loop
- NOT adaptive or learning-based
- NOT ML-based (despite the name)

### Guarantees

✅ Same inputs → same outputs (bit-for-bit)  
✅ Apply→Rollback symmetry (proven in acceptance tests)  
✅ No randomness, no adaptive learning  
✅ No cross-run state  
✅ SHA-256 verification on all apply operations  
✅ Formal data contracts with validation  

### Version Stability Policy

Any change to the frozen algorithms requires:
1. Major version increment (v1.0.0 → v2.0.0)
2. Algorithm version tag in outputs
3. Ability to run old version alongside new
4. Full regression test suite
5. Documentation update and user notification
6. Migration guide

---

## v1.3 - Adaptive Kernel System (October 29, 2025)

### Major Features

#### Two-Stage Adaptive Kernel Implementation
- **New Default Kernel**: Implemented two-stage kernel combining adaptive smoothing with coverage-weighted smoothing
- **Adaptive Smoothing**: First stage applies 0-2 smoothing passes based on center cell correction magnitude
  - Corrections ≥3.0%: 0 passes (preserve large corrections)
  - Corrections ≤1.0%: 2 passes (smooth small corrections)
  - Linear taper between thresholds for smooth transitions
- **Coverage-Weighted Smoothing**: Second stage applies neighbor-weighted averaging with configurable parameters
  - Alpha: 0.20 (smoothing strength)
  - Center bias: 1.25 (preserve center cell influence)
  - Minimum hits: 1 (include all cells)
  - Distance power: 1 (linear distance weighting)

#### Enhanced Test Data Generation
- **Realistic AFR Errors**: Updated synthetic data generation to use percentage-based AFR errors
  - Replaced absolute AFR errors with percentage-based variance (±8-9%)
  - Uses Gaussian noise + sinusoidal patterns for realistic large corrections
  - Enables proper testing of adaptive kernel behavior with meaningful deltas

#### Production Safety Improvements
- **Updated Clamping**: Changed default correction clamping from ±15% to ±7% for production safety
- **Validation**: All changes validated through self-tests, acceptance tests, and integration testing

### Technical Details
- **Files Modified**:
  - `ai_tuner_toolkit_dyno_v1_2.py`: Integrated two-stage kernel as default `kernel_smooth()` function
  - `selftest.py`: Updated `make_synthetic_csv()` for percentage-based AFR error generation
  - `io_contracts.py`: Updated manifest schema for new kernel parameters
  - `ve_operations.py`: Maintained compatibility with updated clamping defaults
- **Validation Results**: Adaptive behavior confirmed (0.41% max delta between kernel variants)
- **Git Integration**: Changes committed and pushed to main branch (commit: 1cdf8142)

### Documentation
- **Integration Summary**: Created `TWO_STAGE_KERNEL_INTEGRATION.md` with comprehensive implementation details
- **Kernel Parameters**: Documented all configurable parameters and their effects
- **Testing Strategy**: Updated test data generation for realistic kernel validation

## Bug Fixes

### Fixed VE Table Format Issue
- **Problem**: Base front VE table (`tables/FXDLS_Wheelie_VE_Base_Front.csv`) had incorrect format
  - Table was transposed with MAP values as rows and RPM values as columns
  - Code expects RPM values as rows and MAP values as columns
  - This caused the error "missing RPM header row"

### Added New Files
1. `fix_ve_table.py`
   - New utility script to transpose VE tables
   - Correctly formats CSV files to match expected layout
   - Changes first cell header to "RPM"
   - Creates output with `_fixed` suffix

### Modified Files
1. `selftest_runner.py`
   - Updated to use fixed VE table (`FXDLS_Wheelie_VE_Base_Front_fixed.csv`)
   - Changed base_front path to point to new transposed file

### Generated Files
- `tables/FXDLS_Wheelie_VE_Base_Front_fixed.csv`
  - Transposed version of original VE table
  - Properly formatted with RPM as rows and MAP as columns

### Test Results
- Selftest now passes successfully
- All expected output files are generated correctly
- Verified in output directory: `outputs_selftest_20251029_165311`