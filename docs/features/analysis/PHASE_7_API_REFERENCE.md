# Phase 7 API Reference

Complete API reference for the Predictive Test Planning system.

## Base URL

All endpoints are prefixed with `/api/nextgen/planner/`

Example: `http://localhost:5001/api/nextgen/planner/cumulative-coverage`

## Authentication

Currently no authentication required (local development). Production deployments should add authentication middleware.

## Common Parameters

### Query Parameters

- `vehicle_id` (string, default: "default") - Unique identifier for the vehicle

## Endpoints

### Coverage Tracking

#### `GET /cumulative-coverage`

Get aggregated coverage statistics for a vehicle across all runs.

**Query Parameters:**
- `vehicle_id` (optional, default: "default")

**Response:** `200 OK`
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
  "last_updated": "2026-01-27T15:30:00Z",
  "created_at": "2026-01-20T10:00:00Z"
}
```

**Error Responses:**
- `404 Not Found` - No coverage data exists for this vehicle

**Example:**
```bash
curl http://localhost:5001/api/nextgen/planner/cumulative-coverage?vehicle_id=supra_001
```

---

#### `GET /cumulative-gaps`

Get coverage gaps based on cumulative data across all runs.

**Query Parameters:**
- `vehicle_id` (optional, default: "default")
- `min_hits` (optional, default: 5) - Minimum hit count threshold

**Response:** `200 OK`
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
    },
    {
      "surface_id": "spark_f",
      "region_name": "tip_in_zone",
      "rpm_range": [2000, 4500],
      "map_range": [50, 85],
      "empty_cells": 18,
      "total_cells": 30,
      "coverage_pct": 40.0,
      "impact": "high",
      "description": "Tip-in transition zone - transient fueling sensitive"
    }
  ],
  "gap_count": 2
}
```

**Example:**
```bash
curl "http://localhost:5001/api/nextgen/planner/cumulative-gaps?vehicle_id=supra_001&min_hits=3"
```

---

### Constraints Configuration

#### `GET /constraints`

Get current test planner constraints for a vehicle.

**Query Parameters:**
- `vehicle_id` (optional, default: "default")

**Response:** `200 OK`
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

**Example:**
```bash
curl http://localhost:5001/api/nextgen/planner/constraints?vehicle_id=supra_001
```

---

#### `PUT /constraints`

Update test planner constraints for a vehicle.

**Query Parameters:**
- `vehicle_id` (optional, default: "default")

**Request Body:**
```json
{
  "min_rpm": 1500,
  "max_rpm": 6500,
  "min_map_kpa": 30,
  "max_map_kpa": 100,
  "max_pulls_per_session": 5,
  "preferred_test_environment": "inertia_dyno"
}
```

**Field Descriptions:**
- `min_rpm` (int) - Minimum RPM for test suggestions
- `max_rpm` (int) - Maximum RPM for test suggestions
- `min_map_kpa` (int) - Minimum MAP (kPa) for test suggestions
- `max_map_kpa` (int) - Maximum MAP (kPa) for test suggestions
- `max_pulls_per_session` (int) - Maximum number of test suggestions to return
- `preferred_test_environment` (string) - One of: "inertia_dyno", "street", "both"

**Response:** `200 OK`
```json
{
  "success": true,
  "vehicle_id": "supra_001",
  "constraints": {
    "min_rpm": 1500,
    "max_rpm": 6500,
    "min_map_kpa": 30,
    "max_map_kpa": 100,
    "max_pulls_per_session": 5,
    "preferred_test_environment": "inertia_dyno"
  }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid constraint values
- `500 Internal Server Error` - Failed to save constraints

**Example:**
```bash
curl -X PUT http://localhost:5001/api/nextgen/planner/constraints?vehicle_id=supra_001 \
  -H "Content-Type: application/json" \
  -d '{
    "min_rpm": 1500,
    "max_rpm": 6500,
    "max_pulls_per_session": 5,
    "preferred_test_environment": "inertia_dyno"
  }'
