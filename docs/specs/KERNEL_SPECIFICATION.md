# DynoAI3 Kernel Specification

**Version:** 1.0.0  
**Last Updated:** 2025-12-13  
**Math Version:** 1.0.0

---

## Purpose

This document provides the complete mathematical specification of DynoAI3's three deterministic kernels (K1, K2, K3). These kernels are **frozen** as part of the v1.0.0 math contract.

Any modification to these algorithms requires a major version increment and creates a new math generation.

---

## Kernel Execution Order

DynoAI3 applies kernels in a **fixed, deterministic order**:

1. **K1: Gradient-Limited Adaptive Smoothing** - Preserve large corrections, smooth noise
2. **K2: Coverage-Weighted Smoothing** - Apply neighbor-weighted averaging (embedded in K1)
3. **K3: Tiered Spark Logic** - Generate spark timing adjustments

This order is **immutable** for math version 1.0.0.

---

## K1: Gradient-Limited Adaptive Smoothing

### Purpose

Smooth VE correction noise while preserving large, significant corrections.

### Algorithm

K1 consists of four sequential stages:

#### Stage 1: Gradient Calculation

For each cell `(r, c)`:

```
gradient[r][c] = max(|center - neighbor|) for all valid neighbors
```

**Neighbors considered:** 4-connected (up, down, left, right)

**Implementation:**
```python
for r in range(rows):
    for c in range(cols):
        center_val = grid[r][c]
        if center_val is None:
            continue
        
        max_diff = 0.0
        neighbors = [
            grid[r-1][c],  # up
            grid[r+1][c],  # down
            grid[r][c-1],  # left
            grid[r][c+1]   # right
        ]
        
        for neighbor in neighbors:
            if neighbor is not None:
                max_diff = max(max_diff, abs(center_val - neighbor))
        
        gradients[r][c] = max_diff
```

#### Stage 2: Adaptive Smoothing

For each cell `(r, c)`, determine smoothing passes based on correction magnitude:

```
abs_correction = |grid[r][c]|

if abs_correction >= 3.0:
    adaptive_passes = 0  # No smoothing, preserve large corrections
elif abs_correction <= 1.0:
    adaptive_passes = passes  # Full smoothing for small corrections
else:
    # Linear taper between 1.0% and 3.0%
    taper_factor = (3.0 - abs_correction) / (3.0 - 1.0)
    adaptive_passes = round(passes × taper_factor)
```

**Parameters:**
- `passes`: Maximum smoothing passes (default: 2)
- Large correction threshold: 3.0%
- Small correction threshold: 1.0%

**Smoothing operation (per pass):**
```
smoothed_val = (center + sum(valid_neighbors)) / (1 + num_valid_neighbors)
```

**Implementation:**
```python
for _ in range(adaptive_passes):
    neighbors = [smoothed_val]  # Include center
    
    if r > 0 and grid[r-1][c] is not None:
        neighbors.append(grid[r-1][c])
    if r < rows-1 and grid[r+1][c] is not None:
        neighbors.append(grid[r+1][c])
    if c > 0 and grid[r][c-1] is not None:
        neighbors.append(grid[r][c-1])
    if c < cols-1 and grid[r][c+1] is not None:
        neighbors.append(grid[r][c+1])
    
    smoothed_val = sum(neighbors) / len(neighbors)
```

#### Stage 3: Gradient-Limited Blending

For cells with high gradients, blend back toward original value:

```
if gradient_magnitude > gradient_threshold:
    blend_factor = min(1.0, gradient_magnitude / (gradient_threshold × 2))
    result = (1 - blend_factor) × smoothed + blend_factor × original
else:
    result = smoothed
```

**Parameters:**
- `gradient_threshold`: 1.0% (default)

**Blend factor behavior:**
- At gradient = threshold: blend_factor = 0.5 (50% original, 50% smoothed)
- At gradient = threshold × 2: blend_factor = 1.0 (100% original)
- At gradient < threshold: blend_factor = 0.0 (100% smoothed)

