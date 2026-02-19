# Phase 7: Predictive Test Planning - User Guide

## Overview

Phase 7 introduces intelligent test planning that learns from your dyno sessions and suggests the most efficient next steps to maximize table coverage. Instead of guessing which pulls to run, the system tracks what you've covered across all runs and recommends tests that fill the most important gaps with minimal time investment.

## Key Features

### 1. **Cross-Run Coverage Tracking**
The system remembers every cell you've hit across all runs for each vehicle, building a cumulative coverage map that persists between sessions.

### 2. **Smart Gap Detection**
Automatically identifies coverage gaps in high-impact regions:
- **High Priority**: High-MAP midrange (torque peak, knock-sensitive)
- **High Priority**: Tip-in transition zones (transient fueling critical)
- **Medium Priority**: Idle/low-MAP (stability and sensor quality)

### 3. **Efficiency Scoring**
Every test suggestion includes an efficiency score showing expected coverage gain per minute of dyno time.

### 4. **User Constraints**
Set practical limits that filter suggestions:
- RPM range (e.g., 1500-6500)
- MAP range (e.g., 30-100 kPa)
- Max pulls per session
- Preferred environment (dyno, street, or both)

### 5. **Visual Priority Overlay**
Color-coded heatmap shows exactly which cells to target next:
- 🔴 Red = High priority gaps
- 🟡 Yellow = Medium priority gaps
- 🔵 Blue = Already covered

## Quick Start

### First Run

1. **Run your first dyno session** as normal
2. **Generate NextGen analysis**:
   ```bash
   POST /api/nextgen/<run_id>/generate
   ```
3. **Record the run** to start tracking:
   ```bash
   POST /api/nextgen/planner/feedback
   {
     "run_id": "run1",
     "vehicle_id": "my_supra",
     "dyno_signature": "dynojet_001"
   }
   ```

### Configure Your Constraints

In the NextGen Analysis panel, expand the **Test Planner Constraints** section:

1. Set **RPM range** based on your engine's safe operating range
2. Set **MAP range** (naturally aspirated might be 20-100 kPa, boosted could be higher)
3. Set **max pulls per session** based on your typical dyno booking time
4. Choose **test environment**: dyno-only, street-only, or both

Click **Apply Constraints** to save.

### Get Smart Suggestions

After recording a run, the system automatically:
- Updates cumulative coverage
- Identifies remaining gaps
- Filters suggestions by your constraints
- Sorts by efficiency

View suggestions in the **Next Test Plan** section. Each test shows:
- **Expected coverage gain**: "+8.5% coverage"
- **Efficiency badge**: High/Medium/Low efficiency
- **Priority**: P1 (highest) to P3
- **RPM/MAP ranges**: Exactly where to test

### Run Suggested Tests

Execute the top 2-3 suggested tests in your next session. After each run:
1. Generate NextGen analysis
2. POST to `/planner/feedback` to update tracker
3. Suggestions automatically refresh with new priorities

### Track Progress

Check your cumulative coverage:
```bash
GET /api/nextgen/planner/cumulative-coverage?vehicle_id=my_supra
```

Response shows:
- Total runs completed
- Overall coverage percentage
- List of all run IDs
- Last update timestamp

## UI Guide

### NextGen Analysis Panel Sections

#### 1. Channel Readiness
Shows which required channels are present/missing.

#### 2. Mode Distribution
Summary of data by operating mode (WOT, cruise, tip-in, etc.).

#### 3. Coverage Gaps Panel
Lists the most important missing regions with:
- RPM and MAP ranges
- Impact level (high/medium/low)
- Coverage percentage
- Recommended test type

#### 4. Test Planner Constraints (NEW in Phase 7)
Interactive panel to configure your limits:
- Sliders for RPM/MAP ranges
- Input for max pulls per session
- Radio buttons for test environment preference

#### 5. Hit These Cells Next (NEW in Phase 7)
Visual heatmap overlay showing:
- Red cells = high priority targets
- Yellow cells = medium priority targets
- Blue cells = already covered
- Click cells to filter suggestions for that region

#### 6. Dyno Pull Script
Step-by-step dyno test instructions with:
- Gear recommendations
- Start/end RPM
- Expected coverage gain per pull
- Efficiency score

#### 7. Street Script
Street logging route instructions for:
- Cruise segments
- Tip-in/tip-out events
- Heat soak periods
- Idle holds

#### 8. Spark Valley Findings
Detected timing valleys (collapsed by default).

#### 9. Heatmaps
Interactive 2D surfaces for spark, AFR error, knock rate.

