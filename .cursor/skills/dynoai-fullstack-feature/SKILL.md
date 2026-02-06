---
name: dynoai-fullstack-feature
description: Scaffolds a new full-stack feature across the DynoAI Flask + React monorepo. Creates Flask blueprint, service module, API client, React Query hook, page component, and route registration following established project patterns. Use when the user asks to add a new feature, create a new page, add a new API endpoint with frontend, or scaffold a new module.
---

# DynoAI Full-Stack Feature Scaffolding

## When to Use

Use this skill when adding a feature that spans backend and frontend, such as:
- A new tuning wizard (e.g., Heat Soak, Decel Pop)
- A new analysis pipeline (e.g., knock detection)
- A new integration (e.g., new hardware protocol)
- A new page with its own API endpoints

## Scaffolding Checklist

Copy and track progress:

```
Feature: [FEATURE_NAME]
- [ ] Step 1: Flask Blueprint (api/routes/<feature>.py)
- [ ] Step 2: Service module (api/services/<feature>.py)
- [ ] Step 3: Register blueprint (api/app.py)
- [ ] Step 4: API client functions (frontend/src/api/<feature>.ts)
- [ ] Step 5: React Query hook (frontend/src/hooks/use<Feature>.ts)
- [ ] Step 6: Page component (frontend/src/pages/<Feature>Page.tsx)
- [ ] Step 7: Register route (frontend/src/App.tsx)
- [ ] Step 8: TypeScript types (frontend/src/types/<feature>Types.ts or inline)
```

## Step 1: Flask Blueprint

Create `api/routes/<feature>.py`:

```python
"""<Feature> API routes."""
import logging
from flask import Blueprint, jsonify, request

from api.errors import ValidationError, with_error_handling

logger = logging.getLogger(__name__)

<feature>_bp = Blueprint("<feature>", __name__, url_prefix="/api/<feature>")


@<feature>_bp.route("/status", methods=["GET"])
@with_error_handling
def get_status():
    """Get <feature> status."""
    return jsonify({"status": "ok"})


@<feature>_bp.route("/analyze", methods=["POST"])
@with_error_handling
def run_analysis():
    """Run <feature> analysis."""
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required")

    # Call service layer
    from api.services.<feature> import <Feature>Service
    result = <Feature>Service().analyze(data)

    return jsonify(result)
```

**Key patterns:**
- Always use `@with_error_handling` decorator
- Raise `ValidationError`, `NotFoundError`, etc. from `api/errors.py`
- Import services lazily inside route functions (avoids circular imports)
- Use `logger` not `print` for logging

## Step 2: Service Module

Create `api/services/<feature>.py`:

```python
"""<Feature> business logic."""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class <Feature>Config:
    """Configuration for <feature>."""
    param_a: float = 1.0
    param_b: int = 10


class <Feature>Service:
    """<Feature> analysis service."""

    def __init__(self, config: <Feature>Config | None = None):
        self.config = config or <Feature>Config()

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run <feature> analysis.

        Args:
            data: Input data dict.

        Returns:
            Results dict.
        """
        logger.info("Starting <feature> analysis")
        # Business logic here
        return {"status": "complete", "results": {}}
```

**Key patterns:**
- Dataclass for configuration
- Service class with `__init__` accepting optional config
- Type hints on all public methods
- Docstrings with Args/Returns

## Step 3: Register Blueprint

In `api/app.py`, add within the blueprint registration section:

```python
try:
    from api.routes.<feature> import <feature>_bp
    app.register_blueprint(<feature>_bp)
    print("[+] <Feature> registered at /api/<feature>")
except Exception as e:
    print(f"[!] Warning: Could not initialize <Feature>: {e}")
```

**Location:** Add after the last `register_blueprint` block, before `register_error_handlers(app)`.

## Step 4: API Client Functions

Create `frontend/src/api/<feature>.ts`:

```typescript
import api from "@/lib/api";
import { encodePathSegment } from "@/lib/sanitize";

// --- Types ---

export interface <Feature>Status {
  status: string;
}

export interface <Feature>AnalysisRequest {
  // Request fields matching Python endpoint
}

export interface <Feature>AnalysisResult {
  status: string;
  results: Record<string, unknown>;
}

// --- API Functions ---

export async function get<Feature>Status(): Promise<<Feature>Status> {
  const response = await api.get("/api/<feature>/status");
  return response.data;
}

export async function run<Feature>Analysis(
  data: <Feature>AnalysisRequest
): Promise<<Feature>AnalysisResult> {
  const response = await api.post("/api/<feature>/analyze", data);
  return response.data;
}
```

**Key patterns:**
- Import `api` from `@/lib/api` (the shared axios instance)
- Use `encodePathSegment` for any dynamic URL segments
- Export interfaces for all request/response shapes
- Each function is `async`, returns typed `Promise<T>`

## Step 5: React Query Hook

Create `frontend/src/hooks/use<Feature>.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import {
  get<Feature>Status,
  run<Feature>Analysis,
  type <Feature>AnalysisRequest,
} from "@/api/<feature>";

export function use<Feature>() {
  const queryClient = useQueryClient();

  const {
    data: status,
    isLoading: isLoadingStatus,
    error: statusError,
  } = useQuery({
    queryKey: ["<feature>", "status"],
    queryFn: get<Feature>Status,
    staleTime: 10_000,
  });

  const analysisMutation = useMutation({
    mutationFn: (data: <Feature>AnalysisRequest) => run<Feature>Analysis(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["<feature>"] });
    },
  });

  const runAnalysis = useCallback(
    (data: <Feature>AnalysisRequest) => analysisMutation.mutateAsync(data),
    [analysisMutation]
  );

  return {
    // Data
    status,

    // Loading states
    isLoadingStatus,
    isAnalyzing: analysisMutation.isPending,

    // Errors
    statusError,
    analysisError: analysisMutation.error,

    // Actions
    runAnalysis,
  };
}
```

**Key patterns:**
- `useQuery` for reads, `useMutation` for writes
- Invalidate related queries on mutation success
- Wrap actions in `useCallback`
- Return structured object: data, loading states, errors, actions

## Step 6: Page Component

Create `frontend/src/pages/<Feature>Page.tsx`:

```tsx
import { use<Feature> } from "@/hooks/use<Feature>";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

export default function <Feature>Page() {
  const { status, isLoadingStatus, statusError } = use<Feature>();

  if (isLoadingStatus) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive rounded-lg p-4">
          Failed to load: {statusError.message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold"><Feature></h1>
      <pre>{JSON.stringify(status, null, 2)}</pre>
    </div>
  );
}
```

**Key patterns:**
- Default export (required for `React.lazy`)
- Use the custom hook for all data
- Loading and error states handled first
- Tailwind classes for styling
- `space-y-6` for vertical spacing, `p-6` for page padding

## Step 7: Register Route

In `frontend/src/App.tsx`:

1. Add lazy import at the top with other lazy imports:

```typescript
const <Feature>Page = lazy(() => import("./pages/<Feature>Page"));
```

2. Add Route inside the `<Routes>` block:

```tsx
<Route path="/<feature>" element={
  <Suspense fallback={<LoadingSpinner />}>
    <<Feature>Page />
  </Suspense>
} />
```

## Step 8: Types (if complex)

If the feature has many types, create `frontend/src/types/<feature>Types.ts`:

```typescript
// Keep types co-located with API client for simple features.
// Create this file only when types are shared across multiple components.
export interface <Feature>Config {
  // ...
}
```

## Naming Conventions

| Layer | Convention | Example |
|---|---|---|
| Blueprint variable | `<feature>_bp` | `heat_soak_bp` |
| Blueprint name | `"<feature>"` | `"heat_soak"` |
| URL prefix | `/api/<feature>` | `/api/heat-soak` |
| Service class | `<Feature>Service` | `HeatSoakService` |
| API client file | `<feature>.ts` | `heatSoak.ts` |
| Hook | `use<Feature>` | `useHeatSoak` |
| Page component | `<Feature>Page` | `HeatSoakPage` |
| Route path | `/<feature>` | `/heat-soak` |

## Additional Resources

For templates with more detail, see [templates.md](templates.md).
