# DynoAI Training Data Guide

## Overview

This guide explains DynoAI's AI training data structures designed to capture learnable patterns from V-twin tuning sessions. The training data enables machine learning models to:

- **Predict base VE tables** from build specifications (cam overlap, displacement, stage level)
- **Automate per-cylinder balancing** by learning imbalance patterns
- **Generate decel fuel management** overlays automatically
- **Optimize timing tables** while avoiding knock
- **Compensate for heat soak** thermal drift
- **Recommend AFR targets** based on operating conditions

## Architecture

### Data Flow

```
Raw Dyno Log → TuningSession → Pattern Extraction → TrainingDataset → AI Model
```

1. **Raw Dyno Logs**: CSV files with RPM, MAP, TPS, AFR, knock, IAT data
2. **TuningSession**: Structured session data with build config, tables, outcomes
3. **Pattern Extraction**: Algorithms that extract learnable patterns
4. **TrainingDataset**: Aggregated patterns from multiple sessions
5. **AI Model**: Machine learning model trained on patterns

### Key Data Structures

#### 1. Build Configuration

Captures engine specifications that determine tuning requirements:

```python
build_config = BuildConfiguration(
    engine_family=EngineFamily.TWIN_CAM,
    displacement_ci=103,
    compression_ratio=10.5,
    stage=StageLevel.STAGE_2,
    cam_spec=CamSpecification(
        profile=CamProfile.S_AND_S_475,
        intake_duration_deg=228,
        exhaust_duration_deg=228,
        intake_lift_in=0.475,
        exhaust_lift_in=0.475,
        lobe_separation_angle_deg=106,
        overlap_deg_front=34.7,
        overlap_deg_rear=22.4,
        idle_rpm_target=950
    ),
    air_cleaner="S&S Stealth",
    throttle_body_mm=55,
    header_type="2-into-1",
    injector_flow_lb_hr=5.2,
    octane_requirement=91
)
```

#### 2. Tuning Session

Complete record of a tuning session:

```python
session = TuningSession(
    session_id="run_20250106_001",
    timestamp_utc="2025-01-06T18:30:00Z",
    tuner_id="tuner_001",
    build_config=build_config,
    objective=TuningObjective.VE_OPTIMIZATION,
    conditions=EnvironmentalConditions(
        ambient_temp_f=75.0,
        barometric_pressure_inhg=29.92,
        humidity_percent=45.0,
        altitude_ft=500
    ),
    dyno_metadata=DynoSessionMetadata(
        dyno_type="Dynojet 250i",
        load_type="inertia",
        fan_airflow_cfm=5000,
        warmup_time_min=10,
        runs_performed=6
    ),
    # VE/Spark tables before and after
    initial_ve_table_front=[[...]],
    final_ve_table_front=[[...]],
    # Results
    peak_hp=92.5,
    peak_torque=98.2,
    afr_accuracy_rms_error=0.18,
    max_cylinder_afr_delta=0.7,
    tuning_duration_hours=4.5
)
```

#### 3. VE Scaling Pattern

Captures how VE changes with build modifications:

```python
ve_pattern = VEScalingPattern(
    engine_family=EngineFamily.TWIN_CAM,
    stage=StageLevel.STAGE_2,
    cam_overlap_category="moderate",  # From cam spec
    displacement_ci=103,
    ve_delta_idle=+12.5,      # +12.5% VE at idle
    ve_delta_cruise=+15.2,    # +15.2% at cruise
    ve_delta_midrange=+18.7,  # +18.7% at midrange
    ve_delta_wot=+22.3,       # +22.3% at WOT
    front_rear_ve_difference_pct=2.1,  # 2.1% difference
    sessions_observed=1
)
```

**AI Application**: Train model to predict VE deltas from `(engine_family, stage, cam_overlap, displacement)` → `(idle_delta, cruise_delta, mid_delta, wot_delta)`

#### 4. Cylinder Imbalance Pattern

Captures per-cylinder AFR variation and corrections:

```python
imbalance_pattern = CylinderImbalancePattern(
    engine_family=EngineFamily.TWIN_CAM,
    cam_profile=CamProfile.S_AND_S_585,
    exhaust_type="true_dual",
    header_length_delta_in=2.5,  # Rear header 2.5" longer
    imbalance_cells=[
        # (rpm_idx, kpa_idx, afr_delta)
        (4, 6, 0.8),   # Rear 0.8 richer at 2500 RPM, 60 kPa
        (5, 7, 1.1),   # Rear 1.1 richer at 3000 RPM, 70 kPa
        (6, 8, 0.9),   # Rear 0.9 richer at 3500 RPM, 80 kPa
    ],
    primary_cause="exhaust_scavenging",
    front_ve_corrections=[[...]],  # VE adjustments applied
    rear_ve_corrections=[[...]],
    imbalance_before_max=1.2,
    imbalance_after_max=0.3,
    correction_success=True
)
```

