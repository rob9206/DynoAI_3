# Implementation Specification: Per-Cylinder Auto-Balancing

_Version: 1.0 | Status: Draft | Last Updated: 2025-12-06_

## Executive Summary

This specification defines an algorithm for automatically balancing VE tables between front and rear cylinders on Harley-Davidson V-twin engines. The feature eliminates the current manual process of sensor swapping and duplicate calibration, reducing per-cylinder tuning time from 2+ hours to minutes.

---

## Problem Statement

### Current Pain Point
Professional tuners report that per-cylinder optimization doubles calibration time because:
1. Wideband sensors must be physically moved between exhaust pipes
2. Separate dyno runs are required for each cylinder
3. Independent VE table adjustments must be made manually
4. No existing tool automates the balancing process

### Documented Evidence
- AFR differences of **0.5-1.0 points** between front and rear cylinders are common even with identical VE values
- Temperature differentials: rear cylinder runs **50-100°F hotter** than front
- Uneven firing intervals (315°/405° on Twin Cams) cause front cylinder to draw more air from shared plenum
- Forum consensus: "The only way to do that is with a realtime AFR gauge and you need to do each cylinder separately"

### Target Outcome
Automatically generate balanced VE corrections for both cylinders from a single dyno session with dual-wideband logging.

---

## Technical Approach

### Algorithm Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 Per-Cylinder Auto-Balancing                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: WinPEP CSV with dual AFR columns                        │
│         (afr_meas_f, afr_meas_r, afr_cmd_f, afr_cmd_r)         │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐                         │
│  │ Front Cyl    │     │ Rear Cyl     │                         │
│  │ AFR Binning  │     │ AFR Binning  │                         │
│  └──────┬───────┘     └──────┬───────┘                         │
│         │                    │                                   │
│         ▼                    ▼                                   │
│  ┌──────────────┐     ┌──────────────┐                         │
│  │ VE Error     │     │ VE Error     │                         │
│  │ Calculation  │     │ Calculation  │                         │
│  └──────┬───────┘     └──────┬───────┘                         │
│         │                    │                                   │
│         └────────┬───────────┘                                   │
│                  ▼                                               │
│         ┌──────────────────┐                                    │
│         │ Cross-Cylinder   │                                    │
│         │ Correlation      │                                    │
│         └────────┬─────────┘                                    │
│                  │                                               │
│         ┌────────┴─────────┐                                    │
│         ▼                  ▼                                     │
│  ┌─────────────┐    ┌─────────────┐                            │
│  │ VE Delta    │    │ VE Delta    │                            │
│  │ Front.csv   │    │ Rear.csv    │                            │
│  └─────────────┘    └─────────────┘                            │
│                                                                  │
│  Output: Balanced, independent corrections per cylinder          │
│          + Cylinder Balance Report                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Formula

**VE Error per cylinder:**
```python
ve_error_front = (afr_measured_front / afr_commanded_front) - 1.0
ve_error_rear = (afr_measured_rear / afr_commanded_rear) - 1.0
```

**Balance differential:**
```python
balance_diff = ve_error_front - ve_error_rear  # Positive = front running leaner
```

**Correction application:**
```python
# Standard VE correction
ve_correction_front = 1.0 + ve_error_front
ve_correction_rear = 1.0 + ve_error_rear

# With balance weighting (optional)
balance_weight = config.get('balance_weight', 0.5)  # 0.0-1.0
ve_correction_front *= (1.0 + balance_diff * balance_weight * 0.5)
ve_correction_rear *= (1.0 - balance_diff * balance_weight * 0.5)
```

---

## Data Requirements

### Input CSV Columns (Required)

| Column | Description | Example |
|--------|-------------|---------|
| `rpm` | Engine speed | 3500 |
| `map_kpa` | Manifold pressure | 75 |
| `afr_cmd_f` | Commanded AFR, front cylinder | 13.2 |
| `afr_cmd_r` | Commanded AFR, rear cylinder | 13.2 |
| `afr_meas_f` | Measured AFR, front cylinder | 13.8 |
| `afr_meas_r` | Measured AFR, rear cylinder | 13.5 |

### Input CSV Columns (Optional but Recommended)

| Column | Description | Use |
|--------|-------------|-----|
| `cht_f` | Cylinder head temp, front | Temperature compensation |
| `cht_r` | Cylinder head temp, rear | Temperature compensation |
| `iat` | Intake air temperature | Density correction |
| `ve_f` | Current VE value, front | Absolute output calculation |
| `ve_r` | Current VE value, rear | Absolute output calculation |

### Dual-Wideband Sensor Requirement