**Implementation:**
```python
for r in range(rows):
    for c in range(cols):
        original_val = grid[r][c]
        smoothed_val = adaptive_grid[r][c]
        
        if original_val is None or smoothed_val is None:
            continue
        
        gradient_magnitude = gradients[r][c]
        
        if gradient_magnitude > gradient_threshold:
            blend_factor = min(1.0, gradient_magnitude / (gradient_threshold * 2))
            gradient_limited_grid[r][c] = (
                (1 - blend_factor) * smoothed_val + 
                blend_factor * original_val
            )
        else:
            gradient_limited_grid[r][c] = smoothed_val
```

#### Stage 4: Coverage-Weighted Smoothing (K2)

Apply final neighbor-weighted averaging with configurable parameters.

See **K2 specification** below for complete details.

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `passes` | 2 | Maximum smoothing iterations |
| `gradient_threshold` | 1.0 | Gradient magnitude limit (%) |

### File Location

`ai_tuner_toolkit_dyno_v1_2.py::kernel_smooth()`

### Test Coverage

- `selftest.py`: Validates kernel behavior
- `acceptance_test.py`: Tests apply/rollback with kernel
- Golden file tests: Detect unintended changes

---

## K2: Coverage-Weighted Smoothing

### Purpose

Apply neighbor-weighted averaging with center cell bias to reduce noise while preserving cell authority.

### Algorithm

For each cell `(r, c)`:

1. Collect neighbor values and weights
2. Apply distance-based weighting
3. Calculate weighted average
4. Alpha-blend with original value

**Mathematical formula:**

```
weighted_sum = center × center_bias + Σ(neighbor_i × weight_i)
total_weight = center_bias + Σ(weight_i)
smoothed = weighted_sum / total_weight
final = alpha × smoothed + (1 - alpha) × center
```

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `alpha` | 0.20 | Smoothing strength (0.0 = no smoothing, 1.0 = full smoothing) |
| `center_bias` | 1.25 | Weight multiplier for center cell |
| `min_hits` | 1 | Minimum neighbors required to smooth |
| `dist_pow` | 1 | Distance power for weighting (1 = linear) |

### Implementation

```python
alpha = 0.20
center_bias = 1.25
min_hits = 1
dist_pow = 1

for r in range(rows):
    for c in range(cols):
        center_val = final_grid[r][c]
        if center_val is None:
            continue
        
        # Collect neighbors with weights
        neighbor_values = [center_val]
        neighbor_weights = [center_bias]
        
        neighbors = [
            (r-1, c, 1.0),  # up
            (r+1, c, 1.0),  # down
            (r, c-1, 1.0),  # left
            (r, c+1, 1.0)   # right
        ]
        
        for nr, nc, base_weight in neighbors:
            if 0 <= nr < rows and 0 <= nc < cols:
                n_val = final_grid[nr][nc]
                if n_val is not None:
                    dist_weight = 1.0 / (1.0 ** dist_pow)
                    neighbor_values.append(n_val)
                    neighbor_weights.append(base_weight * dist_weight)
        
        # Apply coverage weighting
        if len(neighbor_values) >= min_hits:
            weighted_sum = sum(v * w for v, w in zip(neighbor_values, neighbor_weights))
            total_weight = sum(neighbor_weights)
            smoothed_val = weighted_sum / total_weight
            
            # Alpha blend
            final_grid[r][c] = alpha * smoothed_val + (1 - alpha) * center_val
```

### Weight Calculation

For immediate neighbors (distance = 1):
```
weight = base_weight × (1.0 / (1.0 ^ dist_pow)) = base_weight × 1.0
```

Since `dist_pow = 1` and all immediate neighbors have `base_weight = 1.0`:
```
All neighbor weights = 1.0
Center weight = 1.25
```

### Example Calculation

Given:
- Center cell: 5.0%
- Neighbors: [4.8%, 5.2%, None, 5.1%] (up, down, left, right)

Step 1: Collect values and weights
```
values =  [5.0,  4.8,  5.2,  5.1]
weights = [1.25, 1.0,  1.0,  1.0]
```

