# Transient Fuel Compensation Guide

## Overview

The Transient Fuel Compensation module analyzes dyno data to detect acceleration and deceleration events, then calculates the fuel compensation needed to maintain target AFR during transient conditions.

## Quick Start

```python
import pandas as pd
from dynoai.core.transient_fuel import TransientFuelAnalyzer

# Load your dyno data
df = pd.read_csv('dyno_run.csv')

# Create analyzer
analyzer = TransientFuelAnalyzer(
    target_afr=13.0,              # Your target AFR
    map_rate_threshold=50.0,      # kPa/sec threshold for transient detection
    tps_rate_threshold=20.0,      # %/sec threshold for transient detection
)

# Analyze transients
result = analyzer.analyze_transients(df)

# Review recommendations
for rec in result.recommendations:
    print(rec)

# Export for Power Vision
analyzer.export_power_vision(result, 'transient_compensation.txt')

# Save plots
for name, fig in result.plots.items():
    fig.savefig(f'{name}.png', dpi=150, bbox_inches='tight')
```

## Input Data Requirements

Your CSV file must contain these columns:

| Column | Description | Units | Range |
|--------|-------------|-------|-------|
| `time` | Timestamp | seconds | 0+ |
| `rpm` | Engine speed | rev/min | 0-20000 |
| `map` | Manifold pressure | kPa | 0-500 |
| `tps` | Throttle position | % | 0-100 |
| `afr` | Air-fuel ratio | ratio | 10-18 |
| `iat` | Intake air temp (optional) | °C | -40-150 |
| `target_afr` | Target AFR (optional) | ratio | 10-18 |

**Sample Rate:** 50-100 Hz recommended for accurate rate calculations.

## What It Analyzes

### 1. Transient Event Detection
- **Acceleration Events**: Rapid increase in MAP or TPS
- **Deceleration Events**: Rapid decrease in MAP or TPS
- **Severity Classification**: Mild, moderate, or aggressive

### 2. Enrichment Tables

#### MAP Rate-Based Enrichment
Correlates manifold pressure rate of change to needed fuel enrichment:

```
MAP Rate (kPa/s)  →  Enrichment (%)
     50           →       2%
    100           →       5%
    150           →      10%
```

#### TPS Rate-Based Enrichment
Correlates throttle rate of change to needed fuel enrichment:

```
TPS Rate (%/s)    →  Enrichment (%)
     25           →       2%
     50           →       5%
     75           →      10%
```

### 3. Wall Wetting Compensation
Calculates RPM-dependent compensation factors for fuel film effects:

```python
{
    'idle': 1.05,      # 5% more fuel at idle
    'low': 1.03,       # 3% more fuel 1500-3000 RPM
    'mid': 1.01,       # 1% more fuel 3000-5000 RPM
    'high': 1.0,       # No compensation 5000-8000 RPM
    'redline': 1.0     # No compensation 8000+ RPM
}
```

### 4. Deceleration Fuel Cut
Recommends fuel reduction during deceleration to prevent rich conditions.

## Understanding Results

### Detected Events

```python
for event in result.detected_events:
    print(f"{event.event_type} event at {event.start_time:.1f}s")
    print(f"  Severity: {event.severity}")
    print(f"  Peak MAP rate: {event.peak_map_rate:.1f} kPa/s")
    print(f"  Peak TPS rate: {event.peak_tps_rate:.1f} %/s")
    print(f"  AFR error: {event.afr_error_avg:.2f}")
```

### Recommendations

The analyzer provides actionable recommendations:

- **"Increase transient enrichment by X%"** - Add more fuel during acceleration
- **"Reduce transient enrichment"** - Reduce fuel during acceleration (too rich)
- **"Enable or increase decel fuel cut"** - Cut fuel during deceleration
- **"Consider adding MAP/TPS rate-based compensation"** - Use advanced tables

### Visualization Plots

Three plots are generated:

1. **MAP Rate Enrichment** - Shows enrichment vs MAP rate
2. **TPS Rate Enrichment** - Shows enrichment vs TPS rate
3. **Timeline** - Shows RPM, MAP, AFR with highlighted transient events

## Integration with Power Vision

### Export Format

```python
analyzer.export_power_vision(result, 'transient_comp.txt')
```

The export file contains:
- MAP rate enrichment table
- TPS rate enrichment table
- Wall wetting factors by RPM range
- Tuning recommendations

### Applying to Your Tune

1. **Review the recommendations** - Understand what needs adjustment
2. **Start conservative** - Apply 50% of recommended enrichment initially
3. **Test on dyno** - Verify AFR stays on target during transients
4. **Iterate** - Increase enrichment if still lean, decrease if rich

## Advanced Configuration

### Custom Thresholds

```python
analyzer = TransientFuelAnalyzer(
    target_afr=12.8,                 # Custom target AFR
    map_rate_threshold=75.0,         # Higher threshold = detect only aggressive events
    tps_rate_threshold=30.0,         # Higher threshold = less sensitive
    afr_tolerance=0.3,               # Tighter tolerance = more strict
    sample_rate_hz=100.0,            # Match your data logger sample rate
)
```

### Multiple Target AFRs

If your tune has different target AFRs at different RPM/load points:

```python
# Add target_afr column to your data
df['target_afr'] = df.apply(
    lambda row: 12.5 if row['rpm'] > 5000 else 13.0,
    axis=1
)

result = analyzer.analyze_transients(df)
```

## Troubleshooting

### No Events Detected

**Problem:** `result.detected_events` is empty

**Solutions:**
- Check your data has actual transient events (not just steady-state)
- Lower the thresholds: `map_rate_threshold=30.0, tps_rate_threshold=15.0`
- Verify sample rate is adequate (50+ Hz)

### Too Many Events Detected

**Problem:** Every small throttle movement triggers an event

**Solutions:**
- Raise the thresholds: `map_rate_threshold=75.0, tps_rate_threshold=40.0`
- Smooth your input data before analysis
- Filter out events shorter than 0.5 seconds

### AFR Errors Look Wrong

**Problem:** Calculated AFR errors don't match what you see

**Solutions:**
- Verify your `target_afr` column is correct
- Check AFR sensor calibration
- Ensure time column is in seconds (not milliseconds)

### Plots Don't Show

**Problem:** `result.plots` is empty or plots don't display

**Solutions:**
- Module uses non-interactive backend (Agg)
- Save plots to files: `fig.savefig('plot.png')`
- For interactive viewing, change backend before import

## Example Workflows

### Workflow 1: Quick Analysis

```python
# Load, analyze, export - one shot
df = pd.read_csv('dyno_run.csv')
analyzer = TransientFuelAnalyzer()
result = analyzer.analyze_transients(df)
analyzer.export_power_vision(result, 'export.txt')
```

### Workflow 2: Iterative Tuning

```python
# First run - baseline
result1 = analyzer.analyze_transients(df_baseline)
print(f"Baseline: {len(result1.detected_events)} events")

# Apply corrections, re-test
result2 = analyzer.analyze_transients(df_after_corrections)
print(f"After corrections: {len(result2.detected_events)} events")

# Compare AFR errors
errors_before = [e.afr_error_avg for e in result1.detected_events]
errors_after = [e.afr_error_avg for e in result2.detected_events]
print(f"Error improvement: {np.mean(errors_before) - np.mean(errors_after):.2f}")
```

### Workflow 3: Batch Processing

```python
import glob

for csv_file in glob.glob('runs/*.csv'):
    df = pd.read_csv(csv_file)
    result = analyzer.analyze_transients(df)
    
    # Save results
    base_name = csv_file.replace('.csv', '')
    analyzer.export_power_vision(result, f'{base_name}_transient.txt')
    
    for plot_name, fig in result.plots.items():
        fig.savefig(f'{base_name}_{plot_name}.png')
```

## Best Practices

### Data Collection
- **Use high sample rate** (50-100 Hz minimum)
- **Include variety of transients** (mild, moderate, aggressive)
- **Test in multiple gears** (different loads)
- **Warm engine** (cold enrichment affects results)

### Analysis
- **Start conservative** (apply 50% of recommendations)
- **Verify determinism** (same data = same results)
- **Check for sensor noise** (smooth data if needed)
- **Document changes** (track what you applied)

### Tuning
- **Test incrementally** (small changes, re-test)
- **Verify safety** (never go leaner without verification)
- **Use dyno for validation** (not street testing)
- **Keep backups** (save original tune files)

## API Reference

### TransientFuelAnalyzer

```python
class TransientFuelAnalyzer:
    def __init__(
        self,
        target_afr: float = 13.0,
        map_rate_threshold: float = 50.0,
        tps_rate_threshold: float = 20.0,
        afr_tolerance: float = 0.5,
        sample_rate_hz: float = 50.0,
    )
    
    def analyze_transients(self, df: pd.DataFrame) -> TransientFuelResult
    
    def detect_transient_events(self, df: pd.DataFrame) -> List[TransientEvent]
    
    def calculate_map_rate_enrichment(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame
    
    def calculate_tps_rate_enrichment(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame
    
    def calculate_wall_wetting_compensation(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> Dict[str, float]
    
    def export_power_vision(
        self, result: TransientFuelResult, output_path: str
    ) -> None
```

### TransientFuelResult

```python
@dataclass
class TransientFuelResult:
    wall_wetting_factor: Dict[str, float]
    map_rate_table: pd.DataFrame
    tps_rate_table: pd.DataFrame
    transient_3d_table: pd.DataFrame
    decel_fuel_cut_table: pd.DataFrame
    afr_error_during_transients: List[Tuple[float, float]]
    detected_events: List[TransientEvent]
    recommendations: List[str]
    plots: Dict[str, plt.Figure]
```

### TransientEvent

```python
@dataclass
class TransientEvent:
    start_time: float
    end_time: float
    event_type: str  # 'accel' or 'decel'
    severity: str    # 'mild', 'moderate', 'aggressive'
    peak_map_rate: float
    peak_tps_rate: float
    avg_rpm: float
    afr_error_avg: float
    afr_error_peak: float
```

## Support

For issues or questions:
- Check the test suite: `tests/test_transient_fuel.py`
- Run the example: `python dynoai/core/transient_fuel.py`
- Review DynoAI_3 documentation: `docs/`

---

**Safety Notice:** Always verify tuning changes on a dyno before street use. Incorrect transient compensation can cause engine damage.

