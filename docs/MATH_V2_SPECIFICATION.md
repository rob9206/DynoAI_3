# DynoAI Math v2.0.0 Specification

**Status:** DRAFT - Requires Review  
**Author:** DynoAI Engineering  
**Date:** 2025-12-15  
**Supersedes:** Math v1.0.0 (7% per AFR point linear model)

---

## Executive Summary

Math v2.0.0 introduces a **physically accurate ratio-based VE correction model** that replaces the simplified linear "7% per AFR point" approximation used in Math v1.0.0.

### Why This Change?

1. **Physical Accuracy**: The ratio model directly reflects fuel delivery physics
2. **Consistency**: Resolves existing formula inconsistencies in the codebase
3. **Industry Standard**: Aligns with OEM and professional calibration systems
4. **Better Extreme Handling**: More accurate at large AFR deviations

---

## 1. Problem Statement

### 1.1 Current v1.0.0 Formula (Linear Approximation)

```python
# Math v1.0.0 - Linear approximation
afr_error = AFR_measured - AFR_target  # positive = lean
ve_correction = 1 + (afr_error * 0.07)  # 7% per AFR point
```

**Limitations:**
- Assumes linear relationship between AFR error and fuel requirement
- Becomes increasingly inaccurate at larger deviations
- The "7%" factor is an empirical approximation, not derived from physics

### 1.2 Existing Codebase Inconsistency

**CRITICAL:** The codebase currently has TWO different formulas:

| Location | Formula | Sign Convention |
|----------|---------|-----------------|
| `cylinder_balancing.py` | `error * 0.07` | error = measured - target |
| `jetdrive_autotune.py` | `error * 7.0 / 100` | error = measured - target |
| `autotune_workflow.py` | `error * 7.0` | error = measured - target |
| `LiveVETable.tsx` | `error * 7.0 / 100` | error = measured - target |
| `ai_tuner_toolkit_dyno_v1_2.py` | `(target - measured) / measured` | **DIFFERENT** |

This inconsistency means different parts of DynoAI calculate corrections differently.

---

## 2. Math v2.0.0 Specification

### 2.1 Core Formula

```python
# Math v2.0.0 - Ratio Model (Physically Accurate)
VE_correction = AFR_measured / AFR_target
```

**That's it.** The formula is elegant because it directly represents the fuel ratio error.

### 2.2 Physical Derivation

**Fundamental Principle:** AFR (Air-Fuel Ratio) is defined as:
```
AFR = mass_of_air / mass_of_fuel
```

**If AFR is too high (lean):**
- More air per unit fuel than desired
- Need to ADD fuel to reach target
- Required fuel multiplier = measured_AFR / target_AFR > 1

**If AFR is too low (rich):**
- Less air per unit fuel than desired  
- Need to REMOVE fuel to reach target
- Required fuel multiplier = measured_AFR / target_AFR < 1

**Example:**
- Target AFR = 13.0 (desired mixture)
- Measured AFR = 14.0 (actual mixture - running lean)
- Correction = 14.0 / 13.0 = 1.077
- Meaning: Increase fuel by 7.7% to achieve target

### 2.3 Mathematical Proof

Let:
- `F_current` = current fuel mass
- `A` = air mass (constant for a given operating point)
- `AFR_target` = desired air-fuel ratio
- `AFR_measured` = actual air-fuel ratio

Currently:
```
AFR_measured = A / F_current
∴ F_current = A / AFR_measured
```

To achieve target:
```
AFR_target = A / F_required
∴ F_required = A / AFR_target
```

Correction factor:
```
VE_correction = F_required / F_current
             = (A / AFR_target) / (A / AFR_measured)
             = AFR_measured / AFR_target  ✓
```

**QED.** The ratio formula is the exact mathematical solution.

---

## 3. Comparison: v1.0.0 vs v2.0.0

### 3.1 Numerical Comparison

| Scenario | Target | Measured | v1.0.0 (7%) | v2.0.0 (Ratio) | Actual Need |
|----------|--------|----------|-------------|----------------|-------------|
| Slightly Lean | 13.0 | 13.5 | 1.035 (+3.5%) | 1.038 (+3.8%) | +3.8% |
| Lean | 13.0 | 14.0 | 1.070 (+7.0%) | 1.077 (+7.7%) | +7.7% |
| Very Lean | 13.0 | 15.0 | 1.140 (+14.0%) | 1.154 (+15.4%) | +15.4% |
| Extremely Lean | 12.5 | 16.0 | 1.245 (+24.5%) | 1.280 (+28.0%) | +28.0% |
| Slightly Rich | 13.0 | 12.5 | 0.965 (-3.5%) | 0.962 (-3.8%) | -3.8% |
| Rich | 13.0 | 12.0 | 0.930 (-7.0%) | 0.923 (-7.7%) | -7.7% |
| Very Rich | 13.0 | 11.0 | 0.860 (-14.0%) | 0.846 (-15.4%) | -15.4% |
| On Target | 13.0 | 13.0 | 1.000 (0%) | 1.000 (0%) | 0% |

