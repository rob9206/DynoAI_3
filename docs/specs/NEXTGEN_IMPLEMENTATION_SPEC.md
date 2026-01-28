# DynoAI NextGen Workflow Implementation Specification

**Spark/Fuel Coupling + Cause Tree + Next-Test Planner**

This document specifies the file-by-file implementation plan for integrating physics-informed ECU reasoning into DynoAI_3, enabling next-generation tuning workflows with deterministic analysis, causal diagnosis, and intelligent test planning.

---

## 1. Integration Overview

### 1.1 Executive Summary

DynoAI_3 already contains most primitives needed for advanced ECU analysis including VE math, weighted binning, transient analysis, heat soak analysis, knock optimization, diagnostics file serving, and a reusable heatmap UI. The missing piece is a unifying analysis contract that transforms logs into:

- Consistent RPM/MAP surfaces
- Higher-level findings like WOT spark valley and rear-cylinder knock dominance
- A deterministic cause tree
- A next-test plan that can be executed on dyno or road to reduce uncertainty

This contract becomes the input to any LLM narration layer and to training data collection, while maintaining DynoAI's core guarantees of deterministic, reproducible, bit-for-bit consistent outputs.

### 1.2 Minimal Vertical Slice Goal

The first deliverable generates and displays a NextGen analysis panel on any completed run that includes:

- Spark valley summary for front versus rear plus a spark surface heatmap at high MAP
- Knock activity surface with rate or intensity proxy plus valley band detection
- A cause tree list showing hypotheses with confidence and evidence
- A next-test plan list with high-level logging-focused tests

This can be delivered without changing the existing VE correction math or the existing auto-tune workflow. It is additive: it reads the run's input CSV and writes one JSON artifact to the run output directory.

---

## 2. Data Contract: Canonical Signals

### 2.1 Required Channels

The NextGen slice requires the following canonical columns from input data:

| Channel | Description | Unit |
|---------|-------------|------|
| `rpm` | Engine speed | RPM |
| `map_kpa` | Manifold absolute pressure | kPa |
| `tps` | Throttle position | % |
| `iat` | Intake air temperature | °C |
| `ect` | Engine coolant temperature | °C |
| `afr_meas_f` | Measured AFR front cylinder | ratio |
| `afr_meas_r` | Measured AFR rear cylinder | ratio |
| `spark_f` | Spark timing front cylinder | °BTDC |
| `spark_r` | Spark timing rear cylinder | °BTDC |
| `knock` | Knock sensor activity | varies |

### 2.2 Graceful Degradation

If some channels are missing, the NextGen analyzer degrades gracefully:

- If no per-cylinder channels are available, it builds single cylinder surfaces and marks confidence lower
- If no knock channel is present, it still builds spark surfaces but disables knock-valley reasoning
- Missing optional channels reduce confidence in related hypotheses but do not prevent analysis

---

## 3. New Core Modules: File-by-File Plan

### 3.1 `dynoai/core/log_normalizer.py`

**Purpose:** Normalize different upstream data sources into the canonical columns defined above.

**Functions:**
- `normalize_dataframe(df: pd.DataFrame)` returns `pd.DataFrame` with consistent lower_snake_case columns
- `detect_and_rename_columns(df)` uses existing Power Vision channel mappings from `api/services/powercore_integration.py`

**Output:** Consistent columns including `rpm`, `map_kpa`, `tps`, `iat`, `afr_meas_f`, `spark_f`, `knock`, etc.

### 3.2 `dynoai/core/mode_detection.py`

**Purpose:** Label samples into operating modes for targeted surfaces and features including idle/low MAP stability, tip-in transient windows, and WOT/high MAP regions.

**New Dataclasses and Enums:**

```python
class ModeTag(Enum):
    IDLE = "idle"
    CRUISE = "cruise"
    TIP_IN = "tip_in"
    TIP_OUT = "tip_out"
    WOT = "wot"
    DECEL = "decel"
    HEAT_SOAK = "heat_soak"

@dataclass
class ModeDetectionConfig:
    tps_wot_threshold: float
    map_wot_threshold: float
    rpm_idle_ceiling: float
    tps_idle_ceiling: float
    map_idle_ceiling: float
    tpsdot_tipin_threshold: float
    mapdot_tipin_threshold: float
    sample_time_col: str = "index-based dt"  # optional

@dataclass
class ModeLabeledFrame:
    df: pd.DataFrame  # with added mode columns
    summary_counts: dict
```

**API:** `label_modes(df, config)` returns `ModeLabeledFrame`. Implementation must be deterministic and threshold-based with no machine learning in v1.

### 3.3 `dynoai/core/surface_builder.py`

**Purpose:** Build reusable RPM/MAP surfaces using the existing weighted_binning utilities, providing a unified format for all grid-based analysis.

**New Dataclasses:**