**Hardware Configuration:**
- Two wideband O2 sensors required (one per exhaust pipe)
- Supported controllers: Innovate MTX-L, AEM X-Series, PLX DM-6
- WinPEP must be configured to log both channels simultaneously

**Single-Wideband Fallback:**
If only one AFR column present, fall back to existing behavior with warning:
```
WARNING: Single-cylinder AFR data detected. Per-cylinder balancing disabled.
         For best results, use dual-wideband setup.
```

---

## Algorithm Implementation

### Phase 1: Independent Binning

Each cylinder's data is binned independently into the RPM/kPa grid:

```python
def bin_cylinder_data(df: pd.DataFrame, cylinder: str) -> dict:
    """
    Bin AFR measurements for a single cylinder.
    
    Args:
        df: DataFrame with logged data
        cylinder: 'front' or 'rear'
    
    Returns:
        Dict with binned AFR errors and hit counts per grid cell
    """
    afr_cmd_col = f'afr_cmd_{cylinder[0]}'  # afr_cmd_f or afr_cmd_r
    afr_meas_col = f'afr_meas_{cylinder[0]}'
    
    bins = {}
    for rpm_bin in RPM_BINS:
        for kpa_bin in KPA_BINS:
            mask = (
                (df['rpm'] >= rpm_bin - RPM_BIN_WIDTH/2) &
                (df['rpm'] < rpm_bin + RPM_BIN_WIDTH/2) &
                (df['map_kpa'] >= kpa_bin - KPA_BIN_WIDTH/2) &
                (df['map_kpa'] < kpa_bin + KPA_BIN_WIDTH/2)
            )
            cell_data = df[mask]
            if len(cell_data) > 0:
                afr_cmd = cell_data[afr_cmd_col].mean()
                afr_meas = cell_data[afr_meas_col].mean()
                ve_error = (afr_meas / afr_cmd) - 1.0
                bins[(rpm_bin, kpa_bin)] = {
                    'error': ve_error,
                    'hits': len(cell_data),
                    'afr_cmd': afr_cmd,
                    'afr_meas': afr_meas
                }
    return bins
```

### Phase 2: Cross-Cylinder Correlation Analysis

Identify systematic differences between cylinders:

```python
def analyze_cylinder_balance(front_bins: dict, rear_bins: dict) -> dict:
    """
    Analyze balance between front and rear cylinder VE requirements.
    
    Returns:
        Dict with balance metrics and recommendations
    """
    balance_report = {
        'avg_front_error': 0.0,
        'avg_rear_error': 0.0,
        'avg_balance_diff': 0.0,
        'max_imbalance_cell': None,
        'imbalanced_regions': [],
        'recommendations': []
    }
    
    common_cells = set(front_bins.keys()) & set(rear_bins.keys())
    
    if not common_cells:
        balance_report['warnings'] = ['No overlapping data between cylinders']
        return balance_report
    
    diffs = []
    for cell in common_cells:
        front_err = front_bins[cell]['error']
        rear_err = rear_bins[cell]['error']
        diff = front_err - rear_err
        diffs.append({
            'cell': cell,
            'front_error': front_err,
            'rear_error': rear_err,
            'diff': diff,
            'hits': min(front_bins[cell]['hits'], rear_bins[cell]['hits'])
        })
    
    # Weighted average by hit count
    total_hits = sum(d['hits'] for d in diffs)
    balance_report['avg_balance_diff'] = sum(
        d['diff'] * d['hits'] for d in diffs
    ) / total_hits
    
    # Identify imbalanced regions (>0.5% difference)
    IMBALANCE_THRESHOLD = 0.005  # 0.5%
    for d in diffs:
        if abs(d['diff']) > IMBALANCE_THRESHOLD:
            balance_report['imbalanced_regions'].append(d)
    
    # Find worst imbalance
    if diffs:
        worst = max(diffs, key=lambda x: abs(x['diff']))
        balance_report['max_imbalance_cell'] = worst
    
    # Generate recommendations
    if abs(balance_report['avg_balance_diff']) > 0.01:  # >1% systematic difference
        if balance_report['avg_balance_diff'] > 0:
            balance_report['recommendations'].append(
                'Front cylinder running systematically lean. '
                'Check: front exhaust leak, injector flow, intake seal.'
            )
        else:
            balance_report['recommendations'].append(
                'Rear cylinder running systematically lean. '
                'Check: rear exhaust leak, heat-related injector issues.'
            )
    
    return balance_report
```

### Phase 3: Balanced VE Correction Generation