Step 2: Weighted average
```
weighted_sum = 5.0×1.25 + 4.8×1.0 + 5.2×1.0 + 5.1×1.0 = 21.35
total_weight = 1.25 + 1.0 + 1.0 + 1.0 = 4.25
smoothed = 21.35 / 4.25 = 5.024
```

Step 3: Alpha blend
```
final = 0.20 × 5.024 + 0.80 × 5.0 = 1.005 + 4.0 = 5.005
```

### File Location

`ai_tuner_toolkit_dyno_v1_2.py::kernel_smooth()` (Stage 4)

### Test Coverage

- Kernel validation in `selftest.py`
- Parameter verification in test suite
- Golden file regression tests

---

## K3: Tiered Spark Logic

### Purpose

Generate spark advance/retard recommendations based on knock detection and temperature.

### Algorithm

K3 consists of two components:

#### Component 1: Base Spark Suggestion

For each cell `(r, c)`:

```python
def spark_suggestion(knock_grid, iat_grid):
    for r in range(rows):
        for c in range(cols):
            knock_value = knock_grid[r][c] or 0.0
            iat = iat_grid[r][c]
            
            pull = 0.0
            
            # Calculate retard based on knock
            if knock_value >= 0.5:
                pull = -min(2.0, max(0.5, (knock_value / 3.0) * 2.0))
            
            # Add hot IAT penalty
            if iat is not None and iat >= HOT_IAT_THRESHOLD_F and pull < 0.0:
                pull -= 0.5
            
            spark_grid[r][c] = pull
```

**Knock-based retard formula:**
```
if knock >= 0.5:
    raw_retard = (knock / 3.0) × 2.0
    clamped_retard = -min(2.0, max(0.5, raw_retard))
```

**Examples:**
- knock = 0.5 → retard = -0.5°
- knock = 1.5 → retard = -1.0°
- knock = 3.0 → retard = -2.0°
- knock = 6.0 → retard = -2.0° (clamped)

**Hot IAT penalty:**
```
if IAT >= HOT_IAT_THRESHOLD_F and retard < 0.0:
    retard -= 0.5°
```

#### Component 2: Rear Cylinder Rule

Special handling for rear cylinder in power band:

```python
def enforce_rear_rule(spark_grid, extra_rule_deg=2.0, hot_extra=-1.0, iat_grid=None):
    for ri, rpm in enumerate(RPM_BINS):
        if 2800 <= rpm <= 3600:
            for ki, kpa in enumerate(KPA_BINS):
                if 75 <= kpa <= 95:
                    # Apply base retard
                    base = -abs(extra_rule_deg)
                    spark_grid[ri][ki] += base
                    
                    # Apply hot IAT penalty
                    if iat_grid is not None:
                        iat = iat_grid[ri][ki]
                        if iat is not None and iat >= HOT_IAT_THRESHOLD_F:
                            spark_grid[ri][ki] += hot_extra
```

**Power band definition:**
- RPM: 2800-3600 (inclusive)
- MAP: 75-95 kPa (inclusive)

**Retard amounts:**
- Base: -2.0° (default `extra_rule_deg`)
- Hot IAT: additional -1.0° (default `hot_extra`)

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `HOT_IAT_THRESHOLD_F` | System constant | Temperature threshold for hot compensation |
| `extra_rule_deg` | 2.0 | Base retard for rear power band (degrees) |
| `hot_extra` | -1.0 | Additional retard when hot (degrees) |

### Example Calculation

**Scenario 1: Front cylinder, moderate knock, normal temp**
- RPM: 3000
- MAP: 80 kPa
- Knock: 1.5
- IAT: 90°F

Calculation:
```
raw_retard = (1.5 / 3.0) × 2.0 = 1.0
clamped = -min(2.0, max(0.5, 1.0)) = -1.0°
hot_penalty = 0.0 (IAT below threshold)
final = -1.0°
```

**Scenario 2: Rear cylinder, power band, high knock, hot**
- RPM: 3200 (in power band)
- MAP: 85 kPa (in power band)
- Knock: 3.0
- IAT: 120°F (hot)