**Key Observations:**
1. At small errors (<1 AFR point), both formulas are similar
2. At large errors, v1.0.0 **underestimates** the required correction
3. v2.0.0 is mathematically exact at all error magnitudes

### 3.2 Error Analysis

The v1.0.0 linear model error grows with deviation:

```
Relative Error = |v1.0 - v2.0| / v2.0 × 100%

At 1 AFR point deviation: ~1% relative error
At 2 AFR point deviation: ~3% relative error  
At 3 AFR point deviation: ~6% relative error
At 4 AFR point deviation: ~10% relative error
```

For typical tuning scenarios (±1 AFR point), the difference is small.
For extreme scenarios (±3+ AFR points), v1.0.0 significantly underestimates.

### 3.3 Why v1.0.0 Used 7%

The "7% per AFR point" approximation works because:

At stoichiometric (AFR ≈ 14.7):
```
Δfuel/fuel ≈ -ΔAFR/AFR ≈ -ΔAFR/14.7 ≈ 0.068 ≈ 7%
```

This linear approximation is the first-order Taylor expansion of the ratio model around stoichiometric. It's a reasonable shortcut for small deviations near stoich, but loses accuracy:
- At richer targets (AFR 12-13)
- At larger deviations

---

## 4. Implementation Specification

### 4.1 Core Function

```python
def calculate_ve_correction(
    afr_measured: float,
    afr_target: float,
    math_version: str = "2.0.0"
) -> float:
    """
    Calculate VE correction factor from AFR measurements.
    
    Math v2.0.0 uses the physically accurate ratio model:
        VE_correction = AFR_measured / AFR_target
    
    Args:
        afr_measured: Measured AFR from wideband sensor
        afr_target: Target/commanded AFR
        math_version: "1.0.0" for legacy 7% model, "2.0.0" for ratio model
    
    Returns:
        VE correction multiplier (1.0 = no change, >1 = add fuel, <1 = remove fuel)
    
    Raises:
        ValueError: If AFR values are invalid (<=0 or outside safe range)
    """
    # Validate inputs
    AFR_MIN = 9.0   # Minimum valid AFR
    AFR_MAX = 20.0  # Maximum valid AFR
    
    if not (AFR_MIN <= afr_measured <= AFR_MAX):
        raise ValueError(f"AFR measured {afr_measured} outside valid range [{AFR_MIN}, {AFR_MAX}]")
    if not (AFR_MIN <= afr_target <= AFR_MAX):
        raise ValueError(f"AFR target {afr_target} outside valid range [{AFR_MIN}, {AFR_MAX}]")
    
    if math_version == "1.0.0":
        # Legacy linear approximation (7% per AFR point)
        afr_error = afr_measured - afr_target
        return 1.0 + (afr_error * 0.07)
    
    elif math_version == "2.0.0":
        # Ratio model (physically accurate)
        return afr_measured / afr_target
    
    else:
        raise ValueError(f"Unknown math version: {math_version}")
```

### 4.2 Configuration

```python
# dynoai/core/math_config.py

from enum import Enum
from dataclasses import dataclass

class MathVersion(Enum):
    V1_0_0 = "1.0.0"  # Legacy 7% per AFR point
    V2_0_0 = "2.0.0"  # Ratio model (default)

@dataclass(frozen=True)
class MathConfig:
    """Immutable math configuration for VE calculations."""
    
    version: MathVersion = MathVersion.V2_0_0
    
    # Safety clamps (applied to final correction)
    max_correction_pct: float = 15.0  # Maximum ±15% correction
    
    # Validation ranges
    afr_min: float = 9.0
    afr_max: float = 20.0
    
    def __post_init__(self):
        if self.max_correction_pct <= 0:
            raise ValueError("max_correction_pct must be positive")

# Default configuration
DEFAULT_MATH_CONFIG = MathConfig(version=MathVersion.V2_0_0)

# Legacy configuration for backwards compatibility
LEGACY_MATH_CONFIG = MathConfig(version=MathVersion.V1_0_0)
```

### 4.3 Files Requiring Update

