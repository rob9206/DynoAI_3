# Changelog - October 29, 2025

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