```python
@dataclass
class SurfaceAxis:
    name: str
    unit: str
    bins: list[float]

@dataclass
class SurfaceStats:
    min: float
    max: float
    mean: float
    p05: float
    p95: float
    non_nan_cells: int
    total_samples: int

@dataclass
class Surface2D:
    surface_id: str
    title: str
    description: str
    rpm_axis: SurfaceAxis
    map_axis: SurfaceAxis
    values: list[list[float | None]]  # nested list
    hit_count: list[list[int]]
    stats: SurfaceStats
    mask_info: str | None = None  # which modes were included

@dataclass
class SurfaceSpec:
    value_expr: Callable | str  # callable or column name
    filter_expr: Callable  # returns mask
    agg: str  # "mean" | "max" | "min" | "p95" | "rate"
    weighting: WeightingStrategy  # UniformWeighting or LogarithmicWeighting
    min_samples_per_cell: int
```

**Functions:** `build_surface(df, spec, rpm_bins, map_bins)` returns `Surface2D`. This unifies everything into the same surface format the UI can render.

### 3.4 `dynoai/core/spark_valley.py`

**Purpose:** Detect and describe the WOT spark valley behavior for front and rear cylinders, relating it to knock and airmass proxies.

**New Dataclasses:**

```python
@dataclass
class SparkValleyFinding:
    cylinder: str  # "front" | "rear" | "global"
    rpm_center: float
    rpm_band: tuple[float, float]  # (low, high)
    depth_deg: float  # peak-to-valley
    valley_min_deg: float
    pre_valley_deg: float
    post_valley_deg: float
    map_band_used: float
    confidence: float
    evidence: list[str]
```

**Functions:**
- `detect_spark_valley(surface_spark: Surface2D, high_map_min_kpa: float)` returns `list[SparkValleyFinding]`

**Detection Algorithm:**

The detector must be robust to noise. It uses a smoothed curve across RPM at high MAP by averaging the last 2-3 MAP bins. It finds a midrange minimum bracketed by higher timing on each side if present. Confidence decreases if coverage is sparse.

### 3.5 `dynoai/core/cause_tree.py`

**Purpose:** Deterministic hypothesis generation from surfaces plus mode summaries plus existing analyzers.

**New Dataclasses:**

```python
@dataclass
class Hypothesis:
    hypothesis_id: str
    title: str
    confidence: float  # 0.0 to 1.0
    category: str  # "transient" | "load_signal" | "knock_limit" | "temp_trim" | "fuel_model"
    evidence: list[str]
    distinguishing_checks: list[str]  # what to log or compare next

@dataclass
class CauseTreeResult:
    hypotheses: list[Hypothesis]
    summary: str
```

**Inputs:**
- `ModeLabeledFrame` summary from mode_detection
- `TransientFuelResult` from `dynoai/core/transient_fuel.py` if available
- `HeatProfile` and `SoakEvents` from `dynoai/core/heat_management.py` if used
- Surfaces including spark, knock, and afr_error

**Output:** The same symptom-to-causes-to-distinguishing-observations logic from the ECU model document, expressed as stable objects DynoAI can render and store.

### 3.6 `dynoai/core/next_test_planner.py`

**Purpose:** Produce a prioritized next run plan that reduces uncertainty and increases coverage where it matters.

**New Dataclasses:**

```python
@dataclass
class TestStep:
    name: str
    goal: str
    constraints: str
    required_channels: list[str]
    success_criteria: str
    risk_notes: str

@dataclass
class NextTestPlan:
    steps: list[TestStep]
    priority_rationale: str
```

**Logic:**

Uses `hit_count` matrices to find low-coverage but high-impact cells including high MAP midrange, idle low MAP, and tip-in transition zones. If cause_tree includes transient lean tip-in, proposes a controlled roll-on sweep with logging emphasis rather than any calibration action.

### 3.7 `dynoai/core/nextgen_payload.py`

**Purpose:** A single stable JSON schema for everything NextGen produces.

**New Dataclasses:**

```python
@dataclass
class NextGenAnalysisPayload:
    schema_version: str  # "dynoai.nextgen@1"
    run_id: str
    generated_at: str
    inputs_present: dict[str, bool]
    mode_summary: dict
    surfaces: dict[str, Surface2D]
    spark_valley: list[SparkValleyFinding]
    cause_tree: CauseTreeResult
    next_tests: NextTestPlan
    notes_warnings: list[str]
    
    def to_dict(self) -> dict:
        """JSON serialization"""
        ...
```

---

## 4. New Service Layer: API File-by-File Plan

### 4.1 `api/services/nextgen_workflow.py`

**Purpose:** Orchestration around runs and caching.

**Class NextGenWorkflow:**

```python
class NextGenWorkflow:
    def generate_for_run(self, run_id: str, force: bool = False) -> NextGenAnalysisPayload:
        ...
    
    def load_cached(self, run_id: str) -> Optional[NextGenAnalysisPayload]:
        ...
    
    def resolve_input_path(self, run_id: str) -> str:
        # Prefers Jetstream RunManager via api/services/run_manager.py get_run_input_path()
        # Fallback to OUTPUT_FOLDER/run_id/input.csv conventions
        ...
```

**Write Outputs:**
- `NextGenAnalysis.json` containing the full payload
- `NextGenAnalysis_Meta.json` containing version, columns, row count, and sha256

### 4.2 `api/routes/nextgen.py`