```python
def generate_balanced_corrections(
    front_bins: dict,
    rear_bins: dict,
    balance_report: dict,
    config: dict
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate balanced VE correction tables for both cylinders.
    
    Args:
        front_bins: Binned front cylinder data
        rear_bins: Binned rear cylinder data
        balance_report: Cross-cylinder analysis
        config: Configuration dict with clamping limits, etc.
    
    Returns:
        Tuple of (front_ve_delta, rear_ve_delta) as numpy arrays
    """
    clamp_pct = config.get('clamp_pct', 7.0) / 100.0
    
    front_delta = np.zeros((len(RPM_BINS), len(KPA_BINS)))
    rear_delta = np.zeros((len(RPM_BINS), len(KPA_BINS)))
    
    for i, rpm in enumerate(RPM_BINS):
        for j, kpa in enumerate(KPA_BINS):
            cell = (rpm, kpa)
            
            # Front cylinder correction
            if cell in front_bins:
                front_delta[i, j] = front_bins[cell]['error']
            
            # Rear cylinder correction
            if cell in rear_bins:
                rear_delta[i, j] = rear_bins[cell]['error']
    
    # Apply clamping (safety limit)
    front_delta = np.clip(front_delta, -clamp_pct, clamp_pct)
    rear_delta = np.clip(rear_delta, -clamp_pct, clamp_pct)
    
    return front_delta, rear_delta
```

---

## Output Files

### Primary Outputs

| File | Description |
|------|-------------|
| `VE_Correction_Delta_Front.csv` | Front cylinder VE corrections |
| `VE_Correction_Delta_Rear.csv` | Rear cylinder VE corrections |
| `Cylinder_Balance_Report.json` | Balance analysis and recommendations |
| `manifest.json` | Extended with `per_cylinder_balance` section |

### Cylinder Balance Report Schema

```json
{
  "version": "1.0",
  "generated_at": "2025-12-06T14:30:00Z",
  "input_file": "dyno_log_20251206.csv",
  "summary": {
    "front_cylinder": {
      "avg_ve_error_pct": -2.3,
      "bins_covered": 45,
      "total_hits": 1250
    },
    "rear_cylinder": {
      "avg_ve_error_pct": -1.8,
      "bins_covered": 42,
      "total_hits": 1180
    },
    "balance": {
      "avg_difference_pct": -0.5,
      "max_imbalance_pct": 1.2,
      "max_imbalance_cell": {"rpm": 3500, "kpa": 80},
      "imbalanced_region_count": 8
    }
  },
  "imbalanced_regions": [
    {
      "rpm_range": [3000, 4000],
      "kpa_range": [70, 90],
      "avg_imbalance_pct": 0.8,
      "likely_cause": "Rear cylinder heat soak at moderate load"
    }
  ],
  "recommendations": [
    "Front cylinder requires 0.5% more fuel on average than rear",
    "Consider checking front exhaust gasket seal",
    "Rear cylinder efficiency higher, likely due to cooling differential"
  ],
  "temperature_correlation": {
    "enabled": true,
    "front_avg_cht_f": 265,
    "rear_avg_cht_f": 325,
    "temp_diff_impact": "Rear running hotter by 60°F, contributing to balance difference"
  }
}
```

---

## CLI Interface

### New Flags

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv dyno_log.csv \
  --outdir ./output \
  --per-cylinder                    # Enable per-cylinder mode (auto-detect dual AFR)
  --per-cylinder-balance-weight 0.5 # Cross-cylinder balance weighting (0.0-1.0)
  --per-cylinder-report             # Generate detailed balance report
```

### Backward Compatibility

- If `--per-cylinder` not specified and dual AFR columns present: warn and use averaged values
- If `--per-cylinder` specified but single AFR column: error with helpful message
- Existing single-cylinder workflows unchanged

---

## Integration Points

### With Existing Core Engine

```python
# In ai_tuner_toolkit_dyno_v1_2.py main()

if args.per_cylinder:
    # Validate dual-AFR data present
    validate_dual_afr_columns(df)
    
    # Run independent binning
    front_bins = bin_cylinder_data(df, 'front')
    rear_bins = bin_cylinder_data(df, 'rear')
    
    # Analyze balance
    balance_report = analyze_cylinder_balance(front_bins, rear_bins)
    
    # Generate corrections
    front_delta, rear_delta = generate_balanced_corrections(
        front_bins, rear_bins, balance_report, config
    )
    
    # Apply smoothing (existing kernel)
    front_delta = kernel_smooth(front_delta, passes=args.smooth_passes)
    rear_delta = kernel_smooth(rear_delta, passes=args.smooth_passes)
    
    # Write outputs
    write_ve_delta(front_delta, outdir / 'VE_Correction_Delta_Front.csv')
    write_ve_delta(rear_delta, outdir / 'VE_Correction_Delta_Rear.csv')
    write_balance_report(balance_report, outdir / 'Cylinder_Balance_Report.json')
