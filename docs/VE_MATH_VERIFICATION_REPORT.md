# VE Tuning Math Verification Report

**Date**: 2025-12-13  
**Version**: DynoAI v3 (ve_operations.py v1.0.0)  
**Status**: ✅ VERIFIED - All invariants locked and tested

## Executive Summary

This report verifies that DynoAI3's VE tuning math is **internally consistent**, **deterministic**, and **invertible**. All mathematical operations have been traced end-to-end and proven to be free of floating state, cached artifacts, or hidden normalization.

**Key Finding**: The VE apply/rollback system implements a mathematically sound, reversible transformation with well-defined safety limits and deterministic behavior.

---

## 1. Core Mathematical Invariants (LOCKED)

### 1.1 Apply Formula
```
updated_ve = base_ve × (1 + factor/100)
```

**Location**: `ve_operations.py` line 363  
**Example**: base=100.0, factor=5.0% → updated=105.0  
**Test Coverage**: `TestApplyMathFormula`

### 1.2 Rollback Formula
```
restored_ve = current_ve / (1 + factor/100)
```

**Location**: `ve_operations.py` line 511  
**Example**: current=105.0, factor=5.0% → restored=100.0  
**Test Coverage**: `TestRollbackMathFormula`

### 1.3 Inverse Property (Verified)
```
rollback(apply(base, factor), factor) = base
```

**Precision**: ±0.001 (4 decimal places)  
**Test Coverage**: `test_apply_then_rollback_exact_inverse`  
**Verification Method**: Full end-to-end apply → rollback cycle with comparison to original

---

## 2. Determinism Verification

### 2.1 VEApply Determinism
**Invariant**: Same input → bit-identical output  
**Verified**: ✅ SHA-256 hash comparison  
**Test**: `test_determinism_same_input_same_output`

**Results**:
- Multiple runs with identical inputs produce identical CSV files (bit-for-bit)
- No time-based variation
- No randomness
- No instance state affects results

### 2.2 Kernel Determinism
All three kernel implementations (k1, k2, k3) are deterministic:

| Kernel | Name | Determinism | Test |
|--------|------|-------------|------|
| k1 | Gradient-Limited | ✅ Verified | `test_k1_gradient_limit_deterministic` |
| k2 | Coverage-Adaptive | ✅ Verified | `test_k2_coverage_adaptive_deterministic` |
| k3 | Bilateral | ✅ Verified | `test_k3_bilateral_deterministic` |

**Method**: Identical inputs produce identical outputs (double-run comparison)

---

## 3. Clamping and Safety Limits

### 3.1 VEApply Clamping
**Default Maximum**: ±7.0%  
**Configurable**: Yes (via `max_adjust_pct` parameter)  
**Symmetry**: ✅ Verified symmetric around zero  
**Location**: `clamp_factor_grid()` function

**Clamping Logic**:
```python
if factor > max_adjust_pct:
    clamped = max_adjust_pct
elif factor < -max_adjust_pct:
    clamped = -max_adjust_pct
else:
    clamped = factor
```

**Test Coverage**:
- `test_clamp_factor_grid_symmetric`
- `test_clamp_factor_grid_boundary_conditions`
- `test_clamp_preserves_structure`

### 3.2 Kernel-Specific Clamping Rules

