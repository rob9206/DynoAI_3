# DynoAI Test Patterns Reference

## Frontend: Testing VE Apply Utilities

These are the highest-ROI tests because `veApply/` contains pure functions with well-defined inputs and outputs.

### confidenceCalculator.test.ts

```typescript
import { describe, it, expect } from "vitest";
import { getClampResult, getConfidenceLevel } from "../confidenceCalculator";

describe("getClampResult", () => {
  it("returns skip for zero hits", () => {
    const result = getClampResult(3000, 50, 0);
    expect(result.confidence).toBe("skip");
    expect(result.limit).toBeNull();
  });

  it("returns low confidence for few hits in cruise zone", () => {
    const result = getClampResult(3000, 50, 5);
    expect(result.confidence).toBe("low");
    expect(result.limit).toBe(0.03); // ±3%
  });

  it("returns high confidence for many hits in cruise zone", () => {
    const result = getClampResult(3000, 50, 150);
    expect(result.confidence).toBe("high");
    expect(result.limit).toBe(0.07); // ±7%
  });

  it("uses zone-appropriate thresholds for WOT", () => {
    // WOT needs fewer hits for high confidence (30 vs 100 for cruise)
    const result = getClampResult(4000, 100, 35);
    expect(result.confidence).toBe("high");
    expect(result.zone).toBe("wot");
  });
});
```

### coverageCalculator.test.ts

```typescript
import { describe, it, expect } from "vitest";
import { calculateCoverage, getCoverageGrade } from "../coverageCalculator";

describe("calculateCoverage", () => {
  const rpmAxis = [1500, 2000, 2500, 3000, 3500];
  const mapAxis = [30, 50, 70, 90, 100];

  it("returns 0% for empty grid", () => {
    const hitCounts = Array(5).fill(null).map(() => Array(5).fill(0));
    const result = calculateCoverage(hitCounts, rpmAxis, mapAxis);
    expect(result.totalCoveragePct).toBe(0);
    expect(result.activeCells).toBe(0);
  });

  it("returns 100% for fully populated grid", () => {
    const hitCounts = Array(5).fill(null).map(() => Array(5).fill(200));
    const result = calculateCoverage(hitCounts, rpmAxis, mapAxis);
    expect(result.totalCoveragePct).toBe(100);
  });

  it("weights cruise zone higher than decel", () => {
    // Populate only cruise cells vs only decel cells
    // Cruise-only should give higher weighted coverage
  });
});

describe("getCoverageGrade", () => {
  it("grades A for 90%+", () => {
    expect(getCoverageGrade(95).grade).toBe("A");
  });

  it("grades F for under 40%", () => {
    expect(getCoverageGrade(30).grade).toBe("F");
  });
});
```

### cylinderBalance.test.ts

```typescript
import { describe, it, expect } from "vitest";
import { checkCylinderBalance } from "../cylinderBalance";

describe("checkCylinderBalance", () => {
  const rpmAxis = [2000, 3000, 4000];
  const mapAxis = [50, 70, 90];

  it("reports no bias when cylinders are identical", () => {
    const corrections = [[1.05, 1.03, 1.02], [1.04, 1.06, 1.01], [1.02, 1.03, 1.04]];
    const hitCounts = [[20, 20, 20], [20, 20, 20], [20, 20, 20]];
    const result = checkCylinderBalance(corrections, corrections, hitCounts, rpmAxis, mapAxis);
    expect(Math.abs(result.systematicBias)).toBeLessThan(0.1);
  });

  it("detects systematic rear bias", () => {
    const front = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]];
    const rear = [[1.05, 1.05, 1.05], [1.05, 1.05, 1.05], [1.05, 1.05, 1.05]];
    const hits = [[20, 20, 20], [20, 20, 20], [20, 20, 20]];
    const result = checkCylinderBalance(front, rear, hits, rpmAxis, mapAxis);
    expect(result.systematicBias).toBeGreaterThan(2);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it("excludes cells with insufficient hits", () => {
    const front = [[1.5, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]];
    const rear = [[0.5, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]];
    // First cell has only 1 hit each -- should be excluded
    const hits = [[1, 20, 20], [20, 20, 20], [20, 20, 20]];
    const result = checkCylinderBalance(front, rear, hits, rpmAxis, mapAxis);
    // The extreme cell should not affect the result
    expect(Math.abs(result.systematicBias)).toBeLessThan(1);
  });
});
```

