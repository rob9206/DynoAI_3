# AI Training Data - Quick Start Guide

## TL;DR

DynoAI can now capture tuning knowledge to train AI models. Here's how to use it:

## For Tuners: Contributing Training Data

### Step 1: Complete a Tune

Complete your normal dyno tuning session with DynoAI.

### Step 2: Document the Build

After tuning, record these details:

**Engine Specs**:

- Engine family (Twin Cam, M8, etc.)
- Displacement (103 CI, 114 CI, etc.)
- Compression ratio
- Stage level (1, 2, 3, 4)

**Cam Specs** (IMPORTANT):

- Profile name (S&S 475, Wood TW-222, etc.)
- Overlap degrees (front and rear) - *Check cam card or manufacturer specs*
- Duration @ 0.053" (intake/exhaust)
- Lift (intake/exhaust in inches)

**Intake/Exhaust**:

- Air cleaner type
- Throttle body size (mm)
- Exhaust type (2-into-1, true dual)
- Header diameter

**Fuel**:

- Injector flow (lb/hr)
- Octane requirement

### Step 3: Save Your Tables

Export these from your tuning software:

- Initial VE table (front and rear)
- Final VE table (front and rear)
- Initial spark table (front and rear)
- Final spark table (front and rear)

### Step 4: Submit (Future Feature)

Once we have a web interface, you'll submit your session data.

**Privacy Note**: No customer names or personal info are collected. Only technical specs (engine, cam, results) are stored.

For now, contact the DynoAI team.

## For Developers: Using the Training Data API

### Quick Example

```python
from api.services.training_data_collector import TrainingDataCollector
from api.models.training_data_schemas import *

# Create collector
collector = TrainingDataCollector()

# Define build configuration
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

# Define conditions
conditions = EnvironmentalConditions(
    ambient_temp_f=75.0,
    barometric_pressure_inhg=29.92,
    humidity_percent=45.0,
    altitude_ft=500
)

# Define dyno metadata
dyno_meta = DynoSessionMetadata(
    dyno_type="Dynojet 250i",
    load_type="inertia",
    fan_airflow_cfm=5000,
    warmup_time_min=10,
    runs_performed=6
)

# Create session
session = collector.create_session_from_run(
    run_id="run_20250106_001",
    build_config=build_config,
    objective=TuningObjective.VE_OPTIMIZATION,
    conditions=conditions,
    dyno_metadata=dyno_meta,
    initial_tables={
        "ve_front": [[...]],  # 13x12 grid: [RPM_bins][KPA_bins]
        # Example: [[90, 92, 94, ...], [...], ...]  # Row 0 = 1000 RPM
        "ve_rear": [[...]],
        "spark_front": [[...]],  # Spark advance in degrees
        "spark_rear": [[...]]
    },
    final_tables={
        "ve_front": [[...]],
        "ve_rear": [[...]],
        "spark_front": [[...]],
        "spark_rear": [[...]]
    },
    results={
        "peak_hp": 92.5,
        "peak_torque": 98.2,
        "afr_accuracy_rms_error": 0.18,
        "max_cylinder_afr_delta": 0.7,
        "duration_hours": 4.5,
        "iterations": 3,
        "afr_targets": {
            "idle": 14.0,
            "cruise": 13.8,
            "wot": 12.8
        }
    }
)

# Add to dataset
collector.add_session(session)

# Extract patterns
collector.extract_all_patterns()

# Save
collector.save_dataset("training_data/my_dataset.json")
```

### Validate Your Data

```bash
python scripts/validate_training_data.py training_data/my_dataset.json

# Expected output:
# ✅ Status: VALID
# 📊 Total Sessions: 1, Total Dyno Hours: 4.5
#   Objectives:
#     - ve_optimization: 1
```

## What Gets Learned

### 1. VE Prediction

**Input**: Engine family + Stage + Cam overlap + Displacement  
**Output**: Predicted VE deltas (idle, cruise, midrange, WOT)  
**Benefit**: Instant base maps for new builds

### 2. Cylinder Balancing

**Input**: Cam profile + Exhaust type + Header lengths  
**Output**: Predicted AFR imbalance + Correction factors  
**Benefit**: Auto-balance without sensor swapping

### 3. Decel Pop Fix

**Input**: Cam overlap + Exhaust type + PAIR valve status  
**Output**: Enrichment zones and percentages  
**Benefit**: Auto-generate decel overlay

### 4. Heat Soak Compensation

**Input**: Ambient temp + IAT peak + Soak duration  
**Output**: VE inflation + Correction overlay  
**Benefit**: Compensate for hot dyno conditions

### 5. Timing Optimization

**Input**: Compression ratio + Fuel octane + Cam + Altitude  
**Output**: Safe timing limits + MBT targets  
**Benefit**: Auto-optimize timing safely

## Data Requirements

To train effective models, we need:

- **50+ VE optimization sessions** (10 per common cam)
- **50+ cylinder balance sessions** (various configs)
- **30+ decel pop fixes** (various overlap levels)
- **40+ timing sessions** (various CR/octane combos)
- **25+ heat soak sessions** (various temps)

## File Locations

```text
api/models/training_data_schemas.py       # Data structures
api/services/training_data_collector.py   # Collection service
scripts/validate_training_data.py         # Validation tool
docs/examples/training_data_example.json  # Example dataset
```

## Documentation

- **Full Guide**: `docs/AI_TRAINING_DATA_GUIDE.md`
- **Complete Overview**: `docs/AI_TRAINING_DATA_COMPLETE.md`
- **V-Twin Validation**: `docs/V_TWIN_TUNING_VALIDATION.md`
- **Security Review**: `docs/AI_TRAINING_SECURITY_REVIEW.md`

## Common Mistakes to Avoid

1. **Missing Cam Overlap** - Most critical spec for AI predictions. Check the cam card or manufacturer website.
2. **Incorrect Stage Level** - Use actual stage, not aspiration (e.g., Stage 2, not "Stage 3 wannabe")
3. **Mixed Units** - Displacement in CI, not cc (103 CI not 1690cc)
4. **Forgetting Initial Tables** - Need both BEFORE and AFTER VE/spark tables
5. **No Environmental Data** - Altitude/temp affect results significantly
6. **Zero Values** - Don't leave fields blank; enter actual values or omit optional fields

## Need Help?

1. Check the example dataset: `docs/examples/training_data_example.json`
2. Run validation tool: `python scripts/validate_training_data.py your_file.json`
3. Read full guide: `docs/AI_TRAINING_DATA_GUIDE.md`
4. Contact DynoAI development team

---

**Last Updated**: 2025-01-06  
**Status**: Ready for data collection
