# Implementation Specification: Decel Fuel Management

_Version: 1.0 | Status: Draft | Last Updated: 2025-12-06_

## Executive Summary

This specification defines an automated system for eliminating deceleration popping (afterfire) in Harley-Davidson V-twin engines. The feature addresses a universal complaint among tuners: decel popping cannot be autotuned out by any current platform and requires tedious manual table editing. DynoAI will automatically detect decel events, calculate optimal fuel enrichment, and generate ready-to-apply corrections.

---

## Problem Statement

### Current Pain Point
Deceleration backfire (popping/afterfire) is one of the most common complaints from Harley owners and tuners:
- **Every tuning platform fails here**: "decel popping cannot be autotuned out in Power Vision"
- **Manual process is tedious**: Users must "go into the 0% column and alter the fuel curve from 1750-5500rpm"
- **Tradeoff is poorly understood**: "Getting rid of the noise means de-tuning your motor"—slight richening required

### Root Cause
Fuel burning in the exhaust manifold when:
1. Throttle closes rapidly (deceleration)
2. Unburned fuel/air mixture exits combustion chamber
3. Mixture contacts hot exhaust components
4. Oxygen present (especially with PAIR valve air injection)
5. Mixture ignites in exhaust → audible pop

### Technical Background
- Occurs at **0-5% throttle position** during deceleration
- Most common in **1750-5500 RPM** range
- Worse with:
  - Aftermarket exhaust (hotter, thinner walls)
  - High-flow air cleaners (more air in mixture)
  - PAIR valve still connected (adds oxygen)
  - Lean base tune (EPA compliance maps)

### Target Outcome
Automatically generate decel fuel enrichment corrections that eliminate popping while minimizing efficiency loss.

---

## Technical Approach

### Algorithm Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Decel Fuel Management                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: WinPEP CSV with TPS and RPM data                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Phase 1: Decel Event Detection                            │  │
│  │  - Identify throttle closure rate > threshold             │  │
│  │  - Mark RPM/TPS zones where decel occurs                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Phase 2: AFR Analysis During Decel                        │  │
│  │  - Measure AFR excursions during decel events             │  │
│  │  - Identify lean spikes correlated with popping           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Phase 3: Enrichment Calculation                           │  │
│  │  - Calculate fuel addition needed to prevent lean spike   │  │
│  │  - Apply graduated enrichment based on decel severity     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Phase 4: VE Overlay Generation                            │  │
│  │  - Generate closed-throttle VE corrections                │  │
│  │  - Target 0-7% TPS, 1500-5500 RPM zone                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Output: Decel_Fuel_Overlay.csv                                 │
│          Decel_Analysis_Report.json                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Decel Event Detection

A decel event is defined as:
```python
DECEL_EVENT_CRITERIA = {
    'tps_rate': -15.0,        # TPS change rate (% per second), negative = closing
    'tps_max': 7.0,           # Maximum TPS at end of event (%)
    'rpm_min': 1500,          # Minimum RPM for decel event
    'rpm_max': 5500,          # Maximum RPM for decel event
    'duration_min_ms': 200,   # Minimum event duration (ms)
    'duration_max_ms': 3000,  # Maximum event duration (ms)
}
```

### Enrichment Strategy

Based on industry research, the optimal decel enrichment follows this pattern:

| RPM Range | TPS Range | Base Enrichment | Rationale |
|-----------|-----------|-----------------|-----------|
| 1500-2500 | 0-2% | +20-25% | Lowest airflow, highest pop risk |
| 1500-2500 | 2-5% | +15-20% | Transitional zone |
| 2500-3500 | 0-2% | +15-20% | Moderate airflow |
| 2500-3500 | 2-5% | +10-15% | Transitional zone |
| 3500-4500 | 0-2% | +10-15% | Higher airflow, less enrichment needed |
| 3500-4500 | 2-5% | +8-12% | Transitional zone |
| 4500-5500 | 0-2% | +8-12% | Highest airflow during decel |
| 4500-5500 | 2-5% | +5-10% | Minimal enrichment needed |

---

## Data Requirements

