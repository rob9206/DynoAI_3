"""End-to-end slice test for the WotVeGraft tool.

This is the first lifted tool that consumes more than one input PVV (a
donor + a base). The donor PVV path flows through finding.tool_params and
ToolPlan.bound_params.

Asserts:

  1. Byte-identical SHA-256 against the seanbike reference output
     (`..._wotplus8_fromv5.pvv`) when given the same donor + base + defaults.
  2. Idempotency: same plan twice -> same SHA.
  3. plan().predicted_cells_changed == actual cells_changed.
  4. Both target VE table ids change; nothing else (ItemIntegrityGate).
  5. plan() raises if donor_pvv_path is missing or not on disk.
  6. axis_alignment gate fires when donor and base have mismatched axes,
     and no file is written.
  7. Manifest captures donor SHA, base SHA, scalar factor, and per-table
     stats.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.detectors.wot_lean import WotLeanDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.diagnostics.finding import Finding
from dynoai.tools.wot_ve_graft import (
    DEFAULT_VE_FRONT_ID,
    DEFAULT_VE_REAR_ID,
    TOOL_NAME,
    WotVeGraftTool,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
)
ITER_PATCHES = SESSION_DIR / "iterations" / "iter_0" / "patches"
DONOR_PVV = ITER_PATCHES / "newnenww_emergency_rich_v5_stepup.pvv"
BASE_PVV = ITER_PATCHES / "v_pc_advanced_translation_safeavg140_gpsmooth_sparkramp.pvv"
REFERENCE_DONOR_SHA = (
    "7e20e0f19af79eab9503166f1d173d07a0085c5336f502492945b9597cdbc43a"
)
REFERENCE_BASE_SHA = (
    "b5a69006943b65ec9a5c7dc647e32874908839b929c874b56024d1a8099a9a76"
)
REFERENCE_OUTPUT_SHA = (
    "c9b970b0a16e129ca5a0a2114e4cfbcff33e2ecf10de901194f3c452be7ef787"
)
REFERENCE_FRONT_CELLS_CHANGED = 78
REFERENCE_REAR_CELLS_CHANGED = 78


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def fixture_donor_sha() -> str:
    assert DONOR_PVV.exists(), f"missing fixture: {DONOR_PVV}"
    sha = _sha256(DONOR_PVV)
    assert sha == REFERENCE_DONOR_SHA, (
        f"donor drift: got {sha}, expected {REFERENCE_DONOR_SHA}"
    )
    return sha


@pytest.fixture(scope="module")
def fixture_base_sha() -> str:
    assert BASE_PVV.exists(), f"missing fixture: {BASE_PVV}"
    sha = _sha256(BASE_PVV)
    assert sha == REFERENCE_BASE_SHA, (
        f"base drift: got {sha}, expected {REFERENCE_BASE_SHA}"
    )
    return sha


def _make_ctx(iter_dir: Path, *, profile: dict | None = None) -> DetectionContext:
    iter_dir.mkdir(parents=True, exist_ok=True)
    return DetectionContext(
        base_pvv_path=BASE_PVV,
        vehicle_profile=profile or {"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
    )


def _make_finding(donor: Path = DONOR_PVV, **overrides) -> Finding:
    params = {
        "kind": "wot_lean",
        "severity": 0.85,
        "confidence": 0.9,
        "evidence": {"rpm_min_krpm": 5.0, "tps_min_pct": 80.0},
        "suggested_tool": TOOL_NAME,
        "tool_params": {"donor_pvv_path": str(donor)},
        "source": "wot_lean_detector",
    }
    params.update(overrides)
    return Finding(**params)


def test_lifted_tool_matches_seanbike_reference_sha(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """The new tool must produce byte-identical output to graft_wot_from_v5."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_ref")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success, f"apply failed: {result.gates_failed}"
    assert result.sha256 == REFERENCE_OUTPUT_SHA, (
        f"byte drift from seanbike WOT graft reference: got {result.sha256}, "
        f"expected {REFERENCE_OUTPUT_SHA}"
    )
    assert result.cells_changed == (
        REFERENCE_FRONT_CELLS_CHANGED + REFERENCE_REAR_CELLS_CHANGED
    )


