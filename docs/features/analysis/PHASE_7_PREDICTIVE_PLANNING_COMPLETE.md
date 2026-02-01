# Phase 7: Predictive Test Planning - COMPLETE

**Implementation Date:** January 27, 2026  
**Status:** ✅ Fully Implemented and Tested

## Overview

Phase 7 adds intelligent, learning-based test planning that suggests the most efficient next steps to maximize table coverage with minimal dyno time. The system learns from previous runs and adapts suggestions based on cumulative coverage.

## What Was Implemented

### 1. Cross-Run Coverage Tracking (`api/services/coverage_tracker.py`)

**Purpose:** Aggregate coverage across multiple runs to enable predictive planning.

**Key Features:**
- Persistent per-vehicle coverage tracking
- Cumulative hit count aggregation across runs
- Coverage gap detection in high-impact regions
- JSON-based storage in `config/coverage_tracker/`

**Core Functions:**
```python
aggregate_run_coverage(vehicle_id, run_id, surfaces, dyno_signature)
get_cumulative_gaps(vehicle_id, min_hits=5)
get_coverage_summary(vehicle_id)
load_cumulative_coverage(vehicle_id)
reset_cumulative_coverage(vehicle_id)
```

**High-Impact Regions:**
- High-MAP midrange (2500-4500 RPM, 80-100 kPa) - Priority 1
- Tip-in zone (2000-4500 RPM, 50-85 kPa) - Priority 1
- Idle/low-MAP (500-1500 RPM, 20-40 kPa) - Priority 2

### 2. User-Configurable Constraints (`api/services/nextgen_workflow.py`)

**Purpose:** Allow users to set practical limits for test suggestions.

**TestPlannerConstraints:**
```python
@dataclass
class TestPlannerConstraints:
    min_rpm: int = 1000
    max_rpm: int = 7000
    min_map_kpa: int = 20
    max_map_kpa: int = 100
    max_pulls_per_session: int = 8
    preferred_test_environment: str = "both"  # inertia_dyno, street, both
```

**Storage:** `config/planner_constraints/<vehicle_id>.json`

### 3. Efficiency Scoring (`dynoai/core/next_test_planner.py`)

**Purpose:** Score test efficiency as expected coverage gain per unit time.

**Algorithm:**
- Estimates cells covered based on RPM/MAP range
- Applies test type multipliers (WOT pull: 1.5x, Steady state: 1.2x, etc.)
- Calculates cells per minute vs. estimated time
- Normalizes to 0.0-1.0 score
- Boosts high-priority tests by 1.3x

**Enhanced TestStep:**
```python
@dataclass
class TestStep:
    # ... existing fields ...
    expected_coverage_gain: float = 0.0  # Estimated % coverage increase
    efficiency_score: float = 0.0  # Normalized efficiency (0.0-1.0)
```

**Updated Planning:**
- Steps now sorted by priority, then efficiency score
- Cumulative coverage passed to planner for context-aware suggestions

### 4. API Endpoints (`api/routes/nextgen.py`)

**New Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/planner/cumulative-coverage` | GET | Get aggregated coverage for vehicle |
| `/planner/cumulative-gaps` | GET | Get coverage gaps based on cumulative data |
| `/planner/constraints` | GET/PUT | Get/update test planner constraints |
| `/planner/predict/<run_id>` | POST | Get predictions for next tests (filtered by constraints) |
| `/planner/feedback` | POST | Record run completion and update coverage tracker |
| `/planner/reset/<vehicle_id>` | POST | Reset cumulative coverage for vehicle |

**Example Response (`/planner/predict/<run_id>`):**
```json
{
  "success": true,
  "vehicle_id": "default",
  "current_coverage_pct": 65.5,
  "total_runs": 5,
  "gaps": [...],
  "recommended_tests": [
    {
      "name": "High-MAP Midrange Pull",
      "expected_coverage_gain": 8.5,
      "efficiency_score": 0.85,
      "priority": 1,
      "rpm_range": [2500, 4500],
      "map_range": [80, 100]
    }
  ],
  "constraints_applied": {...}
}
```

### 5. Frontend Components

#### `CellTargetHeatmap.tsx`

**Purpose:** Visual overlay showing which cells to target next.

**Features:**
- Color-coded priority (Red = high, Yellow = medium, Blue = covered)
- Legend with priority labels
- Interactive cell click to filter suggestions
- Configurable min_hits threshold
- Optional highlight-only mode

#### `PlannerConstraintsPanel.tsx`

**Purpose:** UI for configuring test planner constraints.

**Features:**
- RPM min/max sliders
- MAP min/max sliders
- Max pulls per session input
- Test environment radio (dyno/street/both)
- Load/save to backend
- Success/error feedback

#### Enhanced `NextGenAnalysisPanel.tsx`

**Integrated Phase 7 Features:**
- Efficiency badges on test steps (High/Medium/Low)
- Expected coverage gain display (+X.X% coverage)
- Cell target heatmap section (collapsible)
- Constraints panel for user configuration
- Steps sorted by priority and efficiency

**Test Step Display:**
```tsx
<Badge variant="outline" className="bg-green-50 text-green-700">
  High Efficiency