### Input CSV Columns (Required)

| Column | Description | Example |
|--------|-------------|---------|
| `rpm` | Engine speed | 3500 |
| `tps` | Throttle position (%) | 2.5 |
| `timestamp` or sample rate | Time reference | 0.010 (10ms) |

### Input CSV Columns (Recommended)

| Column | Description | Use |
|--------|-------------|-----|
| `afr_meas_f` | Measured AFR front | Detect lean spikes |
| `afr_meas_r` | Measured AFR rear | Detect lean spikes |
| `map_kpa` | Manifold pressure | Confirm closed throttle |
| `egt_f` / `egt_r` | Exhaust gas temps | Correlate with popping |

### Decel Event Log Format

If user has audio/video noting pop events, optional input:
```json
{
  "decel_events": [
    {"timestamp_ms": 45230, "severity": "loud", "rpm_approx": 3200},
    {"timestamp_ms": 67890, "severity": "moderate", "rpm_approx": 2800}
  ]
}
```

---

## Algorithm Implementation

### Phase 1: Decel Event Detection

```python
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

@dataclass
class DecelEvent:
    """Represents a detected deceleration event."""
    start_idx: int
    end_idx: int
    start_rpm: float
    end_rpm: float
    start_tps: float
    end_tps: float
    tps_rate: float  # %/second
    duration_ms: float
    afr_min: float = None  # Leanest AFR during event
    afr_max: float = None  # Richest AFR during event
    pop_likelihood: float = 0.0  # 0.0-1.0 score

def detect_decel_events(
    df,
    sample_rate_ms: float = 10.0,
    config: dict = None
) -> List[DecelEvent]:
    """
    Detect deceleration events from logged data.
    
    Args:
        df: DataFrame with rpm, tps columns
        sample_rate_ms: Time between samples in milliseconds
        config: Optional config overrides
    
    Returns:
        List of detected DecelEvent objects
    """
    config = config or DECEL_EVENT_CRITERIA
    
    # Calculate TPS rate of change
    tps = df['tps'].values
    tps_rate = np.gradient(tps) / (sample_rate_ms / 1000.0)  # %/second
    
    events = []
    in_event = False
    event_start = 0
    
    for i in range(len(df)):
        rpm = df['rpm'].iloc[i]
        tps_val = tps[i]
        rate = tps_rate[i]
        
        # Check if entering decel event
        if not in_event:
            if (rate <= config['tps_rate'] and 
                rpm >= config['rpm_min'] and 
                rpm <= config['rpm_max']):
                in_event = True
                event_start = i
        
        # Check if exiting decel event
        else:
            # Event ends when TPS stabilizes or opens
            if rate > -5.0 or tps_val > config['tps_max']:
                duration_ms = (i - event_start) * sample_rate_ms
                
                if (duration_ms >= config['duration_min_ms'] and 
                    duration_ms <= config['duration_max_ms']):
                    
                    event = DecelEvent(
                        start_idx=event_start,
                        end_idx=i,
                        start_rpm=df['rpm'].iloc[event_start],
                        end_rpm=rpm,
                        start_tps=tps[event_start],
                        end_tps=tps_val,
                        tps_rate=np.mean(tps_rate[event_start:i]),
                        duration_ms=duration_ms
                    )
                    events.append(event)
                
                in_event = False
    
    return events


def analyze_decel_afr(
    df,
    events: List[DecelEvent],
    afr_col: str = 'afr_meas_f'
) -> List[DecelEvent]:
    """
    Analyze AFR behavior during decel events.
    
    Adds afr_min, afr_max, and pop_likelihood to each event.
    """
    for event in events:
        event_data = df.iloc[event.start_idx:event.end_idx]
        
        if afr_col in df.columns:
            afr_values = event_data[afr_col].values
            event.afr_min = np.min(afr_values)
            event.afr_max = np.max(afr_values)
            
            # Calculate pop likelihood based on lean excursion
            # Lean spike > 15.5 AFR is high pop risk
            lean_spike = event.afr_max - 14.7  # Deviation from stoich
            event.pop_likelihood = min(1.0, max(0.0, lean_spike / 2.0))
    
    return events
```

