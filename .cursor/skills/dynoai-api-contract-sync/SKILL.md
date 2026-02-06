---
name: dynoai-api-contract-sync
description: Detects and fixes type drift between Python API responses and TypeScript interfaces in the DynoAI codebase. Compares Flask route return shapes with frontend type definitions. Use when the user mentions type mismatch, API contract, sync types, type drift, or asks to update frontend types from backend or vice versa.
---

# DynoAI API Contract Sync

## Problem

Python Flask routes return dicts. TypeScript API clients expect typed interfaces. These diverge silently when:
- A field is added to a Python response but not the TS interface
- A field is renamed on one side but not the other
- A field type changes (e.g., `int` to `str`)
- Optional fields become required or vice versa

## Where Types Live

| Side | Location | Pattern |
|---|---|---|
| Python routes | `api/routes/*.py` | `return jsonify({...})` dicts |
| Python services | `api/services/*.py` | Return dicts or dataclasses |
| Python models | `api/models/*.py` | SQLAlchemy models |
| TS API clients | `frontend/src/api/*.ts` | Exported interfaces |
| TS shared types | `frontend/src/lib/api.ts` | Inline interfaces |
| TS domain types | `frontend/src/types/*.ts` | Exported interfaces |
| TS lib types | `frontend/src/lib/types.ts` | `ManifestData`, `AnalysisStatus`, `VEData` |

## Sync Workflow

### Step 1: Identify the Endpoint

Determine which endpoint has drifted. Common triggers:
- Runtime error: "property X does not exist on type Y"
- New backend field not showing in frontend
- User reports missing data in UI

### Step 2: Read the Python Source of Truth

Read the Flask route to extract the response shape:

```
1. Open api/routes/<feature>.py
2. Find the endpoint function
3. Trace the return jsonify({...}) call
4. If it calls a service, trace into api/services/<feature>.py
5. Document every field, its Python type, and whether it's optional
```

**Python-to-TypeScript type mapping:**

| Python | TypeScript | Notes |
|---|---|---|
| `str` | `string` | |
| `int` | `number` | |
| `float` | `number` | |
| `bool` | `boolean` | |
| `None` | `null` | |
| `dict` | `Record<string, unknown>` | Or a typed interface |
| `list[str]` | `string[]` | |
| `Optional[str]` | `string \| null` | Or `string?` if absent vs null |
| `datetime` (serialized) | `string` | ISO 8601 format |
| `Enum.value` | String literal union | `"pending" \| "complete" \| "error"` |

### Step 3: Compare with TypeScript Interface

Read the corresponding TS interface and diff:

```
1. Open frontend/src/api/<feature>.ts (or frontend/src/lib/api.ts)
2. Find the response interface
3. Compare field-by-field with Python response
4. Mark: MATCH, MISSING_IN_TS, MISSING_IN_PY, TYPE_MISMATCH
```

### Step 4: Generate Updated TypeScript

Update the TS interface to match the Python source of truth. Rules:

1. **Python is source of truth** for response shapes (backend owns the contract)
2. **TypeScript is source of truth** for request shapes (frontend owns what it sends)
3. **Add fields as optional** (`field?: type`) if they were recently added to Python and might not be present in older API responses
4. **Preserve JSDoc comments** on existing fields
5. **Keep the interface in its current file** -- don't move types between files during sync

### Step 5: Verify Consumers

After updating the interface, check all consumers:

```
Search for: the interface name and the API function name
Files to check: frontend/src/hooks/, frontend/src/components/, frontend/src/pages/
Fix: any property access that doesn't match the updated interface
```

## Common Sync Scenarios

### Scenario A: New field added to Python response

```python
# Python added "convergence_rate" to response
return jsonify({
    "status": "complete",
    "results": {...},
    "convergence_rate": 0.85,  # NEW
})
```

Fix: Add to TS interface as optional (backward compat):

```typescript
export interface AnalysisResult {
  status: string;
  results: Record<string, unknown>;
  convergence_rate?: number;  // Added in v1.3
}
```

### Scenario B: Python field renamed

```python
# "error_msg" renamed to "error_message"
return jsonify({"error_message": str(e)})  # was "error_msg"
```

Fix: Update TS interface, then search-and-replace all usages of the old field name in frontend code.

### Scenario C: Nested object shape changed

```python
# "results" changed from flat dict to nested structure
return jsonify({
    "results": {
        "summary": {...},     # was flat fields
        "details": {...},     # was flat fields
    }
})
```

Fix: Create nested TS interfaces:

```typescript
export interface ResultsSummary {
  // summary fields
}

export interface ResultsDetails {
  // detail fields
}

export interface AnalysisResult {
  results: {
    summary: ResultsSummary;
    details: ResultsDetails;
  };
}
```

## Bulk Audit Checklist

When auditing all API contracts at once:

```
Audit Progress:
- [ ] /api/analyze (app.py -> lib/api.ts)
- [ ] /api/status/<run_id> (app.py -> lib/api.ts)
- [ ] /api/ve-data/<run_id> (app.py -> lib/api.ts)
- [ ] /api/apply (app.py -> lib/api.ts)
- [ ] /api/rollback (app.py -> lib/api.ts)
- [ ] /api/jetstream/* (routes/jetstream.py -> api/jetstream.ts)
- [ ] /api/timeline/* (routes/timeline.py -> api/timeline.ts)
- [ ] /api/wizards/* (routes/wizards.py -> api/wizards.ts)
- [ ] /api/jetdrive/* (routes/jetdrive.py -> hooks/useJetDriveLive.ts)
- [ ] /api/virtual-tune/* (routes/virtual_tune.py -> api or hooks)
- [ ] /api/transient/* (routes/transient.py -> api/transient.ts)
- [ ] /api/ea/* (routes/engine_analyzer.py -> api or hooks)
- [ ] /api/nextgen/* (routes/nextgen.py -> lib/api.ts)
- [ ] /api/reports/* (routes/reports.py -> api/reports.ts)
- [ ] /api/powercore/* (routes/powercore.py -> lib/api.ts)
```

## Prevention

To prevent future drift, when adding a new endpoint:

1. Define the response shape in Python first (even as a comment or dataclass)
2. Create the TS interface before writing the API client function
3. Use the `dynoai-fullstack-feature` skill which generates both sides together