**AI Application**: Given `(cam_profile, exhaust_type, header_delta)` → predict likely imbalance cells and correction factors

#### 5. Decel Popping Pattern

Captures decel characteristics and enrichment solutions:

```python
decel_pattern = DecelPoppingPattern(
    engine_family=EngineFamily.TWIN_CAM,
    cam_overlap_deg=28.6,
    exhaust_type="2-into-1",
    pair_valve_present=True,
    pop_severity=7,  # 0-10 scale
    pop_rpm_range=(1500, 3200),
    pop_throttle_position=3.0,
    decel_afr_spike_max=16.5,  # Peak lean spike
    enrichment_zones=[
        # (rpm_min, rpm_max, tps_min, tps_max, enrichment_pct)
        (1500, 2500, 0, 2, 0.22),  # +22% enrichment
        (2500, 3500, 0, 2, 0.18),  # +18% enrichment
    ],
    pop_eliminated=True,
    fuel_economy_impact_pct=-0.8,
    customer_satisfaction=9
)
```

**AI Application**: Given `(cam_overlap, exhaust_type, pair_valve, pop_severity)` → predict enrichment zones

#### 6. Heat Soak Pattern

Captures thermal drift and corrections:

```python
heat_pattern = HeatSoakPattern(
    ambient_temp_f=95.0,
    airflow_cfm=4000,  # Dyno fan
    iat_initial_f=105.0,
    iat_peak_f=165.0,
    iat_soak_time_min=12.5,
    ve_inflation_pct=6.8,  # VE artificially inflated by 6.8%
    affected_rpm_range=(1000, 3000),
    affected_load_range=(20, 50),
    heat_correction_overlay=[[...]],  # Negative corrections
    hp_variation_before=5.2,  # 5.2 HP swing hot vs cold
    hp_variation_after=1.1   # 1.1 HP swing after correction
)
```

**AI Application**: Given `(ambient_temp, iat_peak, soak_time)` → predict VE inflation and generate correction overlay

#### 7. Knock Timing Pattern

Captures knock characteristics and timing optimization:

```python
timing_pattern = KnockTimingPattern(
    compression_ratio=10.5,
    fuel_octane=91,
    cam_profile=CamProfile.S_AND_S_475,
    altitude_ft=500,
    knock_cells=[
        # (rpm_idx, kpa_idx, knock_count)
        (7, 10, 15),  # 15 knock events at 4000 RPM, 90 kPa
        (8, 11, 8),   # 8 knock events at 4500 RPM, 95 kPa
    ],
    knock_severity_max=3.5,  # Max 3.5° retard seen
    timing_retards=[
        # (rpm_idx, kpa_idx, retard_deg)
        (7, 10, -4.0),  # Retard 4° where knock occurred
        (8, 11, -2.0),  # Retard 2°
    ],
    timing_advances=[
        # (rpm_idx, kpa_idx, advance_deg)
        (5, 8, +1.0),  # Safe to advance 1° in clean areas
    ],
    mbt_achieved=True,
    torque_gain_pct=3.2,
    knock_free=True
)
```

**AI Application**: Given `(compression_ratio, fuel_octane, cam_profile, altitude)` → predict safe timing limits and MBT targets

## Usage Workflow

### 1. Collect Training Data

```python
from api.services.training_data_collector import TrainingDataCollector
from api.models.training_data_schemas import *

# Initialize collector
collector = TrainingDataCollector(dataset_id="dynoai_v1")

# Create build configuration
build_config = BuildConfiguration(...)

# Create session from completed dyno run
session = collector.create_session_from_run(
    run_id="run_001",
    build_config=build_config,
    objective=TuningObjective.VE_OPTIMIZATION,
    conditions=EnvironmentalConditions(...),
    dyno_metadata=DynoSessionMetadata(...),
    initial_tables={"ve_front": [...], "ve_rear": [...]},
    final_tables={"ve_front": [...], "ve_rear": [...]},
    results={
        "peak_hp": 92.5,
        "peak_torque": 98.2,
        "afr_accuracy_rms_error": 0.18,
        ...
    }
)

# Add session to dataset
collector.add_session(session)
```

### 2. Extract Patterns

```python
# Extract all patterns from sessions
collector.extract_all_patterns()

# Review extracted patterns
summary = collector.dataset.summary()
print(f"VE patterns: {summary['pattern_counts']['ve_scaling']}")
print(f"Cylinder imbalance patterns: {summary['pattern_counts']['cylinder_imbalance']}")
```

### 3. Save Training Dataset

```python
# Save to JSON
collector.save_dataset("training_data/dataset_2025_v1.json")
```