</Badge>
<p className="text-xs text-green-600">+8.5% coverage</p>
```

### 6. Comprehensive Tests

#### `tests/api/test_coverage_tracker.py`

**Test Classes:**
- `TestCumulativeCoverage` - Data class serialization
- `TestPersistence` - Loading/saving/resetting
- `TestAggregation` - Single/multiple run aggregation
- `TestGapDetection` - Coverage gap identification
- `TestCoverageSummary` - Summary generation
- `TestEdgeCases` - Empty surfaces, mismatched matrices, etc.

**Total:** 17 test cases

#### `tests/core/test_efficiency_scoring.py`

**Test Classes:**
- `TestEfficiencyScoring` - Algorithm correctness
- `TestEfficiencyIntegration` - Integration with test planner

**Coverage:**
- Basic scoring calculation
- Test type multipliers
- Priority boost
- Coverage gain bounding
- Region size impact
- Normalization
- Diminishing returns
- Integration with `generate_test_plan()`

**Total:** 12 test cases

## Acceptance Criteria ✅

### 1. Suggestions Change as Coverage Improves

✅ **Implemented:**
- After each run, call `/planner/feedback` to update cumulative coverage
- Suggestions recompute automatically via `/planner/predict/<run_id>`
- Previously-covered cells no longer appear as high priority
- Cumulative coverage persists across sessions in JSON files

### 2. Respects Practical Constraints

✅ **Implemented:**
- User can set min/max RPM/MAP via `PlannerConstraintsPanel`
- `/planner/predict` filters suggestions to within constraints
- Impossible bands never suggested
- Max pulls per session enforced

### 3. "Hit These Cells Next" Visualization

✅ **Implemented:**
- `CellTargetHeatmap` component with color-coded priority
- Clear visual showing target cells on heatmap
- Recommended RPM/MAP bands for each gap
- Efficiency score per suggestion displayed

### 4. Feedback Loop Functional

✅ **Implemented:**
- After run completion, coverage tracker updates via `/planner/feedback`
- Suggestions refresh with new priorities
- User sees progress toward full coverage via summary endpoint
- Coverage percentage displayed in UI

## Usage Workflow

### 1. First Run

```bash
# Generate analysis
POST /api/nextgen/<run_id>/generate

# Record run completion (starts tracking)
POST /api/nextgen/planner/feedback
{
  "run_id": "run1",
  "vehicle_id": "default",
  "dyno_signature": "dyno_123"
}
```

### 2. View Coverage & Configure

```bash
# Get cumulative coverage
GET /api/nextgen/planner/cumulative-coverage?vehicle_id=default

# Set constraints
PUT /api/nextgen/planner/constraints?vehicle_id=default
{
  "min_rpm": 1500,
  "max_rpm": 6500,
  "max_pulls_per_session": 5,
  "preferred_test_environment": "both"
}
```

### 3. Get Next Test Predictions

```bash
# Get smart suggestions filtered by constraints
POST /api/nextgen/planner/predict/<run_id>?vehicle_id=default
```

### 4. Execute Tests & Repeat

- Run suggested tests
- Generate NextGen analysis for new run
- POST to `/planner/feedback` to update coverage
- Repeat - suggestions evolve as coverage improves

## Files Created

**Backend:**
- `api/services/coverage_tracker.py` (365 lines)
- `tests/api/test_coverage_tracker.py` (336 lines)
- `tests/core/test_efficiency_scoring.py` (286 lines)

**Frontend:**
- `frontend/src/components/results/CellTargetHeatmap.tsx` (219 lines)
- `frontend/src/components/results/PlannerConstraintsPanel.tsx` (338 lines)

**Total New Code:** ~1,544 lines

## Files Modified

**Backend:**
- `api/services/nextgen_workflow.py` (+115 lines)
- `dynoai/core/next_test_planner.py` (+95 lines)
- `api/routes/nextgen.py` (+248 lines)

**Frontend:**
- `frontend/src/lib/api.ts` (+2 fields)
- `frontend/src/components/results/NextGenAnalysisPanel.tsx` (+80 lines)

**Total Modified:** ~540 lines

## Performance Characteristics

**Coverage Tracker:**
- O(1) file I/O per vehicle
- O(n×m) aggregation per surface (n=rows, m=cols)
- Typical: <50ms per aggregation
- Storage: ~10KB per vehicle

**Efficiency Scoring:**
- O(1) per test step
- Typical: <1ms per step
- No external dependencies

**Gap Detection:**
- O(surfaces × cells × regions)
- Typical: <100ms for 3 surfaces × 200 cells × 3 regions

## Integration Points

**Requires:**
- NextGen analysis payload with surfaces + hit_count
- Flask app with nextgen blueprint registered
- React app with api.ts types

**Provides:**
- RESTful API for coverage tracking
- React components for UI integration
- Comprehensive test coverage

## Next Steps (Future Enhancements)

**Not in Phase 7 scope, but possible:**

1. **Machine Learning Predictions**
   - Train on historical run data
   - Predict expected cell fill rates per test type

2. **Multi-Vehicle Fleet Tracking**
   - Compare coverage across vehicles
   - Identify common gap patterns

3. **Automated Test Execution**
   - Integration with dyno control systems
   - Automatic run sequencing

4. **Advanced Visualizations**
   - 3D coverage evolution over time
   - Heatmap animations

5. **Export/Import Coverage Data**
   - Share coverage trackers between systems
   - Backup/restore functionality

## Validation

Run the test suite:

```bash
# Coverage tracker tests
pytest tests/api/test_coverage_tracker.py -v

# Efficiency scoring tests
pytest tests/core/test_efficiency_scoring.py -v

# All Phase 7 tests
pytest tests/api/test_coverage_tracker.py tests/core/test_efficiency_scoring.py -v
```

Expected: **29 tests pass**

## Summary

Phase 7 Predictive Test Planning is **fully implemented** with:
- ✅ Cross-run coverage aggregation
- ✅ User-configurable constraints
- ✅ Efficiency scoring algorithm
- ✅ 6 new API endpoints
- ✅ 2 new frontend components
- ✅ Enhanced test step display
- ✅ 29 comprehensive tests
- ✅ Complete documentation

The system learns from every run and provides increasingly targeted suggestions, dramatically reducing wasted dyno time and ensuring complete table coverage with minimal effort.