### veApplyValidation.test.ts

```typescript
import { describe, it, expect } from "vitest";
import { validateApplyInputs, sanitizeCorrection } from "../veApplyValidation";

describe("sanitizeCorrection", () => {
  it("passes through valid corrections", () => {
    expect(sanitizeCorrection(1.05)).toBe(1.05);
  });

  it("defaults NaN to 1.0", () => {
    expect(sanitizeCorrection(NaN)).toBe(1.0);
  });

  it("defaults Infinity to 1.0", () => {
    expect(sanitizeCorrection(Infinity)).toBe(1.0);
  });

  it("defaults negative to 1.0", () => {
    expect(sanitizeCorrection(-0.5)).toBe(1.0);
  });

  it("defaults zero to 1.0", () => {
    expect(sanitizeCorrection(0)).toBe(1.0);
  });
});

describe("validateApplyInputs", () => {
  it("blocks when base VE is missing", () => {
    const result = validateApplyInputs({
      baseVE: null,
      corrections: { front: [[1.0]], rear: [[1.0]] },
      hitCounts: { front: [[10]], rear: [[10]] },
    });
    expect(result.blocked).toBe(true);
    expect(result.blockReasons.some(r => r.type === "missingBaseVE")).toBe(true);
  });

  it("blocks when only one cylinder has data", () => {
    const result = validateApplyInputs({
      baseVE: [[80]],
      corrections: { front: [[1.05]], rear: null },
      hitCounts: { front: [[10]], rear: null },
    });
    expect(result.blocked).toBe(true);
  });

  it("warns on extreme corrections", () => {
    const result = validateApplyInputs({
      baseVE: [[80]],
      corrections: { front: [[1.20]], rear: [[1.20]] },
      hitCounts: { front: [[50]], rear: [[50]] },
    });
    // 20% correction should warn but not block (block is at 25%)
    expect(result.warnings.length).toBeGreaterThan(0);
  });
});
```

## Backend: Testing Flask Routes with Fixtures

### Shared conftest.py

Create `tests/conftest.py`:

```python
"""Shared test fixtures."""
import pytest


@pytest.fixture
def app():
    """Create test Flask app."""
    from api.app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["DYNOAI_DEBUG"] = False
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_ve_grid():
    """Create a sample 3x3 VE grid for testing."""
    return {
        "rpm_axis": [2000, 3000, 4000],
        "map_axis": [50, 70, 90],
        "ve_table": [
            [75.0, 80.0, 85.0],
            [78.0, 83.0, 88.0],
            [72.0, 77.0, 82.0],
        ],
    }


@pytest.fixture
def sample_afr_data():
    """Create sample AFR analysis data."""
    return {
        "rpm_axis": [2000, 3000, 4000],
        "map_axis": [50, 70, 90],
        "afr_measured": [
            [15.2, 13.8, 13.0],
            [14.9, 13.5, 12.8],
            [15.5, 14.0, 13.2],
        ],
        "afr_target": [
            [14.7, 13.0, 12.5],
            [14.7, 13.0, 12.5],
            [14.7, 13.0, 12.5],
        ],
        "hit_counts": [
            [25, 40, 10],
            [30, 50, 15],
            [20, 35, 8],
        ],
    }
```

### Testing Virtual Tune Routes

```python
"""Tests for virtual tuning endpoints."""
import json
import pytest


class TestVirtualTuneRoutes:
    def test_health_check(self, client):
        response = client.get("/api/virtual-tune/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "orchestrator" in data

    def test_list_sessions_empty(self, client):
        response = client.get("/api/virtual-tune/sessions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data.get("sessions", []), list)

    def test_start_requires_engine_profile(self, client):
        response = client.post(
            "/api/virtual-tune/start",
            data=json.dumps({}),
            content_type="application/json",
        )
        # Should fail validation without engine profile
        assert response.status_code in (400, 422)

    def test_status_not_found(self, client):
        response = client.get("/api/virtual-tune/status/nonexistent")
        assert response.status_code == 404
```