### 4. Train AI Model (Future)

```python
# Load dataset
from api.ml.model_trainer import ModelTrainer

trainer = ModelTrainer()
trainer.load_dataset("training_data/dataset_2025_v1.json")

# Train VE prediction model
ve_model = trainer.train_ve_predictor(
    features=["engine_family", "stage", "cam_overlap", "displacement"],
    targets=["ve_delta_idle", "ve_delta_cruise", "ve_delta_mid", "ve_delta_wot"]
)

# Save trained model
ve_model.save("models/ve_predictor_v1.pkl")
```

## Pattern Requirements for High-Value Features

Based on the V-twin tuning validation research, here are the minimum pattern requirements for each high-priority feature:

### Per-Cylinder VE Optimization (HIGH Priority)

**Patterns Needed:**
- 50+ sessions with cylinder imbalance data
- Various cam profiles (stock, moderate overlap, high overlap)
- Different exhaust types (2-into-1, true dual)
- Temperature differential measurements

**Expected Outcome:**
- Predict imbalance magnitude from build specs
- Auto-generate correction factors
- Reduce tuning time from 6 hours → 3 hours

### Decel Pop Elimination (HIGH Priority)

**Patterns Needed:**
- 30+ sessions with decel pop problems
- Various cam overlap levels (10°-50°)
- PAIR valve present/absent configurations
- Before/after enrichment data

**Expected Outcome:**
- Auto-generate decel enrichment overlay
- Eliminate manual 0% throttle column editing
- 95%+ pop elimination success rate

### Cam-Specific Base Maps (HIGH Priority)

**Patterns Needed:**
- 20+ sessions per common cam profile
- VE deltas from stock for each cam
- Stage progression data (Stage 1 → 2 → 3)

**Expected Outcome:**
- Instant base maps for 10+ common cams
- Reduce initial tune time from 4 hours → 1 hour

### Knock-Based Timing Learning (HIGH Priority)

**Patterns Needed:**
- 40+ sessions with knock detection data
- Various compression ratios (9.0-11.5)
- Different octane levels (91, 93, E85)
- Altitude variations (0-5000 ft)

**Expected Outcome:**
- Auto-advance timing to MBT safely
- Predict knock-prone cells from build specs
- Optimize timing in cells currently skipped

### Heat Soak Compensation (MEDIUM Priority)

**Patterns Needed:**
- 25+ sessions with IAT drift data
- Various ambient temperatures (70°F-100°F)
- Different fan airflow levels
- HP variation measurements

**Expected Outcome:**
- Predict VE inflation from thermal conditions
- Correct for heat-soaked tuning sessions
- Reduce HP variation from 5 HP → 2 HP

## Data Collection Best Practices

### 1. Complete Documentation

Always capture:
- **Full build specs** (don't skip cam overlap degrees!)
- **Environmental conditions** (altitude matters!)
- **Before and after tables** (initial and final VE/spark)
- **Tuner notes** (challenges encountered, solutions applied)

### 2. Quality Over Quantity

Better to have:
- 50 high-quality sessions with complete data
- Than 200 incomplete sessions missing key fields

### 3. Diverse Coverage

Prioritize collecting data from:
- **Various stages** (Stock, Stage 1-4)
- **Different cams** (Stock, mild, aggressive)
- **Multiple engine families** (Twin Cam, M8, Evo)
- **Different altitudes** (Sea level, 3000 ft, 5000 ft)

### 4. Ground Truth Validation

Verify patterns with:
- **Dyno results** (HP, torque, AFR accuracy)
- **Customer feedback** (decel pop eliminated? drivability?)
- **Long-term outcomes** (did tune hold up after 1000 miles?)

## Example Training Data File

See `docs/examples/training_data_example.json` for a complete example with:
- 3 tuning sessions (VE optimization, cylinder balance, decel fix)
- Extracted patterns (VE scaling, imbalance, decel)
- Full build configurations
- Environmental conditions

## Next Steps

1. **Implement data collection hooks** in existing DynoAI tuning workflows
2. **Build pattern extraction algorithms** (mostly complete in `training_data_collector.py`)
3. **Create training dataset** from historical dyno sessions
4. **Train initial ML models** for VE prediction and cylinder balancing
5. **Validate predictions** against held-out test sessions
6. **Deploy models** to production DynoAI

## References

- `api/models/training_data_schemas.py` - Complete schema definitions
- `api/services/training_data_collector.py` - Data collection and pattern extraction
- `docs/V_TWIN_TUNING_VALIDATION.md` - Technical validation of tuning challenges
- `cylinder_balancing.py` - Current cylinder balancing implementation
- `decel_management.py` - Current decel management implementation

---

**Last Updated**: 2025-01-06  
**Version**: 1.0

