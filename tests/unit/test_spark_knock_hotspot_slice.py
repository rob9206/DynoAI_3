"""End-to-end slice test for the SparkKnockHotspot tool.

Asserts:

  1. Byte-identical SHA-256 match against the seanbike reference output
     (`v_pc_advanced_translation_safeavg140_gpsmooth_sparkguard.pvv`).
  2. Idempotency: running the same plan twice gives the same SHA.
  3. plan().predicted_cells_changed == actual cells_changed.
  4. Only the target spark table id changes (ItemIntegrityGate).
  5. SparkClampGate aborts without writing when pull exceeds the gate.
  6. Manifest schema matches the seanbike reference shape.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.detectors.knock_hotspot import KnockHotspotDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.diagnostics.finding import Finding
from dynoai.tools.spark_knock_hotspot import (
    DEFAULT_TARGET_ITEM_ID,
    SparkKnockHotspotTool,
    TOOL_NAME,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
)
INPUT_PVV = (
    SESSION_DIR
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation_safeavg140_gpsmooth.pvv"
)
REFERENCE_INPUT_SHA = (
    "1fbaad312771bb4bebf15388d80fd7f2e25c48f2e339d0eaf38479186ae43d6e"
)
REFERENCE_OUTPUT_SHA = (
    "b246b8b301283376bd3314139b62e3aa17fe68930a5e5fcf088112a9078fa7e8"
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


def _make_ctx(iter_dir: Path, *, profile: dict | None = None) -> DetectionContext:
    iter_dir.mkdir(parents=True, exist_ok=True)
    return DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile=profile or {"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
    )


def _make_finding(**overrides) -> Finding:
    params = {
        "kind": "knock_hotspot",
        "severity": 0.9,
        "confidence": 0.85,
        "evidence": {
            "rpm_min_krpm": 5.0,
            "load_min_kpa": 70.0,
            "cylinder": "front",
        },
        "suggested_tool": TOOL_NAME,
        "tool_params": {},
        "source": "knock_hotspot_detector",
    }
    params.update(overrides)
    return Finding(**params)


def test_lifted_tool_matches_seanbike_reference_sha(tmp_path, fixture_input_sha):
    """The new tool must produce the exact same bytes as the seanbike script."""
    tool = SparkKnockHotspotTool()
    ctx = _make_ctx(tmp_path / "iter_ref")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success, f"apply failed: {result.gates_failed}"
    assert result.sha256 == REFERENCE_OUTPUT_SHA, (
        f"byte drift from seanbike reference: got {result.sha256}, "
        f"expected {REFERENCE_OUTPUT_SHA}"
    )
    assert result.cells_changed == REFERENCE_CELLS_CHANGED
    assert result.extra["cells_targeted"] == REFERENCE_CELLS_CHANGED
    assert result.extra["max_pull_deg"] == pytest.approx(3.0)
    assert result.extra["mean_pull_deg"] == pytest.approx(3.0)


def test_idempotent_apply_produces_same_sha(tmp_path, fixture_input_sha):
    """Same plan twice -> identical bytes."""
    tool = SparkKnockHotspotTool()
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
    tool = SparkKnockHotspotTool()
    ctx = _make_ctx(tmp_path / "iter_parity")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert plan.predicted_cells_changed == result.cells_changed
    assert plan.predicted_max_delta["spark_deg"] == pytest.approx(3.0)


def test_only_target_table_changes(tmp_path, fixture_input_sha):
    """ItemIntegrityGate confirms only the target spark table changed."""
    tool = SparkKnockHotspotTool()
    ctx = _make_ctx(tmp_path / "iter_integrity")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    assert result.extra["changed_ids"] == [DEFAULT_TARGET_ITEM_ID]


def test_spark_clamp_gate_aborts_when_pull_exceeds_clamp(tmp_path, fixture_input_sha):
    """A pull_deg > max_retard_deg must fire SparkClampGate and abort without writing."""
    tool = SparkKnockHotspotTool()
    ctx = _make_ctx(tmp_path / "iter_abort")
    finding = _make_finding(
        tool_params={"pull_deg": 6.0, "max_retard_deg": 3.0}
    )

    plan = tool.plan(finding, ctx)
    assert plan.predicted_max_delta["spark_deg"] > 3.0
    result = tool.apply(plan, ctx)

    assert result.success is False
    assert any(gf.gate == "spark_clamp" for gf in result.gates_failed)
    assert plan.output_pvv_path.exists() is False
    assert result.sha256 is None
    assert result.patch_path is None


def test_manifest_schema_matches_seanbike_reference(tmp_path, fixture_input_sha):
    """Generated manifest must keep the field shape the reference expects."""
    tool = SparkKnockHotspotTool()
    ctx = _make_ctx(tmp_path / "iter_manifest")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "spark_hotspot_guard_patch"
    assert manifest["target_item_id"] == DEFAULT_TARGET_ITEM_ID
    assert manifest["output"]["sha256"] == REFERENCE_OUTPUT_SHA
    assert manifest["summary"]["cells_targeted"] == REFERENCE_CELLS_CHANGED
    assert manifest["patch_policy"]["pull_deg"] == 3.0
    assert manifest["patch_policy"]["floor_deg"] == 5.0
    assert manifest["finding"]["kind"] == "knock_hotspot"


def test_profile_override_narrows_zone(tmp_path, fixture_input_sha):
    """Raising rpm_min_krpm narrows the zone -> fewer cells changed, different SHA."""
    tool = SparkKnockHotspotTool()
    ctx_default = _make_ctx(tmp_path / "iter_default")
    ctx_narrow = _make_ctx(
        tmp_path / "iter_narrow",
        profile={
            "id": "seanbike",
            "tool_overrides": {TOOL_NAME: {"rpm_min_krpm": 6.0}},
        },
    )
    finding = _make_finding()

    result_default = tool.apply(tool.plan(finding, ctx_default), ctx_default)
    result_narrow = tool.apply(tool.plan(finding, ctx_narrow), ctx_narrow)

    assert result_default.success and result_narrow.success
    assert result_default.sha256 == REFERENCE_OUTPUT_SHA
    assert result_narrow.sha256 != REFERENCE_OUTPUT_SHA
    assert result_narrow.cells_changed < result_default.cells_changed


# ---------------------------------------------------------------------------
# End-to-end dispatcher tests with a synthetic knock surface.
#
# Plant a knock hotspot at the same zone the seanbike reference patch
# targets (RPM >= 5000, MAP >= 70 kPa). The detector should emit a Finding
# whose tool_params route through dispatcher.step() to spark_knock_hotspot,
# producing the reference SHA b246b8b3...
# ---------------------------------------------------------------------------


def _build_planted_knock_surface(
    cylinder: str = "front",
    *,
    rpm_min_hot: float = 5000.0,
    load_min_hot: float = 70.0,
    hot_rate: float = 0.18,
    cold_rate: float = 0.0,
    hit_count: int = 25,
) -> Surface2D:
    """Synthetic knock surface with a planted hot zone."""
    rpm_bins = [3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0, 6500.0, 7000.0]
    load_bins = [40.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    values: list[list[float | None]] = []
    hits: list[list[int]] = []
    for rpm in rpm_bins:
        row_v: list[float | None] = []
        row_h: list[int] = []
        for kpa in load_bins:
            if rpm >= rpm_min_hot and kpa >= load_min_hot:
                row_v.append(hot_rate)
            else:
                row_v.append(cold_rate)
            row_h.append(hit_count)
        values.append(row_v)
        hits.append(row_h)

    return Surface2D(
        surface_id=f"knock_{cylinder}",
        title=f"Knock activity {cylinder}",
        description="synthetic planted hotspot fixture",
        rpm_axis=SurfaceAxis(name="rpm", unit="RPM", bins=rpm_bins),
        map_axis=SurfaceAxis(name="map", unit="kPa", bins=load_bins),
        values=values,
        hit_count=hits,
        stats=SurfaceStats(
            min=cold_rate,
            max=hot_rate,
            mean=hot_rate / 3,
            non_nan_cells=len(rpm_bins) * len(load_bins),
            total_cells=len(rpm_bins) * len(load_bins),
            total_samples=hit_count * len(rpm_bins) * len(load_bins),
        ),
    )


def test_knock_hotspot_detector_emits_finding_with_zone_bounds(tmp_path, fixture_input_sha):
    """The detector must turn a hot-zone Surface2D into a canonical Finding."""
    detector = KnockHotspotDetector(min_knock_rate=0.05, min_cells=3)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=tmp_path / "iter_detect",
        surfaces={"knock_front": _build_planted_knock_surface("front")},
    )
    ctx.iteration_dir.mkdir(parents=True, exist_ok=True)

    findings = detector.detect(ctx)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "knock_hotspot"
    assert finding.source == "knock_hotspot_detector"
    assert finding.suggested_tool == TOOL_NAME
    assert finding.evidence["cylinder"] == "front"
    # The planted hotspot spans RPM 5000-7000 and MAP 70-100, so the bounding
    # box must start at rpm=5000 / load=70.
    assert finding.evidence["rpm_min_axis"] == 5000.0
    assert finding.evidence["load_min_axis"] == 70.0
    assert finding.evidence["peak_knock_rate"] == pytest.approx(0.18)
    # Unit conversion in tool_params: kRPM, kPa.
    assert finding.tool_params["rpm_min_krpm"] == pytest.approx(5.0)
    assert finding.tool_params["load_min_kpa"] == pytest.approx(70.0)
    # 0.18 knock rate maps to severity ~0.75 (moderate band).
    assert 0.7 <= finding.severity <= 0.85
    assert finding.confidence > 0.0


def test_dispatcher_step_routes_synthetic_hotspot_to_reference_sha(tmp_path, fixture_input_sha):
    """Full pipeline: knock surface -> detector -> dispatcher -> reference SHA."""
    tool = SparkKnockHotspotTool()
    dispatcher = TuningDispatcher(
        detectors=[KnockHotspotDetector(min_knock_rate=0.05, min_cells=3)],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_e2e"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"knock_front": _build_planted_knock_surface("front")},
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is not None
    assert decision.plan.tool == TOOL_NAME
    assert decision.plan.finding.kind == "knock_hotspot"
    # Detector-derived zone (rpm_min_krpm=5.0, load_min_kpa=70.0) matches the
    # seanbike reference defaults, so the patch must be byte-identical.
    result = dispatcher.apply(decision.plan, ctx)
    assert result.success
    assert result.sha256 == REFERENCE_OUTPUT_SHA
    assert result.cells_changed == REFERENCE_CELLS_CHANGED


def test_dispatcher_skips_when_knock_below_threshold(tmp_path, fixture_input_sha):
    """Cold knock surface -> no findings -> no plan."""
    tool = SparkKnockHotspotTool()
    dispatcher = TuningDispatcher(
        detectors=[KnockHotspotDetector(min_knock_rate=0.05, min_cells=3)],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_cold"
    iter_dir.mkdir(parents=True, exist_ok=True)
    cold_surface = _build_planted_knock_surface(
        "front", hot_rate=0.02, cold_rate=0.0
    )
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"knock_front": cold_surface},
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is None
    assert decision.findings == ()