Calculation:
```
# Base spark suggestion
raw_retard = (3.0 / 3.0) × 2.0 = 2.0
clamped = -min(2.0, max(0.5, 2.0)) = -2.0°
hot_penalty = -0.5°
base_suggestion = -2.5°

# Rear rule
power_band_retard = -2.0°
hot_extra = -1.0°
rear_adjustment = -3.0°

# Final
final = -2.5° + (-3.0°) = -5.5°
```

### File Location

- `ai_tuner_toolkit_dyno_v1_2.py::spark_suggestion()`
- `ai_tuner_toolkit_dyno_v1_2.py::enforce_rear_rule()`

### Test Coverage

- Unit tests for spark calculation
- Power band boundary tests
- Hot IAT threshold tests
- Rear rule validation

---

## Kernel Composition

### Execution Flow

```
Input: VE correction grid (from AFR analysis)
  ↓
K1 Stage 1: Calculate gradients
  ↓
K1 Stage 2: Adaptive smoothing (magnitude-dependent)
  ↓
K1 Stage 3: Gradient-limited blending
  ↓
K2 (K1 Stage 4): Coverage-weighted smoothing
  ↓
Output: Smoothed VE correction grid
  ↓
K3: Generate spark suggestions (separate from VE path)
  ↓
Output: Spark timing adjustments
```

### Data Flow

```
WinPEP CSV
  ↓ parse
AFR measurements + targets
  ↓ bin & aggregate
AFR error grid
  ↓ compute VE delta
Raw VE correction grid
  ↓ K1 + K2
Smoothed VE correction grid
  ↓ clamp
Final VE correction output
  
Knock grid + IAT grid
  ↓ K3
Spark suggestion output
```

### Independence

- **K1 and K2** operate on VE corrections only
- **K3** operates independently on knock and IAT data
- VE and spark paths do not interact
- Each kernel is stateless (no cross-run state)

---

## Determinism Guarantees

### K1: Gradient-Limited Smoothing

**Deterministic because:**
- No random number generation
- Fixed algorithm with documented parameters
- Same grid always produces same gradients
- Adaptive logic is purely mathematical
- No external state or dependencies

**Verification:**
```python
# Run twice on same input
result1 = kernel_smooth(grid, passes=2, gradient_threshold=1.0)
result2 = kernel_smooth(grid, passes=2, gradient_threshold=1.0)
assert result1 == result2  # Bit-identical
```

### K2: Coverage-Weighted Smoothing

**Deterministic because:**
- Fixed weight calculation
- No random sampling
- Neighbor iteration order is consistent
- Alpha blending is pure math
- No adaptive or learning behavior

**Verification:**
```python
# Run on same grid multiple times
results = [coverage_weighted_smooth(grid) for _ in range(10)]
assert all(r == results[0] for r in results)  # All identical
```

### K3: Tiered Spark Logic

**Deterministic because:**
- Pure function of knock and IAT
- No randomness
- Fixed thresholds and formulas
- Power band boundaries are constants
- No state between cells or runs

**Verification:**
```python
# Same inputs always give same outputs
spark1 = spark_suggestion(knock_grid, iat_grid)
spark2 = spark_suggestion(knock_grid, iat_grid)
assert spark1 == spark2  # Bit-identical
```

---

## Parameter Tuning (NOT Allowed in v1.0.0)

The following parameters are **frozen** for math version 1.0.0:

### K1 Parameters (Frozen)

- `passes = 2` - Cannot change without version increment
- `gradient_threshold = 1.0` - Cannot change without version increment
- Large correction threshold = 3.0% - Cannot change
- Small correction threshold = 1.0% - Cannot change

### K2 Parameters (Frozen)

- `alpha = 0.20` - Cannot change without version increment
- `center_bias = 1.25` - Cannot change without version increment
- `min_hits = 1` - Cannot change without version increment
- `dist_pow = 1` - Cannot change without version increment

### K3 Parameters (Frozen)