else:
    # Existing single-table logic
    ...
```

### With VE Operations

Existing `VEApply` works unchanged—user applies front and rear corrections separately:

```bash
# Apply front cylinder corrections
python ve_operations.py apply \
  --base tables/VE_Base_Front.csv \
  --factor output/VE_Correction_Delta_Front.csv \
  --output tables/VE_Updated_Front.csv

# Apply rear cylinder corrections  
python ve_operations.py apply \
  --base tables/VE_Base_Rear.csv \
  --factor output/VE_Correction_Delta_Rear.csv \
  --output tables/VE_Updated_Rear.csv
```

---

## Safety Considerations

### Clamping Rules
- Per-cylinder corrections subject to same ±7% default clamp
- Cross-cylinder differential limited to ±3% (configurable)
  - Rationale: >3% difference likely indicates hardware issue, not tuning need

### Validation Checks
1. **Hit count parity**: Warn if one cylinder has <50% of other's hits
2. **Coverage overlap**: Require >70% grid overlap between cylinders
3. **Systematic bias detection**: Flag if one cylinder consistently lean/rich across all bins
4. **Temperature correlation**: Warn if balance correlates strongly with CHT differential

### Warning Thresholds

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Cylinder hit imbalance | >50% difference | Warning in report |
| Systematic lean bias | >2% one cylinder | Recommendation to check hardware |
| Max cell imbalance | >3% | Capped at ±3%, flagged for manual review |
| No overlap data | <10 common cells | Error, require more data |

---

## Testing Requirements

### Unit Tests

```python
# tests/unit/test_per_cylinder_balance.py

def test_bin_cylinder_data_front():
    """Front cylinder binning produces correct grid."""
    
def test_bin_cylinder_data_rear():
    """Rear cylinder binning produces correct grid."""
    
def test_analyze_balance_symmetric():
    """Balanced cylinders produce ~0 differential."""
    
def test_analyze_balance_front_lean():
    """Front-lean condition detected and reported."""
    
def test_clamp_cross_cylinder_differential():
    """Cross-cylinder diff limited to ±3%."""
    
def test_missing_afr_column_error():
    """Missing dual AFR columns raises clear error."""
```

### Integration Tests

```python
# tests/integration/test_per_cylinder_pipeline.py

def test_dual_afr_csv_processing():
    """Full pipeline with dual-AFR CSV produces two delta files."""
    
def test_balance_report_generated():
    """Balance report JSON created with correct schema."""
    
def test_backward_compat_single_afr():
    """Single-AFR CSV still works without --per-cylinder flag."""
```

### Acceptance Criteria

| Test | Expected Result |
|------|-----------------|
| Dual-AFR CSV with --per-cylinder | Two VE delta files + balance report |
| Single-AFR CSV with --per-cylinder | Error message, no output |
| Dual-AFR CSV without flag | Warning, averaged single output |
| Extreme imbalance (>5%) | Clamped, flagged in report |

---

## Implementation Phases

### Phase 1: Core Algorithm (Week 1-2)
- [ ] Implement `bin_cylinder_data()` function
- [ ] Implement `analyze_cylinder_balance()` function
- [ ] Implement `generate_balanced_corrections()` function
- [ ] Add CLI flags and validation

### Phase 2: Integration (Week 2-3)
- [ ] Integrate with existing smoothing kernels
- [ ] Extend manifest.json schema
- [ ] Create balance report JSON output
- [ ] Update diagnostics report format

### Phase 3: Testing & Documentation (Week 3-4)
- [ ] Write unit tests (target: 90% coverage)
- [ ] Write integration tests
- [ ] Update user documentation
- [ ] Create example dual-AFR CSV for testing

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time saved per tune | 1-2 hours (vs manual sensor swap) |
| Balance detection accuracy | >90% of hardware issues flagged |
| User adoption | >50% of dual-wideband users within 6 months |
| False positive rate | <5% incorrect imbalance warnings |

---

## References

- [VTWIN_TUNING_TECHNICAL_VALIDATION.md](VTWIN_TUNING_TECHNICAL_VALIDATION.md) - Source research
- [DYNOAI_SAFETY_RULES.md](DYNOAI_SAFETY_RULES.md) - Clamping and safety limits
- [ROADMAP.md](ROADMAP.md) - Feature roadmap context