#### 10. Cause Tree Hypotheses
Ranked diagnostic hypotheses (collapsed by default).

## API Reference

### Coverage Tracking

#### Get Cumulative Coverage
```http
GET /api/nextgen/planner/cumulative-coverage?vehicle_id=<id>
```

**Response:**
```json
{
  "vehicle_id": "my_supra",
  "dyno_signature": "dynojet_001",
  "total_runs": 5,
  "run_ids": ["run1", "run2", "run3", "run4", "run5"],
  "surfaces": ["spark_f", "spark_r", "afr_error_f", "afr_error_r"],
  "total_cells": 800,
  "covered_cells": 520,
  "coverage_pct": 65.0,
  "last_updated": "2026-01-27T15:30:00Z"
}
```

#### Get Coverage Gaps
```http
GET /api/nextgen/planner/cumulative-gaps?vehicle_id=<id>&min_hits=5
```

**Response:**
```json
{
  "vehicle_id": "my_supra",
  "gaps": [
    {
      "surface_id": "spark_f",
      "region_name": "high_map_midrange",
      "rpm_range": [2500, 4500],
      "map_range": [80, 100],
      "empty_cells": 12,
      "total_cells": 20,
      "coverage_pct": 40.0,
      "impact": "high",
      "description": "High-load midrange - knock-sensitive and torque peak region"
    }
  ],
  "gap_count": 3
}
```

### Constraints

#### Get Constraints
```http
GET /api/nextgen/planner/constraints?vehicle_id=<id>
```

**Response:**
```json
{
  "min_rpm": 1500,
  "max_rpm": 6500,
  "min_map_kpa": 30,
  "max_map_kpa": 100,
  "max_pulls_per_session": 8,
  "preferred_test_environment": "both"
}
```

#### Update Constraints
```http
PUT /api/nextgen/planner/constraints?vehicle_id=<id>
Content-Type: application/json

{
  "min_rpm": 1500,
  "max_rpm": 6500,
  "min_map_kpa": 30,
  "max_map_kpa": 100,
  "max_pulls_per_session": 5,
  "preferred_test_environment": "inertia_dyno"
}
```

### Predictions

#### Get Next Test Predictions
```http
POST /api/nextgen/planner/predict/<run_id>?vehicle_id=<id>
```

**Response:**
```json
{
  "success": true,
  "vehicle_id": "my_supra",
  "current_coverage_pct": 65.0,
  "total_runs": 5,
  "gaps": [...],
  "recommended_tests": [
    {
      "name": "High-MAP Midrange Pull",
      "goal": "Fill torque peak and knock-sensitive region",
      "rpm_range": [2500, 4500],
      "map_range": [80, 100],
      "test_type": "wot_pull",
      "priority": 1,
      "expected_coverage_gain": 8.5,
      "efficiency_score": 0.85,
      "constraints": "Use 3rd or 4th gear; maintain consistent ramp rate",
      "success_criteria": "≥3 samples per cell in target region"
    }
  ],
  "constraints_applied": {...}
}
```

### Feedback Loop

#### Record Run Completion
```http
POST /api/nextgen/planner/feedback
Content-Type: application/json

{
  "run_id": "run6",
  "vehicle_id": "my_supra",
  "dyno_signature": "dynojet_001"
}
```

**Response:**
```json
{
  "success": true,
  "vehicle_id": "my_supra",
  "run_id": "run6",
  "total_runs": 6,
  "new_coverage_pct": 72.5,
  "message": "Coverage updated for vehicle my_supra"
}
```

#### Reset Coverage (Start Fresh)
```http
POST /api/nextgen/planner/reset/<vehicle_id>
```

## Efficiency Scoring Explained

The efficiency score combines three factors:

### 1. Expected Cell Coverage
Based on the RPM/MAP range of the test:
- Larger ranges = more cells covered
- WOT pulls get a 1.5x multiplier (sweep across RPM)
- Steady state gets 1.2x
- Idle holds get 0.5x (small region)

### 2. Estimated Time
Each test type has a typical duration:
- WOT pull: ~2 minutes (ramp + cooldown)
- Steady state sweep: ~5 minutes
- Transient rolloff: ~3 minutes
- Idle hold: ~1 minute

### 3. Priority Boost
High-priority tests (P1) get a 1.3x efficiency boost to ensure critical regions are filled first.

**Final Score:**
```
efficiency = (cells_per_minute / max_cells_per_minute) * priority_multiplier
normalized to 0.0-1.0
```