```

---

### Predictions

#### `POST /predict/<run_id>`

Get smart test predictions filtered by user constraints.

**Path Parameters:**
- `run_id` (string, required) - The run ID to base predictions on

**Query Parameters:**
- `vehicle_id` (optional, default: "default")

**Response:** `200 OK`
```json
{
  "success": true,
  "vehicle_id": "supra_001",
  "current_coverage_pct": 65.0,
  "total_runs": 5,
  "gaps": [
    {
      "surface_id": "spark_f",
      "region_name": "high_map_midrange",
      "rpm_range": [2500, 4500],
      "map_range": [80, 100],
      "empty_cells": 12,
      "total_cells": 20,
      "coverage_pct": 40.0,
      "impact": "high"
    }
  ],
  "recommended_tests": [
    {
      "name": "High-MAP Midrange Pull",
      "goal": "Fill torque peak and knock-sensitive region",
      "rpm_range": [2500, 4500],
      "map_range": [80, 100],
      "test_type": "wot_pull",
      "constraints": "Use 3rd or 4th gear; maintain consistent ramp rate",
      "required_channels": ["rpm", "map", "afr_meas", "spark"],
      "success_criteria": "≥3 samples per cell in target region",
      "risk_notes": "",
      "priority": 1,
      "expected_coverage_gain": 8.5,
      "efficiency_score": 0.85
    }
  ],
  "constraints_applied": {
    "min_rpm": 1500,
    "max_rpm": 6500,
    "max_pulls_per_session": 5,
    "preferred_test_environment": "inertia_dyno"
  }
}
```

**Test Step Fields:**
- `name` (string) - Human-readable test name
- `goal` (string) - Purpose of the test
- `rpm_range` ([int, int] | null) - RPM range to target
- `map_range` ([int, int] | null) - MAP range to target (kPa)
- `test_type` (string) - One of: "wot_pull", "steady_state_sweep", "transient_rolloff", "idle_hold", "general"
- `constraints` (string) - Execution constraints and notes
- `required_channels` ([string]) - Channels needed for this test
- `success_criteria` (string) - How to know the test succeeded
- `risk_notes` (string) - Safety or risk considerations
- `priority` (int) - Priority level (1=highest)
- `expected_coverage_gain` (float) - Expected % coverage increase
- `efficiency_score` (float) - Normalized efficiency (0.0-1.0)

**Error Responses:**
- `404 Not Found` - No coverage data or run not found

**Example:**
```bash
curl -X POST http://localhost:5001/api/nextgen/planner/predict/run5?vehicle_id=supra_001
```

---

### Feedback Loop

#### `POST /feedback`

Record run completion and update cumulative coverage tracker.

**Request Body:**
```json
{
  "run_id": "run6",
  "vehicle_id": "supra_001",
  "dyno_signature": "dynojet_001"
}
```

**Field Descriptions:**
- `run_id` (string, required) - Run identifier that was just completed
- `vehicle_id` (string, required) - Vehicle identifier
- `dyno_signature` (string, optional, default: "unknown") - Dyno/provider signature

**Response:** `200 OK`
```json
{
  "success": true,
  "vehicle_id": "supra_001",
  "run_id": "run6",
  "total_runs": 6,
  "new_coverage_pct": 72.5,
  "message": "Coverage updated for vehicle supra_001"
}
```

**Error Responses:**
- `400 Bad Request` - Missing required fields or invalid data
- `404 Not Found` - Run not found or not analyzed

**Example:**
```bash
curl -X POST http://localhost:5001/api/nextgen/planner/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "run6",
    "vehicle_id": "supra_001",
    "dyno_signature": "dynojet_001"
  }'
```

---

#### `POST /reset/<vehicle_id>`

Reset cumulative coverage for a vehicle (start fresh).

**Path Parameters:**
- `vehicle_id` (string, required) - Vehicle identifier

**Response:** `200 OK`
```json
{
  "success": true,
  "vehicle_id": "supra_001",
  "message": "Coverage tracker reset for supra_001"
}
```

**Error Responses:**
- `500 Internal Server Error` - Failed to reset coverage

**Example:**
```bash
curl -X POST http://localhost:5001/api/nextgen/planner/reset/supra_001
```

⚠️ **Warning:** This operation is irreversible. All coverage history for the vehicle will be lost.

---

## Data Types

### TestPlannerConstraints

```typescript
interface TestPlannerConstraints {
  min_rpm: number;          // Minimum RPM (e.g., 1000)
  max_rpm: number;          // Maximum RPM (e.g., 7000)
  min_map_kpa: number;      // Minimum MAP in kPa (e.g., 20)
  max_map_kpa: number;      // Maximum MAP in kPa (e.g., 100)
  max_pulls_per_session: number;  // Max test suggestions (e.g., 8)
  preferred_test_environment: 'inertia_dyno' | 'street' | 'both';
}
```

### CoverageGap

```typescript
interface CoverageGap {
  surface_id: string;           // e.g., "spark_f"
  region_name: string;          // e.g., "high_map_midrange"
  rpm_range: [number, number];  // e.g., [2500, 4500]
  map_range: [number, number];  // e.g., [80, 100]
  empty_cells: number;          // Number of cells below min_hits
  total_cells: number;          // Total cells in region
  coverage_pct: number;         // Coverage percentage (0-100)
  impact: 'high' | 'medium' | 'low';
  description: string;          // Human-readable description
}
```

### TestStep

```typescript
interface TestStep {
  name: string;
  goal: string;
  rpm_range: [number, number] | null;
  map_range: [number, number] | null;
  test_type: 'wot_pull' | 'steady_state_sweep' | 'transient_rolloff' | 'idle_hold' | 'general';
  constraints: string;
  required_channels: string[];
  success_criteria: string;
  risk_notes: string;
  priority: number;                // 1 = highest
  expected_coverage_gain: number;  // % increase (0-100)
  efficiency_score: number;        // 0.0-1.0
}
```

## Workflow Example

### Complete Workflow

```python
import requests