#### K1 (Gradient-Limited Smoothing)
**File**: `experiments/protos/k1_gradient_limit_v1.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `gradient_threshold` | 1.0% | Limit smoothing where gradients exceed this |
| `alpha` | 0.20 | Blending weight for smoothed value |
| `center_bias` | 1.25 | Weight bias for center cell |
| `dist_pow` | 1 | Distance power for neighbor weighting |

**Adaptive Passes Logic**:
- |ΔVE| ≥ 3.0%: 0 passes (preserve large corrections)
- |ΔVE| ≤ 1.0%: full passes (smooth small corrections)
- 1.0% < |ΔVE| < 3.0%: linear taper

#### K2 (Coverage-Adaptive Clamping)
**File**: `experiments/protos/k2_coverage_adaptive_v1.py`

**Confidence-Based Clamp Limits**:
| Confidence Level | Magnitude | Clamp Limit |
|-----------------|-----------|-------------|
| Low | |ΔVE| ≤ 1.0% | ±15.0% (permissive, for exploration) |
| High | |ΔVE| ≥ 3.0% | ±7.0% (tight, for safety) |
| Medium | 1.0% < |ΔVE| < 3.0% | Linear interpolation |

**Rationale**: Use correction magnitude as proxy for data confidence

#### K3 (Bilateral with Coverage Tiers)
**File**: `experiments/protos/k3_bilateral_v1.py`

**Sample-Count-Based Clamp Limits**:
| Coverage Tier | Sample Count | Clamp Limit |
|--------------|--------------|-------------|
| High | ≥ 100 samples | ±7.0% (tight) |
| Medium | ≥ 20 samples | ±10.0% (medium) |
| Low | < 20 samples | ±15.0% (permissive) |

**Bilateral Weighting**:
```python
bilateral_weight = spatial_weight × similarity_weight
similarity_weight = exp(-(value_diff² / (2 × sigma²)))
```

**Parameters**:
- `sigma`: 0.75 (Gaussian similarity kernel width)
- `center_bias`: 1.25 (center cell weight multiplier)

---

## 4. Binning Rules

### 4.1 RPM Bins
**Definition**: `dynoai.constants.RPM_BINS`  
**Actual Values**: `[1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]`  
**Count**: 11 bins  
**Range**: 1500-6500 RPM  
**Step**: 500 RPM (with 1500 for low-end coverage)

### 4.2 kPa Bins
**Definition**: `dynoai.constants.KPA_BINS`  
**Actual Values**: `[35, 50, 65, 80, 95]`  
**Count**: 5 bins  
**Range**: 35-95 kPa  
**Step**: 15 kPa

### 4.3 Table Dimensions
**Structure**: (len(RPM_BINS) × len(KPA_BINS))  
**Current**: 11 × 5 = 55 cells per VE table  
**Verified**: ✅ All read/write operations preserve dimensions

---

## 5. Precision and Rounding

### 5.1 Storage Precision
**Format**: CSV with 4 decimal places  
**Example**: 80.123456789 → "80.1235"  
**Rounding**: Standard floating-point rounding (nearest)

### 5.2 Computational Precision
**Internal**: Python `float` (IEEE 754 double precision)  
**Accuracy**: Apply → Rollback restoration within ±0.001  
**Test**: `test_precision_preserved_through_apply_rollback`

**Finding**: The 4-decimal precision is sufficient to maintain mathematical consistency through apply/rollback cycles.

---

## 6. State and Caching Analysis

### 6.1 VEApply Statefulness
**Finding**: ✅ **STATELESS**

- No instance variables persist between calls
- No class-level caches
- No global state modified
- Multiple calls with same inputs produce identical results

**Test**: `test_apply_stateless_multiple_runs`

### 6.2 VERollback Statefulness
**Finding**: ✅ **STATELESS**

- No instance variables persist between calls
- Metadata read fresh each time
- No cached computations
- Multiple calls with same inputs produce identical results

**Test**: `test_rollback_stateless`

### 6.3 Hidden Normalization
**Finding**: ✅ **NONE DETECTED**

- No automatic scaling or normalization in apply/rollback
- Kernels apply explicit, documented transformations only
- All weighting and blending factors are explicit parameters

---

## 7. Kernel Ordering

### 7.1 Current State
**Finding**: **No enforced ordering in ve_operations.py**

The kernel registry (`experiments/kernel_registry.py`) defines k1, k2, k3 as **separate, independent smoothing algorithms**, not sequential stages.

**Usage Pattern**:
- Kernels are selected individually via registry lookup
- Each kernel can be used standalone
- No implicit k1 → k2 → k3 pipeline exists in core VE operations

### 7.2 Kernel Registry Structure
```python
REGISTRY = {
    "k1": ("experiments.protos.k1_gradient_limit_v1", "kernel_smooth", ...),
    "k2": ("experiments.protos.k2_coverage_adaptive_v1", "kernel_smooth", ...),
    "k3": ("experiments.protos.k3_bilateral_v1", "kernel_smooth", ...),
}
```

**Finding**: Kernels are **alternative implementations**, not sequential stages.

### 7.3 Recommendation
If kernel ordering is desired for future workflows:
1. Document explicitly in workflow orchestrator
2. Enforce in experiment runner, not in ve_operations.py
3. Version the pipeline (e.g., "pipeline_v1: k1 → k2 → k3")

---

## 8. Metadata and Audit Trail

### 8.1 Metadata Structure
**Location**: JSON file written alongside applied VE table  
**Required Fields**:

```json
{
  "operation": "apply",
  "base_sha": "<SHA-256 of base VE file>",
  "factor_sha": "<SHA-256 of factor file>",
  "applied_at_utc": "<ISO 8601 timestamp>",
  "max_adjust_pct": 7.0,
  "app_version": "1.0.0",
  "base_file": "/path/to/base.csv",
  "factor_file": "/path/to/factor.csv",
  "output_file": "/path/to/output.csv",
  "comment": "Rollback = divide by last factor..."
}
```

### 8.2 Tamper Detection
**Mechanism**: SHA-256 hash verification  
**Verified**: ✅ Rollback checks factor file hash matches metadata  
**Test**: `test_metadata_contains_hashes`

**Protection**:
- Rollback fails if factor file modified after apply
- Hash mismatch raises `RuntimeError` with clear message
- Prevents accidental rollback with wrong factor file

---

## 9. Breaking Changes

### 9.1 Mathematical Breaking Changes
Any of these would break the inverse property and constitute a **MAJOR BREAKING CHANGE**:

1. ❌ Modifying apply formula (line 363 of ve_operations.py)
2. ❌ Modifying rollback formula (line 511 of ve_operations.py)
3. ❌ Changing clamping logic
4. ❌ Altering precision (4 decimals)
5. ❌ Adding hidden normalization
6. ❌ Introducing randomness

### 9.2 Non-Breaking Changes
These can be modified safely:

1. ✅ Changing `DEFAULT_MAX_ADJUST_PCT` (if versioned in metadata)
2. ✅ Adding new kernel implementations (k4, k5, etc.)
3. ✅ Modifying kernel parameters (if versioned)
4. ✅ Extending binning ranges (if backward compatible)
5. ✅ Adding new metadata fields (non-destructive)

### 9.3 Change Management
**Recommendation**:
- Version all mathematical formulas
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Include `math_version` in metadata
- Reject rollback if versions mismatch

---

## 10. Test Coverage Summary

| Test Class | Tests | Status | Coverage |
|------------|-------|--------|----------|
| TestVEApplyRollbackInverse | 2 | ✅ PASS | Core inverse property |
| TestClampingLimits | 3 | ✅ PASS | Clamping logic |
| TestApplyMathFormula | 3 | ✅ PASS | Apply formula |
| TestRollbackMathFormula | 2 | ✅ PASS | Rollback formula |
| TestPrecisionAndRounding | 2 | ✅ PASS | Precision handling |
| TestBinningRules | 3 | ✅ PASS | Bin structure |
| TestNoFloatingState | 2 | ✅ PASS | Statelessness |
| TestMetadataIntegrity | 2 | ✅ PASS | Metadata & hashes |
| TestKernelDeterminism | 3 | ✅ PASS | Kernel determinism |
| TestKernelClampingRules | 3 | ✅ PASS | Kernel-specific rules |

**Total**: 25 tests, 25 passed, 0 failed

---

## 11. Conclusions

### 11.1 Mathematically Locked ✅
The following are **proven invariants** that must not change:

1. **Apply/Rollback formulas** (multiplication/division by `(1 + factor/100)`)
2. **Inverse property** (apply → rollback → exact original within 4 decimals)
3. **Determinism** (same input → identical output)
4. **Statefulness** (no hidden state or caching)
5. **Precision** (4 decimal places for CSV storage)

### 11.2 Well-Documented ✅
The following are **documented but configurable**:

1. **Clamping limits** (default ±7%, configurable)
2. **Kernel parameters** (alpha, sigma, thresholds, etc.)
3. **Binning rules** (RPM: 1500-6500, kPa: 35-95)

### 11.3 No Issues Found ✅
- ✅ No floating state
- ✅ No cached artifacts
- ✅ No hidden normalization
- ✅ No randomness
- ✅ No kernel ordering enforcement (kernels are alternatives, not stages)

### 11.4 Verification Status
**Overall**: ✅ **VERIFIED - PRODUCTION READY**

The VE tuning math is mathematically sound, deterministic, and safe for production use. All invariants are tested and locked.

---

## 12. Recommendations

1. **Version Control**: Add `math_version` field to metadata for future-proofing
2. **Kernel Ordering**: If k1 → k2 → k3 pipeline is desired, implement and document explicitly
3. **Extended Tests**: Add property-based testing (e.g., hypothesis) for broader coverage
4. **Performance**: Current implementation prioritizes correctness; optimize if needed
5. **Documentation**: Maintain this verification report with each mathematical change

---

## Appendix A: Test Execution

**Command**: `python -m pytest tests/test_ve_math_verification.py -v`  
**Result**: 25 passed in 0.10s  
**Environment**: Python 3.12.3, pytest 9.0.2

**Test File**: `/tests/test_ve_math_verification.py`  
**Lines of Test Code**: ~700 lines  
**Coverage**: Core VE operations and all three kernel implementations

---

## Appendix B: References

- `ve_operations.py`: Core VE apply/rollback implementation
- `experiments/kernel_registry.py`: Kernel registry and resolution
- `experiments/protos/k1_gradient_limit_v1.py`: K1 implementation
- `experiments/protos/k2_coverage_adaptive_v1.py`: K2 implementation
- `experiments/protos/k3_bilateral_v1.py`: K3 implementation
- `dynoai/constants.py`: RPM_BINS, KPA_BINS definitions

---

**Report Generated**: 2025-12-13  
**Verified By**: Automated test suite (test_ve_math_verification.py)  
**Next Review**: Before any mathematical formula changes