**Interpretation:**
- **0.7-1.0** = High efficiency (green badge) - great coverage per minute
- **0.4-0.7** = Medium efficiency (yellow badge) - decent return
- **0.0-0.4** = Low efficiency (gray badge) - low coverage per time

## Best Practices

### 1. **Start with Constraints**
Set realistic limits before your first session. This ensures all suggestions are actually executable on your dyno/vehicle.

### 2. **Follow Priority Order**
Always run P1 (high priority) tests first. These fill the most critical regions that affect tuning decisions.

### 3. **Check Coverage After Each Run**
View the updated coverage percentage to track progress toward 100%.

### 4. **Use the Visual Overlay**
The "Hit These Cells Next" heatmap shows exactly where gaps remain. Red zones should be your focus.

### 5. **Mix Test Environments**
If possible, combine dyno pulls (for high-MAP data) with street logging (for transients, cruise, idle). Set environment to "both" for balanced suggestions.

### 6. **Don't Over-Pull**
The system will keep suggesting tests until 100% coverage. Use the `max_pulls_per_session` constraint to avoid dyno fatigue or overheating.

### 7. **Trust the Efficiency Scores**
High-efficiency tests give you the most data in the least time. Run these when dyno time is limited.

### 8. **Update After Every Run**
Always POST to `/planner/feedback` after generating NextGen analysis. This keeps the coverage tracker current.

## Troubleshooting

### "No coverage data found"
**Cause:** Haven't recorded any runs yet.
**Fix:** POST to `/planner/feedback` after your first NextGen analysis.

### "Coverage not increasing"
**Cause:** Running tests in already-covered regions.
**Fix:** Check the "Hit These Cells Next" heatmap and follow the red/yellow zones.

### "All suggestions filtered out"
**Cause:** Constraints are too restrictive.
**Fix:** Widen RPM/MAP ranges or increase `max_pulls_per_session`.

### "Wrong vehicle data"
**Cause:** Using generic "default" vehicle_id for multiple vehicles.
**Fix:** Use unique `vehicle_id` for each vehicle (e.g., "supra_001", "evo_mr").

### "Coverage reset accidentally"
**Cause:** Called `/planner/reset/<vehicle_id>`.
**Fix:** No undo available. Re-run your sessions to rebuild coverage.

## Advanced Usage

### Multi-Vehicle Fleet
Track coverage separately per vehicle:
```bash
# Supra
POST /planner/feedback {"vehicle_id": "supra_001", ...}

# Evo
POST /planner/feedback {"vehicle_id": "evo_mr", ...}

# View Supra coverage
GET /planner/cumulative-coverage?vehicle_id=supra_001

# View Evo coverage
GET /planner/cumulative-coverage?vehicle_id=evo_mr
```

### Export/Import Mapping Templates
Save coverage data for backup:
1. GET `/planner/cumulative-coverage?vehicle_id=my_car`
2. Save JSON response locally
3. Restore by manually placing file in `config/coverage_tracker/`

### Custom Gap Detection
Modify `api/services/coverage_tracker.py` to define your own high-impact regions:
```python
regions = [
    {
        "name": "boost_transition",
        "rpm_range": (3000, 5000),
        "map_range": (50, 80),  # Where boost builds
        "impact": "high",
    },
]
```

### Integration with Auto-Tuning
Use the predictions endpoint to automatically queue tests:
```python
response = requests.post(f"/api/nextgen/planner/predict/{run_id}")
next_tests = response.json()["recommended_tests"]

for test in next_tests[:3]:  # Top 3
    schedule_dyno_pull(
        rpm_range=test["rpm_range"],
        map_range=test["map_range"],
        gear=3,
    )
```

## Storage Locations

- **Coverage tracker files**: `config/coverage_tracker/<vehicle_id>.json`
- **Constraint files**: `config/planner_constraints/<vehicle_id>.json`

Files are human-readable JSON and can be edited manually if needed.

## Performance

- **Coverage aggregation**: <50ms per run
- **Gap detection**: <100ms for typical surfaces
- **Efficiency scoring**: <1ms per test step
- **Storage**: ~10KB per vehicle per 10 runs

## What's Next

Phase 7 provides the foundation for future enhancements:
- **Machine learning predictions** based on historical data
- **Automated test execution** via dyno control integration
- **Fleet analytics** comparing coverage across multiple vehicles
- **Advanced visualizations** showing coverage evolution over time

## Support

For issues or questions:
1. Check the `/docs` folder for additional documentation
2. Run the integration test: `python scripts/test_phase7_integration.py`
3. Review test suite: `pytest tests/api/test_coverage_tracker.py tests/core/test_efficiency_scoring.py -v`
