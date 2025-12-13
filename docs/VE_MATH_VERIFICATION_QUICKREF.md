# VE Math Verification - Quick Reference

## Running the Verification Tests

```bash
# Run all verification tests
python -m pytest tests/test_ve_math_verification.py -v

# Run specific test class
python -m pytest tests/test_ve_math_verification.py::TestVEApplyRollbackInverse -v

# Display verification summary
python -c "from tests.test_ve_math_verification import VERIFICATION_SUMMARY; print(VERIFICATION_SUMMARY)"
```

## Test Coverage

| Test Area | Test Count | Purpose |
|-----------|------------|---------|
| Apply/Rollback Inverse | 2 | Verify mathematical inverse property |
| Clamping Limits | 3 | Verify safety limits are correct |
| Apply Math Formula | 3 | Verify apply formula correctness |
| Rollback Math Formula | 2 | Verify rollback formula correctness |
| Precision & Rounding | 2 | Verify 4-decimal precision handling |
| Binning Rules | 3 | Document and verify RPM/kPa bins |
| No Floating State | 2 | Verify statelessness |
| Metadata Integrity | 2 | Verify tamper detection |
| Kernel Determinism | 3 | Verify k1, k2, k3 are deterministic |
| Kernel Clamping Rules | 3 | Verify kernel-specific clamps |
| **TOTAL** | **25** | All passing ✅ |

## Key Mathematical Invariants (LOCKED 🔒)

### 1. Apply Formula
```python
updated_ve = base_ve × (1 + factor/100)
```
**Example**: base=100.0, factor=5.0% → updated=105.0

### 2. Rollback Formula
```python
restored_ve = current_ve / (1 + factor/100)
```
**Example**: current=105.0, factor=5.0% → restored=100.0

### 3. Inverse Property
```python
rollback(apply(base, factor), factor) == base  # within ±0.001
```

## Breaking vs Non-Breaking Changes

### ❌ BREAKING (DO NOT CHANGE without major version bump)
1. Apply/rollback formulas
2. Clamping logic
3. Storage precision (4 decimals)
4. Adding randomness or state

### ✅ NON-BREAKING (Safe to modify with versioning)
1. DEFAULT_MAX_ADJUST_PCT (if in metadata)
2. Kernel parameters (if versioned)
3. Adding new kernels (k4, k5, etc.)
4. Extending bin ranges (backward compatible)

## Kernel Clamp Quick Reference

| Kernel | Criterion | Clamp Limit |
|--------|-----------|-------------|
| **K1** | Gradient | ±7% default, gradient-limited smoothing |
| **K2** (Low Conf) | \|ΔVE\| ≤ 1% | ±15% (permissive) |
| **K2** (High Conf) | \|ΔVE\| ≥ 3% | ±7% (tight) |
| **K3** (High Cov) | ≥100 samples | ±7% (tight) |
| **K3** (Med Cov) | ≥20 samples | ±10% (medium) |
| **K3** (Low Cov) | <20 samples | ±15% (permissive) |

## Binning Structure

```python
RPM_BINS = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]  # 11 bins
KPA_BINS = [35, 50, 65, 80, 95]  # 5 bins
Table Size = 11 × 5 = 55 cells
```

## Verification Status

✅ **Determinism**: Same input → bit-identical output  
✅ **Inverse Property**: apply → rollback → exact original (±0.001)  
✅ **No Floating State**: Stateless operations  
✅ **No Hidden Normalization**: All transformations explicit  
✅ **Security**: 0 vulnerabilities detected  

## Full Documentation

See `docs/VE_MATH_VERIFICATION_REPORT.md` for complete verification report.