BASE_URL = "http://localhost:5001/api/nextgen"
vehicle_id = "supra_001"

# 1. Run first dyno session and generate NextGen analysis
response = requests.post(f"{BASE_URL}/run1/generate")
print(f"Analysis generated: {response.json()['success']}")

# 2. Record the run to start coverage tracking
response = requests.post(
    f"{BASE_URL}/planner/feedback",
    json={
        "run_id": "run1",
        "vehicle_id": vehicle_id,
        "dyno_signature": "dynojet_001"
    }
)
print(f"Coverage: {response.json()['new_coverage_pct']}%")

# 3. Configure constraints
response = requests.put(
    f"{BASE_URL}/planner/constraints?vehicle_id={vehicle_id}",
    json={
        "min_rpm": 1500,
        "max_rpm": 6500,
        "max_pulls_per_session": 5,
        "preferred_test_environment": "both"
    }
)
print(f"Constraints saved: {response.json()['success']}")

# 4. Get smart predictions for next run
response = requests.post(
    f"{BASE_URL}/planner/predict/run1?vehicle_id={vehicle_id}"
)
predictions = response.json()
print(f"Coverage: {predictions['current_coverage_pct']}%")
print(f"Recommended tests: {len(predictions['recommended_tests'])}")

for test in predictions['recommended_tests'][:3]:
    print(f"  - {test['name']} (P{test['priority']})")
    print(f"    Efficiency: {test['efficiency_score']:.2f}")
    print(f"    Expected gain: +{test['expected_coverage_gain']:.1f}%")

# 5. Run suggested tests, then repeat from step 1
```

## Rate Limiting

No rate limiting currently implemented. Recommended limits for production:
- Coverage queries: 60/minute
- Constraint updates: 10/minute
- Predictions: 30/minute
- Feedback: 60/minute

## Error Handling

All endpoints return consistent error format:

```json
{
  "error": "Descriptive error message",
  "vehicle_id": "supra_001",
  "additional_context": "..."
}
```

Common HTTP status codes:
- `200 OK` - Success
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Storage

### File Locations

- **Coverage trackers**: `config/coverage_tracker/<vehicle_id>.json`
- **Constraints**: `config/planner_constraints/<vehicle_id>.json`

### File Format

Coverage tracker example:
```json
{
  "vehicle_id": "supra_001",
  "dyno_signature": "dynojet_001",
  "total_runs": 5,
  "run_ids": ["run1", "run2", "run3", "run4", "run5"],
  "aggregated_hit_count": {
    "spark_f": [
      [10, 15, 12, 8, 5],
      [15, 20, 18, 10, 7],
      ...
    ],
    "afr_error_f": [...]
  },
  "last_updated": "2026-01-27T15:30:00Z",
  "created_at": "2026-01-20T10:00:00Z"
}
```

## Testing

Run API integration tests:
```bash
# Phase 7 integration test
python scripts/test_phase7_integration.py

# Unit tests
pytest tests/api/test_coverage_tracker.py -v
pytest tests/core/test_efficiency_scoring.py -v
```

## Support

For API issues or questions:
1. Check logs in Flask console
2. Review test suite for usage examples
3. See [PHASE_7_USER_GUIDE.md](PHASE_7_USER_GUIDE.md) for detailed documentation