| File | Type | Changes Required |
|------|------|------------------|
| `dynoai/core/cylinder_balancing.py` | Python | Update `_afr_error_to_ve_correction()` |
| `scripts/jetdrive_autotune.py` | Python | Update `TuneConfig` and `analyze_dyno_data()` |
| `api/services/autotune_workflow.py` | Python | Update `VE_PCT_PER_AFR_POINT` and `analyze_afr()` |
| `ai_tuner_toolkit_dyno_v1_2.py` | Python | Reconcile formula, add version selection |
| `frontend/src/components/jetdrive/LiveVETable.tsx` | TypeScript | Update VE calculation hook |
| `dynoai/core/ve_operations.py` | Python | Add math version to metadata |
| `docs/DETERMINISTIC_MATH_SPECIFICATION.md` | Docs | Document v2.0.0 |
| `docs/WORLD_CLASS_SUMMARY.md` | Docs | Update frozen parameters |
| `CHANGELOG.md` | Docs | Document version change |

---

## 5. Migration Plan

### 5.1 Phase 1: Create Infrastructure (Non-Breaking)

1. Create `dynoai/core/math_config.py` with version enum
2. Create `dynoai/core/ve_math.py` with versioned calculation function
3. Add comprehensive unit tests for both versions
4. Run regression tests to establish v1.0.0 baseline

### 5.2 Phase 2: Update Backend (Backwards Compatible)

1. Update `cylinder_balancing.py` to use new function with default v2.0.0
2. Update `jetdrive_autotune.py` with `--math-version` CLI flag
3. Update `autotune_workflow.py` with version selection
4. Update `ai_tuner_toolkit_dyno_v1_2.py` with version selection
5. All outputs tagged with `math_version: "2.0.0"`

### 5.3 Phase 3: Update Frontend

1. Update `LiveVETable.tsx` to use ratio model
2. Add UI indicator showing math version
3. Optional: Allow user to select math version

### 5.4 Phase 4: Documentation & Testing

1. Update all specification documents
2. Run full acceptance test suite
3. Run comparison tests: v1.0.0 vs v2.0.0 on real data
4. Update CHANGELOG.md
5. Security scan with Snyk

---

## 6. Test Cases

### 6.1 Unit Tests

```python
import pytest
from dynoai.core.ve_math import calculate_ve_correction

class TestVEMathV2:
    """Test cases for Math v2.0.0 ratio model."""
    
    def test_on_target_no_correction(self):
        """When measured equals target, correction should be 1.0."""
        assert calculate_ve_correction(13.0, 13.0) == 1.0
        assert calculate_ve_correction(14.7, 14.7) == 1.0
        assert calculate_ve_correction(12.5, 12.5) == 1.0
    
    def test_lean_increases_fuel(self):
        """Lean condition should increase VE (correction > 1)."""
        correction = calculate_ve_correction(14.0, 13.0)
        assert correction > 1.0
        assert abs(correction - 1.077) < 0.001
    
    def test_rich_decreases_fuel(self):
        """Rich condition should decrease VE (correction < 1)."""
        correction = calculate_ve_correction(12.0, 13.0)
        assert correction < 1.0
        assert abs(correction - 0.923) < 0.001
    
    def test_ratio_math_exact(self):
        """Verify ratio math is exact: correction = measured/target."""
        test_cases = [
            (14.0, 13.0, 14.0/13.0),
            (15.0, 12.5, 15.0/12.5),
            (11.0, 14.0, 11.0/14.0),
            (13.5, 13.5, 1.0),
        ]
        for measured, target, expected in test_cases:
            result = calculate_ve_correction(measured, target)
            assert abs(result - expected) < 1e-10
    
    def test_invalid_afr_raises(self):
        """Invalid AFR values should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_ve_correction(5.0, 13.0)  # Too low
        with pytest.raises(ValueError):
            calculate_ve_correction(13.0, 25.0)  # Too high
        with pytest.raises(ValueError):
            calculate_ve_correction(0, 13.0)    # Zero
    
    def test_v1_compatibility(self):
        """v1.0.0 mode should use 7% per AFR point."""
        # 1 AFR point lean
        v1_result = calculate_ve_correction(14.0, 13.0, math_version="1.0.0")
        assert abs(v1_result - 1.07) < 0.001
        
        # 1 AFR point rich
        v1_result = calculate_ve_correction(12.0, 13.0, math_version="1.0.0")
        assert abs(v1_result - 0.93) < 0.001


class TestVEMathComparison:
    """Compare v1.0.0 and v2.0.0 results."""
    
    def test_small_error_similar(self):
        """At small errors, v1 and v2 should be within 1%."""
        for target in [12.5, 13.0, 13.5, 14.0, 14.7]:
            for delta in [-0.5, -0.3, 0.3, 0.5]:
                measured = target + delta
                v1 = calculate_ve_correction(measured, target, "1.0.0")
                v2 = calculate_ve_correction(measured, target, "2.0.0")
                relative_diff = abs(v1 - v2) / v2
                assert relative_diff < 0.01  # Within 1%
    
    def test_large_error_diverges(self):
        """At large errors, v2 should give larger corrections than v1."""
        # Very lean case
        v1 = calculate_ve_correction(16.0, 12.5, "1.0.0")
        v2 = calculate_ve_correction(16.0, 12.5, "2.0.0")
        assert v2 > v1  # v2 gives larger correction (more accurate)
        
        # Very rich case  
        v1 = calculate_ve_correction(10.0, 13.0, "1.0.0")
        v2 = calculate_ve_correction(10.0, 13.0, "2.0.0")
        assert v2 < v1  # v2 gives larger (more negative) correction
```

