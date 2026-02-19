---
name: dynoai-test-generator
description: Generates tests for the DynoAI codebase. Bootstraps Vitest and React Testing Library for frontend, generates pytest tests for backend. Provides test templates for React Query hooks, utility functions, components, Flask endpoints, and VE math. Use when the user asks to add tests, create test files, set up testing infrastructure, or improve test coverage.
---

# DynoAI Test Generator

## Quick Assessment

Before generating tests, check:

1. **Frontend testing infra exists?** Check `frontend/package.json` for `vitest`. If missing, run Step 0.
2. **Backend testing infra exists?** Check `tests/` directory and `pyproject.toml` for pytest config. Backend usually has this already.

## Step 0: Bootstrap Frontend Testing (one-time)

If `vitest` is not in `frontend/package.json`:

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/test/**", "src/**/*.d.ts"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

Create `frontend/src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom";
```

Add to `frontend/package.json` scripts:

```json
{
  "test": "vitest",
  "test:run": "vitest run",
  "test:coverage": "vitest run --coverage"
}
```

## Test Patterns by Category

### Pattern 1: Pure Utility Functions (Easiest)

Target: `frontend/src/utils/veApply/*.ts`

These are pure functions with no React dependencies -- the best place to start.

```typescript
// frontend/src/utils/veApply/__tests__/zoneClassification.test.ts
import { describe, it, expect } from "vitest";
import { classifyZone } from "../zoneClassification";

describe("classifyZone", () => {
  it("classifies cruise zone (31-69 kPa, 1200-5500 RPM)", () => {
    expect(classifyZone(3000, 50)).toBe("cruise");
  });

  it("classifies WOT zone (95+ kPa)", () => {
    expect(classifyZone(4000, 100)).toBe("wot");
  });

  it("classifies decel zone (<=30 kPa)", () => {
    expect(classifyZone(2000, 25)).toBe("decel");
  });

  it("classifies partThrottle zone (70-94 kPa)", () => {
    expect(classifyZone(3000, 80)).toBe("partThrottle");
  });

  it("classifies edge zone for low RPM", () => {
    expect(classifyZone(800, 50)).toBe("edge");
  });

  it("classifies edge zone for high RPM", () => {
    expect(classifyZone(6000, 50)).toBe("edge");
  });

  // Boundary tests
  it("handles exact boundary at 1200 RPM", () => {
    const result = classifyZone(1200, 50);
    expect(["cruise", "edge"]).toContain(result);
  });
});
```

### Pattern 2: React Query Hooks

Target: `frontend/src/hooks/use*.ts`

```typescript
// frontend/src/hooks/__tests__/useFeature.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";

// Mock the API module
vi.mock("@/api/feature", () => ({
  getFeatureStatus: vi.fn(),
  runFeatureAnalysis: vi.fn(),
}));

import { useFeature } from "../useFeature";
import { getFeatureStatus } from "@/api/feature";

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useFeature", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts in loading state", () => {
    vi.mocked(getFeatureStatus).mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useFeature(), {
      wrapper: createWrapper(),
    });
    expect(result.current.isLoadingStatus).toBe(true);
  });

  it("returns data on success", async () => {
    vi.mocked(getFeatureStatus).mockResolvedValue({ status: "ok" });
    const { result } = renderHook(() => useFeature(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.status).toEqual({ status: "ok" });
    });
  });

  it("returns error on failure", async () => {
    vi.mocked(getFeatureStatus).mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useFeature(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => {
      expect(result.current.statusError).toBeTruthy();
    });
  });
});
```

### Pattern 3: React Components

Target: `frontend/src/components/**/*.tsx`