def test_idempotent_apply_produces_same_sha(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Same plan twice -> identical bytes."""
    tool = WotVeGraftTool()
    ctx_a = _make_ctx(tmp_path / "iter_a")
    ctx_b = _make_ctx(tmp_path / "iter_b")
    finding = _make_finding()

    result_a = tool.apply(tool.plan(finding, ctx_a), ctx_a)
    result_b = tool.apply(tool.plan(finding, ctx_b), ctx_b)

    assert result_a.success and result_b.success
    assert result_a.sha256 == result_b.sha256


def test_plan_apply_parity(tmp_path, fixture_donor_sha, fixture_base_sha):
    """ToolPlan.predicted_cells_changed must equal actual cells_changed."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_parity")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert plan.predicted_cells_changed == result.cells_changed
    assert plan.predicted_cells_changed == (
        REFERENCE_FRONT_CELLS_CHANGED + REFERENCE_REAR_CELLS_CHANGED
    )


def test_only_two_ve_table_ids_change(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """ItemIntegrityGate confirms only the front + rear VE tables changed."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_integrity")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    assert set(result.extra["changed_ids"]) == {
        DEFAULT_VE_FRONT_ID,
        DEFAULT_VE_REAR_ID,
    }


def test_plan_raises_when_donor_path_missing(tmp_path, fixture_base_sha):
    """plan() must reject a finding with no donor_pvv_path."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_no_donor")
    finding = Finding(
        kind="wot_lean",
        severity=0.85,
        confidence=0.9,
        evidence={},
        suggested_tool=TOOL_NAME,
        tool_params={},  # no donor_pvv_path
        source="test",
    )
    with pytest.raises(ValueError, match="donor_pvv_path"):
        tool.plan(finding, ctx)


def test_plan_raises_when_donor_file_missing(tmp_path, fixture_base_sha):
    """plan() must reject a finding pointing at a non-existent donor."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_bad_donor")
    finding = _make_finding(donor=tmp_path / "nonexistent_donor.pvv")
    with pytest.raises(FileNotFoundError):
        tool.plan(finding, ctx)


def test_axis_mismatch_aborts_without_writing(tmp_path, fixture_donor_sha, fixture_base_sha):
    """A donor with axes that disagree with base must trip axis_alignment.

    Build a malformed donor by mutating the row labels of one VE table so they
    no longer align with the base, then run apply() and assert the gate fires
    with no patch file produced.
    """
    bad_donor = tmp_path / "bad_donor.pvv"
    shutil.copy(DONOR_PVV, bad_donor)
    tree = ET.parse(bad_donor)
    root = tree.getroot()
    for item in root.findall("Item"):
        if item.get("id") == DEFAULT_VE_FRONT_ID:
            for row in item.findall("./Rows/Row"):
                original = float(row.get("label", "0"))
                row.set("label", f"{original + 1.0:.4f}")
            break
    tree.write(bad_donor, encoding="utf-8", xml_declaration=True)

    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_axis_bad")
    finding = _make_finding(donor=bad_donor)

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success is False
    assert any(
        gf.gate == "axis_alignment" for gf in result.gates_failed
    ), f"expected axis_alignment failure, got {[gf.gate for gf in result.gates_failed]}"
    assert plan.output_pvv_path.exists() is False
    assert result.sha256 is None


def test_manifest_records_donor_and_scalar_factor(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Manifest must capture both PVV SHAs and the scalar compensation factor."""
    tool = WotVeGraftTool()
    ctx = _make_ctx(tmp_path / "iter_manifest")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "wot_ve_graft"
    assert manifest["inputs"]["source_sha256"] == REFERENCE_DONOR_SHA
    assert manifest["inputs"]["input_sha256"] == REFERENCE_BASE_SHA
    assert manifest["output"]["sha256"] == REFERENCE_OUTPUT_SHA
    # Scalar factor from manifest: src_disp/dst_disp * dst_inj/src_inj
    # = 95.5/103 * 31.07/31.07 = 0.9272 (matches the seanbike reference).
    assert manifest["policy"]["source_to_target_scalar_factor"] == pytest.approx(
        0.9271844660194175
    )
    assert manifest["policy"]["graft_pct"] == 8.0
    assert manifest["finding"]["kind"] == "wot_lean"
    assert len(manifest["table_stats"]) == 2
    front_stats = next(
        t for t in manifest["table_stats"] if t["table_id"] == DEFAULT_VE_FRONT_ID
    )
    assert front_stats["cells_changed"] == REFERENCE_FRONT_CELLS_CHANGED