**Purpose:** New blueprint providing endpoints consistent with existing diagnostics and ve-data patterns.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/nextgen/<run_id>/generate` | Generate analysis (optional `force=true`) |
| GET | `/api/nextgen/<run_id>` | Get cached payload JSON |
| GET | `/api/nextgen/<run_id>/download` | Download NextGenAnalysis.json |

**POST Response:**
```json
{
    "success": true,
    "run_id": "...",
    "generated_at": "...",
    "summary": "...",
    "download_url": "...",
    "payload": {}  // if include=full
}
```

### 4.3 `api/app.py` Modification

Register blueprint near the other analysis blueprints:

```python
from api.routes.nextgen import nextgen_bp
app.register_blueprint(nextgen_bp)
```

---

## 5. Frontend Integration: File-by-File Plan

### 5.1 `frontend/src/lib/api.ts` Modification

Add types and API calls:

```typescript
export interface NextGenAnalysisPayload {
    schema_version: string;
    run_id: string;
    generated_at: string;
    // ... UI-relevant fields
}

export const getNextGenAnalysis = (runId: string) => ...
export const generateNextGenAnalysis = (runId: string, force?: boolean) => ...
```

### 5.2 `frontend/src/hooks/useNextGenAnalysis.ts`

**Purpose:** React Query hooks for NextGen API.

- `useQuery` for GET payload
- `useMutation` for POST generate

### 5.3 `frontend/src/components/results/NextGenAnalysisPanel.tsx`

**Purpose:** Minimal UI for displaying NextGen analysis results.

**UI Elements:**

- **Generate NextGen Analysis** button calling mutation
- **Spark Valley Findings** section showing list plus key metrics
- **Cause Tree** section showing ranked hypotheses with confidence and evidence
- **Next Test Plan** section showing ordered steps
- **Heatmaps** section reusing existing VEHeatmap component for:
  - Spark surface with sequential colormap
  - Knock surface with sequential colormap if present

The existing VEHeatmap is generic enough requiring only label arrays and a matrix.

### 5.4 `frontend/src/pages/RunDetailPage.tsx` Modification

Add a new Card below existing VE sections containing `<NextGenAnalysisPanel runId={runId} />`.

---

## 6. Testing Strategy: File-by-File Plan

### 6.1 `tests/api/test_nextgen_endpoint.py`

Uses existing Flask test client patterns in `tests/api/conftest.py`. Loads the existing `dense_dyno_test.csv` as a run input fixture by copying into a temp run directory structure: `runs/<id>/input/dynoai_input.csv`.

**Validations:**
- POST generate returns 200 and writes NextGenAnalysis.json
- GET returns schema_version and expected keys
- Degrades gracefully if knock column removed (parameterized test)

### 6.2 `tests/core/test_surface_builder.py`

- Ensures `hit_count` and `values` shapes match bins
- Ensures `min_samples_per_cell` works correctly

### 6.3 `tests/core/test_spark_valley.py`

- Builds a synthetic spark surface with a known valley
- Validates detection algorithm correctly identifies valley center, depth, and bounds

---

## 7. Future Extensions

### 7.1 AI Narration Layer

Optional future PR adds `api/services/nextgen_ai_report.py` that:

1. Builds a prompt from `NextGenAnalysisPayload` including surfaces, findings, hypotheses, and next test plan
2. Uses crank-angle pressure trace conceptual model as static system context
3. Calls the existing `/api/xai/chat` path via `dynoai/api/xai_blueprint.py` or any other LLM client
4. Returns a human-readable report plus a structured AI rationale section that references evidence fields rather than raw guesses

### 7.2 Training Data Integration

Optional future PR extends `api/services/training_data_collector.py` to store:

- Detected spark valley parameters
- Cause tree hypotheses and which were confirmed or closed after subsequent runs
- Next-test outcomes

This turns DynoAI into a feedback system where each session produces labeled patterns for future assistance while keeping the core decision artifacts deterministic.

---

## 8. First PR Summary

### 8.1 New Files

- `dynoai/core/log_normalizer.py`
- `dynoai/core/mode_detection.py`
- `dynoai/core/surface_builder.py`
- `dynoai/core/spark_valley.py`
- `dynoai/core/cause_tree.py`
- `dynoai/core/next_test_planner.py`
- `dynoai/core/nextgen_payload.py`
- `api/services/nextgen_workflow.py`
- `api/routes/nextgen.py`
- `frontend/src/hooks/useNextGenAnalysis.ts`
- `frontend/src/components/results/NextGenAnalysisPanel.tsx`
- `tests/api/test_nextgen_endpoint.py` plus small core tests

### 8.2 Modified Files

- `api/app.py` to register blueprint
- `frontend/src/lib/api.ts` for API types and functions
- `frontend/src/pages/RunDetailPage.tsx` to render panel

### 8.3 Deliverable

DynoAI gains a durable internal representation of VE-spark-knock-transients coupling that is computable, inspectable, storable, and UI-renderable. Any next-gen automation including AI should consume that payload, not raw logs. The deterministic core guarantees remain intact while the system gains physics-informed reasoning about ECU behavior.

---

*End of Specification*