```typescript
// frontend/src/components/__tests__/FeaturePage.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import FeaturePage from "@/pages/FeaturePage";

// Mock the hook
vi.mock("@/hooks/useFeature", () => ({
  useFeature: vi.fn(() => ({
    status: { status: "ok" },
    isLoadingStatus: false,
    statusError: null,
  })),
}));

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
};

describe("FeaturePage", () => {
  it("renders without crashing", () => {
    renderWithProviders(<FeaturePage />);
    expect(screen.getByText(/feature/i)).toBeInTheDocument();
  });

  it("shows loading spinner when loading", async () => {
    const { useFeature } = await import("@/hooks/useFeature");
    vi.mocked(useFeature).mockReturnValue({
      status: null,
      isLoadingStatus: true,
      statusError: null,
    } as ReturnType<typeof useFeature>);

    renderWithProviders(<FeaturePage />);
    // Check for loading indicator
  });
});
```

### Pattern 4: Flask API Endpoints (Backend)

Target: `tests/api/test_routes_<feature>.py`

```python
"""Tests for <feature> API endpoints."""
import json
import pytest
from api.app import create_app  # or however the app is initialized


@pytest.fixture
def app():
    """Create test app."""
    from api.app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestFeatureEndpoints:
    """Tests for /api/<feature> endpoints."""

    def test_get_status_returns_200(self, client):
        response = client.get("/api/<feature>/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "status" in data

    def test_analyze_requires_body(self, client):
        response = client.post(
            "/api/<feature>/analyze",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_analyze_with_valid_data(self, client):
        response = client.post(
            "/api/<feature>/analyze",
            data=json.dumps({"param": "value"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "complete"
```

### Pattern 5: VE Math (Backend, Property-Based)

Target: `tests/test_ve_math.py`

```python
"""Tests for VE math correctness."""
import pytest
from dynoai.core.ve_math import (
    calculate_ve_correction,
    correction_to_percentage,
    percentage_to_correction,
)


class TestVECorrection:
    """VE correction calculation tests."""

    def test_stoich_afr_gives_no_correction(self):
        """Measured == target should give correction = 1.0 (no change)."""
        result = calculate_ve_correction(14.7, 14.7)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_lean_gives_positive_correction(self):
        """Lean (measured > target) needs more fuel (correction > 1)."""
        result = calculate_ve_correction(15.5, 14.7)
        assert result > 1.0

    def test_rich_gives_negative_correction(self):
        """Rich (measured < target) needs less fuel (correction < 1)."""
        result = calculate_ve_correction(13.5, 14.7)
        assert result < 1.0

    def test_correction_clamped_to_max(self):
        """Extreme correction should be clamped."""
        result = calculate_ve_correction(20.0, 12.0, clamp=True)
        # Should be clamped to within ±15% by default
        assert 0.85 <= result <= 1.15

    @pytest.mark.parametrize("afr", [8.0, 21.0, -1.0, 0.0])
    def test_invalid_afr_raises(self, afr):
        """Invalid AFR values should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_ve_correction(afr, 14.7)

    def test_percentage_roundtrip(self):
        """correction -> percentage -> correction should be identity."""
        original = 1.077
        pct = correction_to_percentage(original)
        roundtrip = percentage_to_correction(pct)
        assert roundtrip == pytest.approx(original, abs=1e-6)
```

## Priority Order for Test Coverage

1. **`frontend/src/utils/veApply/`** -- Pure functions, highest ROI, no mocking needed
2. **`dynoai/core/ve_math.py`** -- Core math, critical correctness
3. **`frontend/src/hooks/`** -- Hook patterns, moderate complexity
4. **`api/routes/`** -- API contract tests, good regression coverage
5. **`frontend/src/components/`** -- Component render tests, lowest priority

## Test File Naming

| Layer | Pattern | Location |
|---|---|---|
| Frontend utils | `<module>.test.ts` | `frontend/src/utils/<dir>/__tests__/` |
| Frontend hooks | `<hook>.test.tsx` | `frontend/src/hooks/__tests__/` |
| Frontend components | `<Component>.test.tsx` | `frontend/src/components/<dir>/__tests__/` |
| Backend routes | `test_routes_<feature>.py` | `tests/api/` |
| Backend services | `test_<service>.py` | `tests/services/` |
| Core math | `test_ve_math.py` | `tests/` |

## Additional Resources

For more test patterns, see [test-patterns.md](test-patterns.md).