### Phase 2: Enrichment Calculation

```python
def calculate_decel_enrichment(
    events: List[DecelEvent],
    config: dict = None
) -> dict:
    """
    Calculate required enrichment to prevent decel popping.
    
    Returns:
        Dict mapping (rpm_bin, tps_bin) -> enrichment_pct
    """
    # Default enrichment table (baseline before event analysis)
    BASE_ENRICHMENT = {
        # (rpm_min, rpm_max, tps_min, tps_max): enrichment_pct
        (1500, 2500, 0, 2): 0.22,   # +22%
        (1500, 2500, 2, 5): 0.17,   # +17%
        (1500, 2500, 5, 7): 0.10,   # +10%
        (2500, 3500, 0, 2): 0.18,   # +18%
        (2500, 3500, 2, 5): 0.12,   # +12%
        (2500, 3500, 5, 7): 0.08,   # +8%
        (3500, 4500, 0, 2): 0.12,   # +12%
        (3500, 4500, 2, 5): 0.08,   # +8%
        (3500, 4500, 5, 7): 0.05,   # +5%
        (4500, 5500, 0, 2): 0.10,   # +10%
        (4500, 5500, 2, 5): 0.06,   # +6%
        (4500, 5500, 5, 7): 0.04,   # +4%
    }
    
    enrichment_map = {}
    
    # Start with base enrichment
    for zone, base_pct in BASE_ENRICHMENT.items():
        rpm_min, rpm_max, tps_min, tps_max = zone
        enrichment_map[zone] = base_pct
    
    # Adjust based on detected events
    for event in events:
        # Find which zone this event falls into
        for zone in BASE_ENRICHMENT.keys():
            rpm_min, rpm_max, tps_min, tps_max = zone
            
            # Check if event's end point is in this zone
            if (rpm_min <= event.end_rpm < rpm_max and 
                tps_min <= event.end_tps < tps_max):
                
                # Increase enrichment if pop likelihood is high
                if event.pop_likelihood > 0.5:
                    current = enrichment_map[zone]
                    # Add up to 5% more based on pop severity
                    additional = event.pop_likelihood * 0.05
                    enrichment_map[zone] = min(0.30, current + additional)
    
    return enrichment_map
```

### Phase 3: VE Overlay Generation

```python
def generate_decel_ve_overlay(
    enrichment_map: dict,
    rpm_bins: list,
    kpa_bins: list
) -> np.ndarray:
    """
    Generate VE correction overlay for decel fuel management.
    
    Note: Decel occurs at low MAP (high vacuum), typically 20-40 kPa.
    This overlay targets those specific cells.
    
    Args:
        enrichment_map: Dict of zone -> enrichment percentage
        rpm_bins: List of RPM bin centers
        kpa_bins: List of kPa bin centers
    
    Returns:
        2D numpy array of VE correction factors
    """
    # Decel occurs at low MAP values (high vacuum)
    DECEL_KPA_MAX = 45  # Only apply to cells below this kPa
    
    overlay = np.zeros((len(rpm_bins), len(kpa_bins)))
    
    for i, rpm in enumerate(rpm_bins):
        for j, kpa in enumerate(kpa_bins):
            # Only apply enrichment to low-MAP (decel) cells
            if kpa > DECEL_KPA_MAX:
                continue
            
            # Find applicable enrichment zone
            # Map TPS to effective vacuum level
            # Lower kPa = more vacuum = lower effective TPS
            effective_tps = (kpa / DECEL_KPA_MAX) * 7.0  # Scale to 0-7% TPS
            
            for zone, enrichment in enrichment_map.items():
                rpm_min, rpm_max, tps_min, tps_max = zone
                
                if (rpm_min <= rpm < rpm_max and 
                    tps_min <= effective_tps < tps_max):
                    overlay[i, j] = enrichment
                    break
    
    return overlay


def write_decel_overlay(
    overlay: np.ndarray,
    rpm_bins: list,
    kpa_bins: list,
    output_path: str
):
    """
    Write decel VE overlay to CSV in standard format.
    """
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header row: RPM, kPa values
        header = ['RPM'] + [str(kpa) for kpa in kpa_bins]
        writer.writerow(header)
        
        # Data rows
        for i, rpm in enumerate(rpm_bins):
            row = [rpm] + [f'{overlay[i, j]:.4f}' for j in range(len(kpa_bins))]
            writer.writerow(row)
```