def test_profile_override_changes_graft_pct(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Profile override on graft_pct must change the output bytes."""
    tool = WotVeGraftTool()
    ctx_default = _make_ctx(tmp_path / "iter_default")
    ctx_override = _make_ctx(
        tmp_path / "iter_override",
        profile={
            "id": "seanbike",
            "tool_overrides": {TOOL_NAME: {"graft_pct": 4.0}},
        },
    )
    finding = _make_finding()

    result_default = tool.apply(tool.plan(finding, ctx_default), ctx_default)
    result_override = tool.apply(tool.plan(finding, ctx_override), ctx_override)

    assert result_default.success and result_override.success
    assert result_default.sha256 == REFERENCE_OUTPUT_SHA
    assert result_override.sha256 != REFERENCE_OUTPUT_SHA


# ---------------------------------------------------------------------------
# End-to-end dispatcher tests with a synthetic AFR-error surface.
#
# WotLeanDetector consumes an AFR-error surface, detects a lean zone inside
# the WOT region, and emits a Finding whose tool_params route directly to
# wot_ve_graft. The detected zone bounds (rpm_min_krpm=5.0, tps_min_pct=80.0)
# match the seanbike reference defaults so the patch is byte-identical.
# ---------------------------------------------------------------------------


def _build_planted_afr_error_surface(
    cylinder: str = "front",
    *,
    wot_rpm_min: float = 5000.0,
    wot_tps_min: float = 80.0,
    lean_error: float = 0.6,
    cold_error: float = 0.0,
    hit_count: int = 25,
) -> Surface2D:
    """Synthetic AFR-error surface with a planted WOT lean zone.

    Values are AFR-error (measured - target). Positive = lean.
    Lean cells live in RPM >= wot_rpm_min AND TPS >= wot_tps_min.
    """
    rpm_bins = [3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0, 6500.0, 7000.0]
    tps_bins = [40.0, 60.0, 80.0, 90.0, 100.0]

    values: list[list[float | None]] = []
    hits: list[list[int]] = []
    for rpm in rpm_bins:
        row_v: list[float | None] = []
        row_h: list[int] = []
        for tps in tps_bins:
            if rpm >= wot_rpm_min and tps >= wot_tps_min:
                row_v.append(lean_error)
            else:
                row_v.append(cold_error)
            row_h.append(hit_count)
        values.append(row_v)
        hits.append(row_h)

    return Surface2D(
        surface_id=f"afr_error_{cylinder}",
        title=f"AFR error {cylinder}",
        description="synthetic planted WOT lean zone",
        rpm_axis=SurfaceAxis(name="rpm", unit="RPM", bins=rpm_bins),
        map_axis=SurfaceAxis(name="tps", unit="%", bins=tps_bins),
        values=values,
        hit_count=hits,
        stats=SurfaceStats(
            min=cold_error,
            max=lean_error,
            mean=lean_error / 3,
            non_nan_cells=len(rpm_bins) * len(tps_bins),
            total_cells=len(rpm_bins) * len(tps_bins),
            total_samples=hit_count * len(rpm_bins) * len(tps_bins),
        ),
    )


def test_wot_lean_detector_emits_finding_with_zone_and_donor(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """The adapter must convert a lean AFR-error surface into a routable Finding."""
    detector = WotLeanDetector(
        donor_pvv_path=DONOR_PVV,
        wot_rpm_min_krpm=5.0,
        wot_tps_min_pct=80.0,
        min_lean_afr_error=0.10,
        min_cells=3,
    )
    iter_dir = tmp_path / "iter_detect"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"afr_error_front": _build_planted_afr_error_surface("front")},
    )

    findings = detector.detect(ctx)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "wot_lean"
    assert finding.source == "wot_lean_detector"
    assert finding.suggested_tool == TOOL_NAME
    assert finding.evidence["cylinder"] == "front"
    # Planted zone: RPM 5000-7000, TPS 80-100. Detector emits bounds in
    # axis units (raw RPM here, kPa-like for TPS).
    assert finding.evidence["rpm_min_axis"] == 5000.0
    assert finding.evidence["load_min_axis"] == 80.0
    assert finding.evidence["peak_lean_afr_error"] == pytest.approx(0.6)
    # tool_params: kRPM + % + donor path.
    assert finding.tool_params["rpm_min_krpm"] == pytest.approx(5.0)
    assert finding.tool_params["tps_min_pct"] == pytest.approx(80.0)
    assert finding.tool_params["donor_pvv_path"] == str(DONOR_PVV)
    # 0.60 AFR-error -> moderate band, severity ~0.69.
    assert 0.60 <= finding.severity <= 0.75


def test_dispatcher_step_routes_wot_lean_to_reference_sha(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Full pipeline: AFR-error surface -> detector -> dispatcher -> reference SHA."""
    tool = WotVeGraftTool()
    dispatcher = TuningDispatcher(
        detectors=[
            WotLeanDetector(
                donor_pvv_path=DONOR_PVV,
                wot_rpm_min_krpm=5.0,
                wot_tps_min_pct=80.0,
                min_lean_afr_error=0.10,
                min_cells=3,
            )
        ],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_e2e"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"afr_error_front": _build_planted_afr_error_surface("front")},
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is not None
    assert decision.plan.tool == TOOL_NAME
    assert decision.plan.finding.kind == "wot_lean"
    # Detector-derived zone matches the seanbike reference defaults, so the
    # patch SHA must match the byte-identical reference.
    result = dispatcher.apply(decision.plan, ctx)
    assert result.success
    assert result.sha256 == REFERENCE_OUTPUT_SHA
    assert result.cells_changed == (
        REFERENCE_FRONT_CELLS_CHANGED + REFERENCE_REAR_CELLS_CHANGED
    )


def test_dispatcher_skips_when_afr_error_below_threshold(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Clean AFR (no lean) -> no findings -> no plan."""
    tool = WotVeGraftTool()
    dispatcher = TuningDispatcher(
        detectors=[
            WotLeanDetector(
                donor_pvv_path=DONOR_PVV,
                min_lean_afr_error=0.10,
                min_cells=3,
            )
        ],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_clean"
    iter_dir.mkdir(parents=True, exist_ok=True)
    clean_surface = _build_planted_afr_error_surface(
        "front", lean_error=0.05, cold_error=0.0
    )
    ctx = DetectionContext(
        base_pvv_path=BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"afr_error_front": clean_surface},
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is None
    assert decision.findings == ()


def test_detector_with_no_donor_emits_finding_but_plan_fails(
    tmp_path, fixture_donor_sha, fixture_base_sha
):
    """Without a donor configured, the detector still finds the zone, but the
    wot_ve_graft tool will reject the plan because donor_pvv_path is missing.
    This is the correct fail-closed behavior — donor selection is a policy
    decision, not a detector decision."""
    detector = WotLeanDetector(donor_pvv_path=None, min_lean_afr_error=0.10)
    iter_dir = tmp_path / "iter_no_donor"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={"afr_error_front": _build_planted_afr_error_surface("front")},
    )

    findings = detector.detect(ctx)
    assert len(findings) == 1
    assert "donor_pvv_path" not in findings[0].tool_params

    tool = WotVeGraftTool()
    with pytest.raises(ValueError, match="donor_pvv_path"):
        tool.plan(findings[0], ctx)