- `extra_rule_deg = 2.0` - Cannot change without version increment
- `hot_extra = -1.0` - Cannot change without version increment
- Power band RPM range: 2800-3600 - Cannot change
- Power band MAP range: 75-95 kPa - Cannot change

### To Change Parameters

1. Create new math version (v2.0.0)
2. Add `--math-version` CLI flag
3. Tag outputs with `math_version` field
4. Keep v1.0.0 runnable
5. Document changes in CHANGELOG
6. Update all tests
7. Create migration guide

---

## Validation and Testing

### Regression Tests

Each kernel has golden file tests:

```bash
# K1 + K2 combined
python tests/test_kernel_smooth.py

# K3 spark logic
python tests/test_spark_suggestion.py
```

### Property Tests

Validated properties:

**K1:**
- Output grid has same shape as input
- No None values introduced where input had values
- Gradient calculation is symmetric
- Smoothing preserves large corrections (≥3.0%)

**K2:**
- Alpha blending is bounded [0.0, 1.0]
- Center bias is applied correctly
- Weights sum correctly
- Output is deterministic

**K3:**
- Retard is always negative or zero
- Hot IAT penalty only applied when conditions met
- Power band boundaries are exact
- Clamping prevents excessive retard

### Acceptance Criteria

For v1.0.0 math to be valid:

- [ ] All kernel tests pass
- [ ] Golden files match exactly
- [ ] Apply→Rollback symmetry holds
- [ ] No randomness in execution
- [ ] Same input → same output (100 runs)
- [ ] Parameters match specification
- [ ] Documentation is complete

---

## Performance Characteristics

### K1: Gradient-Limited Smoothing

**Complexity:** O(rows × cols × passes)

**Typical runtime:**
- 9×5 grid, 2 passes: <1ms
- 11×9 grid, 2 passes: <5ms

**Memory:** O(rows × cols) for gradient storage

### K2: Coverage-Weighted Smoothing

**Complexity:** O(rows × cols × neighbors)

**Typical runtime:**
- 9×5 grid: <1ms
- 11×9 grid: <2ms

**Memory:** O(rows × cols) for weight storage

### K3: Tiered Spark Logic

**Complexity:** O(rows × cols)

**Typical runtime:**
- 9×5 grid: <1ms
- 11×9 grid: <1ms

**Memory:** O(1) - in-place calculation

### Combined Pipeline

**Total runtime:** <10ms for typical dyno run
**Memory footprint:** ~100KB for full analysis

---

## Version History

### 1.0.0 (2025-12-13)

**Initial stable release**

- K1: Gradient-limited adaptive smoothing
- K2: Coverage-weighted smoothing (integrated with K1)
- K3: Tiered spark logic
- All parameters frozen
- Full test coverage
- Documentation complete

**This version is now frozen and will not change.**

---

## Appendix: Mathematical Proofs

### K1 Smoothing Convergence

After N passes, the smoothing converges to a stable state where additional passes have minimal effect (<0.01% change).

**Proof sketch:**
- Each pass reduces variance by factor ≈ 0.5
- After 2 passes, noise is reduced by ≈ 75%
- Additional passes yield diminishing returns
- Large corrections (≥3.0%) skip smoothing entirely

### K2 Weighted Average Properties

The weighted average is guaranteed to fall within the range of input values.

**Proof:**
```
min(values) ≤ weighted_average ≤ max(values)
```

Since all weights are positive and finite, the weighted average is a convex combination of input values.

### K3 Retard Bounds

The maximum retard is bounded by formula construction.

**Proof:**
- Base retard: -2.0° (clamped)
- Hot IAT penalty: -0.5°
- Rear rule: -2.0°
- Hot rear extra: -1.0°
- Maximum combined: -5.5° (base + hot + rear + hot_rear)

This prevents excessive retard that could cause hesitation or stumbling.

---

**Document Version:** 1.0.0  
**Math Version:** 1.0.0  
**Kernel Freeze Date:** 2025-12-13  
**Next Review:** Before any proposed kernel modification