---

## Output Files

### Primary Outputs

| File | Description |
|------|-------------|
| `Decel_Fuel_Overlay.csv` | VE enrichment overlay for closed-throttle cells |
| `Decel_Analysis_Report.json` | Detailed analysis with detected events |

### Decel Analysis Report Schema

```json
{
  "version": "1.0",
  "generated_at": "2025-12-06T14:30:00Z",
  "input_file": "dyno_log_20251206.csv",
  "summary": {
    "events_detected": 23,
    "avg_pop_likelihood": 0.42,
    "highest_risk_rpm": 2800,
    "highest_risk_tps": 1.2,
    "total_enrichment_applied": "+15.3% average in decel zone"
  },
  "events": [
    {
      "timestamp_ms": 45230,
      "rpm_range": [3200, 2400],
      "tps_range": [12.0, 1.5],
      "duration_ms": 850,
      "afr_excursion": {"min": 13.8, "max": 16.2},
      "pop_likelihood": 0.75,
      "recommended_enrichment": "+18%"
    }
  ],
  "enrichment_zones": [
    {
      "rpm_range": [1500, 2500],
      "tps_range": [0, 2],
      "base_enrichment_pct": 22,
      "adjusted_enrichment_pct": 25,
      "adjustment_reason": "3 high-likelihood events detected"
    }
  ],
  "recommendations": [
    "Consider PAIR valve removal/block-off for further improvement",
    "Aftermarket exhaust detected - higher enrichment applied",
    "Decel enrichment will slightly increase fuel consumption during engine braking"
  ],
  "tradeoffs": {
    "fuel_economy_impact": "-0.5 to -1.0 MPG estimated during mixed driving",
    "emission_impact": "Slight increase in HC during decel (closed loop mitigates)",
    "driveability_impact": "Smoother decel, reduced exhaust bark"
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
  --decel-management              # Enable decel fuel management
  --decel-severity medium         # low|medium|high (enrichment aggressiveness)
  --decel-rpm-min 1500            # Override minimum RPM for decel zone
  --decel-rpm-max 5500            # Override maximum RPM for decel zone
  --decel-report                  # Generate detailed analysis report
```

### Severity Presets

| Severity | Description | Base Enrichment Multiplier |
|----------|-------------|---------------------------|
| `low` | Minimal enrichment, may still have some popping | 0.7x |
| `medium` | Balanced - eliminates most popping | 1.0x (default) |
| `high` | Aggressive - eliminates all popping, impacts economy | 1.3x |

---

## Integration Points

### With Existing VE Pipeline

The decel overlay is applied **in addition to** standard VE corrections:

```python
# In ai_tuner_toolkit_dyno_v1_2.py main()

# Standard VE correction generation (existing)
ve_delta = generate_ve_corrections(df, config)
ve_delta = kernel_smooth(ve_delta, passes=args.smooth_passes)

if args.decel_management:
    # Detect decel events
    events = detect_decel_events(df, sample_rate_ms=10.0)
    events = analyze_decel_afr(df, events)
    
    # Calculate enrichment
    enrichment_map = calculate_decel_enrichment(events, config)
    
    # Generate overlay
    decel_overlay = generate_decel_ve_overlay(
        enrichment_map, RPM_BINS, KPA_BINS
    )
    
    # Write separate overlay file
    write_decel_overlay(
        decel_overlay, RPM_BINS, KPA_BINS,
        outdir / 'Decel_Fuel_Overlay.csv'
    )
    
    # Option: Merge into main VE delta
    if args.decel_merge:
        ve_delta = merge_decel_overlay(ve_delta, decel_overlay)
```

### With VE Operations

Two application strategies:

**Strategy A: Separate Application (Recommended)**
```bash
# First, apply standard VE corrections
python ve_operations.py apply \
  --base tables/VE_Base.csv \
  --factor output/VE_Correction_Delta.csv \
  --output tables/VE_Corrected.csv

# Then, apply decel overlay
python ve_operations.py apply \
  --base tables/VE_Corrected.csv \
  --factor output/Decel_Fuel_Overlay.csv \
  --output tables/VE_Final.csv
```

**Strategy B: Pre-merged (Optional)**
If `--decel-merge` flag used, decel enrichment is included in main delta file.

---

## Safety Considerations

### Enrichment Limits
- Maximum enrichment capped at **+30%** (prevents over-rich condition)
- Minimum enrichment floor of **+5%** in decel zone (prevents ultra-lean)
- Only applied to cells below **45 kPa** (closed throttle vacuum)

### Side Effects
- **Fuel economy**: -0.5 to -2.0 MPG depending on severity setting
- **Emissions**: Slight HC increase during decel (closed-loop mode mitigates)
- **Catalytic converter**: Not a concern—enrichment within safe range

### Validation Checks
1. **Event count sanity**: Warn if <5 events detected (insufficient data)
2. **Extreme enrichment**: Flag if any zone >25% enrichment needed
3. **Temperature correlation**: Check if popping correlates with hot engine state

---

## Testing Requirements

### Unit Tests

```python
# tests/unit/test_decel_management.py

def test_detect_decel_event():
    """Throttle closure detected as decel event."""
    
def test_decel_event_duration_filter():
    """Events outside duration range excluded."""
    
def test_afr_analysis_lean_spike():
    """AFR excursion detected and scored correctly."""
    
def test_enrichment_calculation_base():
    """Base enrichment table applied to zones."""
    
def test_enrichment_clamping():
    """Enrichment capped at 30% maximum."""
    
def test_overlay_low_kpa_only():
    """Enrichment only applied to low-MAP cells."""
```

### Integration Tests

```python
# tests/integration/test_decel_pipeline.py

def test_full_decel_pipeline():
    """Full pipeline detects events and generates overlay."""
    
def test_decel_report_generated():
    """Analysis report JSON created with correct schema."""
    
def test_severity_presets():
    """Low/medium/high presets scale enrichment correctly."""
```

### Acceptance Criteria

| Test | Expected Result |
|------|-----------------|
| Log with throttle chops | Events detected, enrichment calculated |
| Steady-state log (no decel) | No events, warning issued |
| Severity=high | Enrichment 1.3x base values |
| Cells above 45 kPa | Zero enrichment applied |

---

## Implementation Phases

### Phase 1: Core Detection (Week 1)
- [ ] Implement `detect_decel_events()` function
- [ ] Implement `analyze_decel_afr()` function
- [ ] Add CLI flags for decel management

### Phase 2: Enrichment Logic (Week 2)
- [ ] Implement `calculate_decel_enrichment()` function
- [ ] Implement `generate_decel_ve_overlay()` function
- [ ] Create severity presets

### Phase 3: Integration & Output (Week 3)
- [ ] Integrate with main pipeline
- [ ] Generate analysis report JSON
- [ ] Add merge option with standard VE delta

### Phase 4: Testing & Documentation (Week 4)
- [ ] Write unit tests (target: 90% coverage)
- [ ] Write integration tests
- [ ] Update user documentation
- [ ] Create sample test data with decel events

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Pop elimination rate | >90% of pops eliminated on medium setting |
| False positive rate | <5% unnecessary enrichment |
| User satisfaction | "Decel pop" complaints reduced by 80% |
| Fuel economy impact | <1.5 MPG loss on medium setting |

---

## References

- [VTWIN_TUNING_TECHNICAL_VALIDATION.md](../VTWIN_TUNING_TECHNICAL_VALIDATION.md) - Source research
- [DYNOAI_SAFETY_RULES.md](../DYNOAI_SAFETY_RULES.md) - Clamping and safety limits
- Power Commander decel adjustment guide (industry reference)
- Delphi ECM decel fuel cut behavior documentation