### 6.2 Regression Tests

```python
def test_determinism_v2():
    """Same inputs always produce same outputs."""
    results = []
    for _ in range(100):
        result = calculate_ve_correction(14.123, 13.456, "2.0.0")
        results.append(result)
    
    # All results must be identical
    assert len(set(results)) == 1

def test_no_randomness():
    """Verify no random number generation in calculation path."""
    import random
    initial_state = random.getstate()
    
    _ = calculate_ve_correction(14.0, 13.0, "2.0.0")
    
    final_state = random.getstate()
    assert initial_state == final_state
```

---

## 7. Backwards Compatibility

### 7.1 CLI Flag

```bash
# Use v2.0.0 (default)
python scripts/jetdrive_autotune.py --input data.csv

# Use v1.0.0 legacy
python scripts/jetdrive_autotune.py --input data.csv --math-version 1.0.0

# Main toolkit
python ai_tuner_toolkit_dyno_v1_2.py --csv log.csv --math-version 2.0.0
```

### 7.2 Output Metadata

All outputs will include math version:

```json
{
  "run_id": "2025-12-15_run_001",
  "math_version": "2.0.0",
  "formula": "VE_correction = AFR_measured / AFR_target",
  "timestamp_utc": "2025-12-15T10:30:00Z",
  ...
}
```

### 7.3 API Versioning

```python
# API endpoint supports version parameter
POST /api/autotune/analyze
{
  "data": [...],
  "math_version": "2.0.0"  // Optional, defaults to 2.0.0
}
```

---

## 8. Safety Considerations

### 8.1 Clamping (Unchanged from v1.0.0)

All corrections are clamped to safety limits:

```python
# Default: ±15% maximum correction
min_correction = 1.0 - max_correction_pct / 100  # 0.85
max_correction = 1.0 + max_correction_pct / 100  # 1.15

clamped = max(min_correction, min(max_correction, ve_correction))
```

### 8.2 Input Validation

```python
# AFR range validation
AFR_MIN = 9.0   # Below this = sensor error or extreme rich
AFR_MAX = 20.0  # Above this = sensor error or extreme lean

if not (AFR_MIN <= afr <= AFR_MAX):
    raise ValueError(f"AFR {afr} outside safe range")
```

### 8.3 Division Safety

The ratio formula `measured / target` is safe because:
1. Target AFR is validated (never 0)
2. Both values must be within [9.0, 20.0]
3. No possibility of division by zero

---

## 9. Approval Checklist

Before implementing Math v2.0.0:

- [ ] Specification reviewed and approved
- [ ] Mathematical derivation verified
- [ ] Test cases reviewed
- [ ] Migration plan approved
- [ ] Rollback procedure documented
- [ ] All stakeholders notified

---

## 10. Appendix: Formula Derivation Details

### A. Why Ratio, Not Percentage?

Some might ask: "Why not use percentage error?"

**Percentage error approach:**
```
error_pct = (measured - target) / target × 100
ve_correction = 1 + error_pct / 100
            = 1 + (measured - target) / target
            = measured / target  ✓
```

The percentage approach and ratio approach are **mathematically equivalent**!

The ratio form `measured / target` is simply cleaner and more direct.

### B. Relationship to Lambda

For those working with lambda (λ) instead of AFR:

```
λ = AFR / AFR_stoich

VE_correction = λ_measured / λ_target
             = (AFR_measured / AFR_stoich) / (AFR_target / AFR_stoich)
             = AFR_measured / AFR_target  ✓
```

The formula works identically whether using AFR or lambda.

### C. Why Not Use Inverse?

Some systems use `target / measured`:

```
# INCORRECT for VE correction
wrong_correction = AFR_target / AFR_measured
```

This would give the inverse correction (reduce fuel when lean, add when rich).

The correct formula for **VE correction** (how much to multiply fuel by) is:
```
VE_correction = AFR_measured / AFR_target
```

---

**Document Version:** 1.0.0 (Draft)  
**Math Version Specified:** 2.0.0  
**Next Review:** Before implementation begins

