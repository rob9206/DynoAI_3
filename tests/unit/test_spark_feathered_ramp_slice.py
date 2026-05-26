"""End-to-end slice test for the SparkFeatheredRamp tool.

Asserts the vertical slice contract:

  1. The lifted tool produces byte-identical output to the existing seanbike
     reference patch on the canonical input (SHA equality).
  2. Running the same plan twice produces the same SHA (idempotency).
  3. plan().predicted_cells_changed == actual cells_changed in apply()
     (plan/apply parity).
  4. A plan with too-aggressive params triggers SparkClampGate and aborts
     without writing.
  5. The TuningDispatcher routes a Finding to the tool, plans, and applies
     end-to-end (the registry path).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.detectors.spark_valley import SparkValleyDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.diagnostics.finding import Finding
from dynoai.tools.spark_feathered_ramp import (
    DEFAULT_RAMP,
    SparkFeatheredRampTool,
    TOOL_NAME,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEANBIKE_SESSION = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
)
INPUT_PVV = (
    SEANBIKE_SESSION
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation_safeavg140_gpsmooth.pvv"
)
REFERENCE_INPUT_SHA = (
    "1fbaad312771bb4bebf15388d80fd7f2e25c48f2e339d0eaf38479186ae43d6e"
)
REFERENCE_OUTPUT_SHA = (
    "b5a69006943b65ec9a5c7dc647e32874908839b929c874b56024d1a8099a9a76"
)
REFERENCE_CELLS_CHANGED = 77


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def fixture_input_sha() -> str:
    assert INPUT_PVV.exists(), f"missing fixture: {INPUT_PVV}"
    sha = _sha256(INPUT_PVV)
    assert sha == REFERENCE_INPUT_SHA, (
        f"fixture drifted: got {sha}, expected {REFERENCE_INPUT_SHA}"
    )
    return sha


def _make_ctx(iter_dir: Path) -> DetectionContext:
    iter_dir.mkdir(parents=True, exist_ok=True)
    return DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
    )


def _make_finding(**overrides) -> Finding:
    params = {
        "kind": "spark_valley",
        "severity": 0.8,
        "confidence": 0.85,
        "evidence": {
            "rpm_center": 5500.0,
            "rpm_band": (5000.0, 6000.0),
            "cylinder": "front",
        },
        "suggested_tool": TOOL_NAME,
        "tool_params": {},
        "source": "spark_valley_detector",
    }
    params.update(overrides)
    return Finding(**params)


def test_lifted_tool_matches_seanbike_reference_sha(tmp_path, fixture_input_sha):
    """The new tool must produce the exact same bytes as the seanbike script.

    This guards against algorithmic drift during the lift.
    """
    tool = SparkFeatheredRampTool()
    ctx = _make_ctx(tmp_path / "iter_test")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success, f"apply failed: {result.gates_failed}"
    assert result.sha256 == REFERENCE_OUTPUT_SHA, (
        f"byte drift from seanbike reference: got {result.sha256}, "
        f"expected {REFERENCE_OUTPUT_SHA}"
    )
    assert result.cells_changed == REFERENCE_CELLS_CHANGED


def test_idempotent_apply_produces_same_sha(tmp_path, fixture_input_sha):
    """Running the same plan twice must produce identical bytes."""
    tool = SparkFeatheredRampTool()
    ctx_a = _make_ctx(tmp_path / "iter_a")
    ctx_b = _make_ctx(tmp_path / "iter_b")
    finding = _make_finding()

    result_a = tool.apply(tool.plan(finding, ctx_a), ctx_a)
    result_b = tool.apply(tool.plan(finding, ctx_b), ctx_b)

    assert result_a.success and result_b.success
    assert result_a.sha256 == result_b.sha256
    assert result_a.cells_changed == result_b.cells_changed


def test_plan_apply_parity(tmp_path, fixture_input_sha):
    """ToolPlan.predicted_cells_changed must equal actual cells_changed."""
    tool = SparkFeatheredRampTool()
    ctx = _make_ctx(tmp_path / "iter_parity")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert plan.predicted_cells_changed == result.cells_changed
    assert plan.predicted_max_delta["spark_deg"] == pytest.approx(3.0)


def test_spark_clamp_gate_aborts_without_writing(tmp_path, fixture_input_sha):
    """A plan that would exceed the per-cell clamp must abort with no file written."""
    tool = SparkFeatheredRampTool()
    ctx = _make_ctx(tmp_path / "iter_abort")
    aggressive_ramp = [(4.5, 0.0), (5.0, 2.0), (5.5, 5.0), (6.0, 10.0)]
    finding = _make_finding(
        tool_params={
            "ramp": aggressive_ramp,
            "max_retard_deg": 3.0,
        }
    )

    plan = tool.plan(finding, ctx)
    assert plan.predicted_max_delta["spark_deg"] > 3.0
    result = tool.apply(plan, ctx)

    assert result.success is False
    assert any(gf.gate == "spark_clamp" for gf in result.gates_failed)
    assert plan.output_pvv_path.exists() is False
    assert result.sha256 is None
    assert result.patch_path is None


def test_dispatcher_routes_finding_to_tool(tmp_path, fixture_input_sha):
    """End-to-end via TuningDispatcher: Finding -> ToolPlan -> PatchResult."""
    tool = SparkFeatheredRampTool()
    dispatcher = TuningDispatcher(detectors=[], tools={tool.name: tool})
    ctx = _make_ctx(tmp_path / "iter_dispatcher")
    finding = _make_finding()

    # Synthesize what a detector would emit; the dispatcher.step() flow
    # normally runs detectors itself but we bypass that here to keep the
    # slice focused on the routing + tool execution path.
    tool_manifest = tool.manifest()
    assert finding.kind in tool_manifest.fix_kinds
    assert finding.suggested_tool == tool.name

    plan = tool.plan(finding, ctx)
    result = dispatcher.apply(plan, ctx)

    assert result.success
    assert result.sha256 == REFERENCE_OUTPUT_SHA


def test_manifest_emitted_alongside_patch(tmp_path, fixture_input_sha):
    """A manifest.json must be written next to the patch with the correct shape."""
    tool = SparkFeatheredRampTool()
    ctx = _make_ctx(tmp_path / "iter_manifest")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert result.manifest_path is not None and result.manifest_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "spark_feathered_ramp_patch"
    assert manifest["target_item_id"] == "tbl_spark_advance_front_cyl"
    assert manifest["output"]["sha256"] == REFERENCE_OUTPUT_SHA
    assert manifest["summary"]["cells_modified"] == REFERENCE_CELLS_CHANGED
    assert manifest["finding"]["kind"] == "spark_valley"


def test_profile_overrides_change_output(tmp_path, fixture_input_sha):
    """A profile override that bites must change the patch bytes."""
    tool = SparkFeatheredRampTool()
    iter_default = tmp_path / "iter_default"
    iter_override = tmp_path / "iter_override"
    iter_default.mkdir(parents=True, exist_ok=True)
    iter_override.mkdir(parents=True, exist_ok=True)

    ctx_default = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_default,
    )
    ctx_override = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={
            "id": "seanbike",
            "tool_overrides": {TOOL_NAME: {"load_min_kpa": 50.0}},
        },
        iteration_dir=iter_override,
    )
    finding = _make_finding()

    result_default = tool.apply(tool.plan(finding, ctx_default), ctx_default)
    result_override = tool.apply(tool.plan(finding, ctx_override), ctx_override)

    assert result_default.success and result_override.success
    assert result_default.sha256 == REFERENCE_OUTPUT_SHA
    # Lowering load_min_kpa from 70 to 50 expands the load mask to more
    # columns, so more cells get pulled and the output bytes differ.
    assert result_override.sha256 != REFERENCE_OUTPUT_SHA
    assert result_override.cells_changed > result_default.cells_changed


# ---------------------------------------------------------------------------
# End-to-end dispatcher tests with a synthetic Surface2D.
#
# These prove the full Detector -> Finding -> Dispatcher -> Tool path,
# decoupled from the pull-data pipeline. The Surface2D carries a planted
# spark valley at 5000-5500 RPM with a 6 deg depth at high MAP.
# ---------------------------------------------------------------------------


def _build_planted_valley_surface(cylinder: str = "front") -> Surface2D:
    """Build a synthetic spark Surface2D with a known valley shape.

    Curve in the high-MAP band (>= 80 kPa):
      3500-4500 RPM:  35 deg
      5000-5500 RPM:  29 deg  <- the valley, 6 deg depth
      6000-7000 RPM:  35 deg
    """
    rpm_bins = [3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0, 6500.0, 7000.0]
    map_bins = [40.0, 60.0, 80.0, 100.0]

    def cell_value(rpm: float, map_kpa: float) -> float:
        # Below the high-MAP band the cell is a low-load idle/cruise advance.
        if map_kpa < 80.0:
            return 25.0
        # In the high-MAP band, plant a valley between 5000 and 5500 RPM.
        if 5000.0 <= rpm <= 5500.0:
            return 29.0
        return 35.0

    values: List[List[float | None]] = []
    hit_count: List[List[int]] = []
    for rpm in rpm_bins:
        row: list[float | None] = []
        hits_row: list[int] = []
        for kpa in map_bins:
            row.append(cell_value(rpm, kpa))
            hits_row.append(20)
        values.append(row)
        hit_count.append(hits_row)

    return Surface2D(
        surface_id=f"spark_{cylinder}",
        title=f"Spark advance {cylinder}",
        description="synthetic planted valley fixture",
        rpm_axis=SurfaceAxis(name="rpm", unit="RPM", bins=rpm_bins),
        map_axis=SurfaceAxis(name="map", unit="kPa", bins=map_bins),
        values=values,
        hit_count=hit_count,
        stats=SurfaceStats(
            min=25.0,
            max=35.0,
            mean=30.0,
            non_nan_cells=len(rpm_bins) * len(map_bins),
            total_cells=len(rpm_bins) * len(map_bins),
            total_samples=20 * len(rpm_bins) * len(map_bins),
        ),
    )


def test_spark_valley_detector_emits_finding_from_synthetic_surface(tmp_path, fixture_input_sha):
    """The adapter must turn a SparkValleyFinding into a canonical Finding."""
    detector = SparkValleyDetector(high_map_min_kpa=80.0)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=tmp_path / "iter_detect",
        surfaces={"spark_front": _build_planted_valley_surface("front")},
    )
    ctx.iteration_dir.mkdir(parents=True, exist_ok=True)

    findings = detector.detect(ctx)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "spark_valley"
    assert finding.source == "spark_valley_detector"
    assert finding.suggested_tool == TOOL_NAME
    assert finding.evidence["cylinder"] == "front"
    assert 5000.0 <= finding.evidence["rpm_center"] <= 5500.0
    # The core detector smooths with a window of 3, which flattens a planted
    # step from 35 -> 29 -> 35 to an apparent depth of ~4 deg rather than the
    # raw 6 deg. That's the actual depth the dispatcher will see.
    assert finding.evidence["depth_deg"] == pytest.approx(4.0, abs=0.5)
    # depth_deg ~= 4.0 falls in the 2-4 -> 0.30-0.50 band, saturating at 0.5
    # when depth_deg == 4.0 exactly.
    assert 0.45 <= finding.severity <= 0.55
    assert finding.confidence > 0.0


def test_dispatcher_step_routes_synthetic_valley_to_tool(tmp_path, fixture_input_sha):
    """Full pipeline: synthetic surface -> detector -> dispatcher -> ToolPlan."""
    tool = SparkFeatheredRampTool()
    dispatcher = TuningDispatcher(
        detectors=[SparkValleyDetector(high_map_min_kpa=80.0)],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_e2e"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"spark_front": _build_planted_valley_surface("front")},
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is not None
    assert decision.plan.tool == TOOL_NAME
    assert decision.plan.finding.kind == "spark_valley"
    assert decision.plan.predicted_cells_changed > 0
    # The applied SHA must still match the reference because the tool's
    # default ramp is fixed regardless of the finding's severity.
    result = dispatcher.apply(decision.plan, ctx)
    assert result.success
    assert result.sha256 == REFERENCE_OUTPUT_SHA


def test_dispatcher_step_returns_no_plan_when_no_surface(tmp_path, fixture_input_sha):
    """No surfaces -> no findings -> no plan."""
    tool = SparkFeatheredRampTool()
    dispatcher = TuningDispatcher(
        detectors=[SparkValleyDetector()],
        tools={tool.name: tool},
    )
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=tmp_path / "iter_empty",
        surfaces={},
    )
    ctx.iteration_dir.mkdir(parents=True, exist_ok=True)

    decision = dispatcher.step(ctx)

    assert decision.plan is None
    assert decision.findings == ()
