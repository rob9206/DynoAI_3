"""End-to-end slice test for the GpSmoothIdleCruiseVe tool.

Asserts:

  1. Byte-identical SHA-256 match against the existing seanbike reference
     (proving the GP-fit algorithm and the per-cell clamp were lifted
     faithfully across two cylinder tables).
  2. Idempotency: same plan twice -> same SHA.
  3. plan().predicted_cells_changed == actual cells_changed.
  4. Only the two approved VE table ids may change; everything else is
     byte-identical (ItemIntegrityGate).
  5. A tight VeClampGate (e.g. 2 percent) aborts without writing because
     the algorithm's natural deltas exceed it.
  6. Manifest schema includes per-cylinder summary stats and the GP
     hyperparameters block.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.diagnostics.dispatcher import TuningDispatcher
from dynoai.diagnostics.finding import Finding
from dynoai.tools.gp_smooth_idle_cruise_ve import (
    DEFAULT_VE_FRONT_ID,
    DEFAULT_VE_REAR_ID,
    GpSmoothIdleCruiseVeTool,
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
    / "v_pc_advanced_translation_safeavg140.pvv"
)
REFERENCE_INPUT_SHA = (
    "517b03d906d4ea1073ba36abaaddbb2aa837db2020469674a2cca9ee9e71e0fc"
)
REFERENCE_OUTPUT_SHA = (
    "1fbaad312771bb4bebf15388d80fd7f2e25c48f2e339d0eaf38479186ae43d6e"
)
# Per the seanbike reference manifest.
REFERENCE_FRONT_CELLS_CHANGED = 130
REFERENCE_REAR_CELLS_CHANGED = 130


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
        "kind": "idle_ve_noise",
        "severity": 0.7,
        "confidence": 0.9,
        "evidence": {"region": "idle_cruise", "rpm_max_krpm": 4.0, "tps_max_pct": 40.0},
        "suggested_tool": TOOL_NAME,
        "tool_params": {},
        "source": "idle_ve_noise_detector",
    }
    params.update(overrides)
    return Finding(**params)


def test_lifted_tool_matches_seanbike_reference_sha(tmp_path, fixture_input_sha):
    """The lifted tool must produce byte-identical output to the seanbike script."""
    tool = GpSmoothIdleCruiseVeTool()
    ctx = _make_ctx(tmp_path / "iter_ref")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success, f"apply failed: {result.gates_failed}"
    assert result.sha256 == REFERENCE_OUTPUT_SHA, (
        f"byte drift from seanbike GP reference: got {result.sha256}, "
        f"expected {REFERENCE_OUTPUT_SHA}"
    )
    assert result.cells_changed == (
        REFERENCE_FRONT_CELLS_CHANGED + REFERENCE_REAR_CELLS_CHANGED
    )
    assert result.extra["front_cells_changed"] == REFERENCE_FRONT_CELLS_CHANGED
    assert result.extra["rear_cells_changed"] == REFERENCE_REAR_CELLS_CHANGED


def test_idempotent_apply_produces_same_sha(tmp_path, fixture_input_sha):
    """Same plan twice -> identical bytes (MaternGP must be deterministic)."""
    tool = GpSmoothIdleCruiseVeTool()
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
    tool = GpSmoothIdleCruiseVeTool()
    ctx = _make_ctx(tmp_path / "iter_parity")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert plan.predicted_cells_changed == result.cells_changed


def test_only_two_ve_table_ids_change(tmp_path, fixture_input_sha):
    """ItemIntegrityGate confirms only the front + rear VE tables changed."""
    tool = GpSmoothIdleCruiseVeTool()
    ctx = _make_ctx(tmp_path / "iter_integrity")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    assert set(result.extra["changed_ids"]) == {
        DEFAULT_VE_FRONT_ID,
        DEFAULT_VE_REAR_ID,
    }


def test_tight_ve_clamp_gate_aborts_without_writing(tmp_path, fixture_input_sha):
    """A clamp gate tighter than the patch's natural delta must fail closed."""
    tool = GpSmoothIdleCruiseVeTool()
    # The seanbike reference produces max_abs_delta around 6.5 VE on a base
    # around 100 VE, i.e. ~5-7 percent. A 2 percent gate must fire.
    finding = _make_finding(tool_params={"ve_clamp_gate_pct": 2.0})
    ctx = _make_ctx(tmp_path / "iter_tight_clamp")

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success is False
    assert any(gf.gate.startswith("ve_clamp") for gf in result.gates_failed)
    assert plan.output_pvv_path.exists() is False
    assert result.sha256 is None


def test_manifest_includes_gp_hyperparams_and_per_cylinder_stats(
    tmp_path, fixture_input_sha
):
    """The manifest must capture enough to reproduce the patch deterministically."""
    tool = GpSmoothIdleCruiseVeTool()
    ctx = _make_ctx(tmp_path / "iter_manifest")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "gp_smooth_idle_cruise_ve"
    assert manifest["strategy"] == "matern52_posterior_mean_with_per_cell_clamp"
    assert manifest["output"]["sha256"] == REFERENCE_OUTPUT_SHA
    assert manifest["mask"]["rpm_max_krpm"] == 4.0
    assert manifest["mask"]["tps_max_pct"] == 40.0
    assert manifest["clamp_pct"] == 5.0
    assert manifest["gp_hyperparameters"]["front"]["length_scales"] == [0.3, 0.3]
    assert manifest["gp_hyperparameters"]["rear"]["length_scales"] == [0.3, 0.3]
    assert manifest["front_summary"]["cells_changed_in_mask"] == (
        REFERENCE_FRONT_CELLS_CHANGED
    )
    assert manifest["rear_summary"]["cells_changed_in_mask"] == (
        REFERENCE_REAR_CELLS_CHANGED
    )
    assert manifest["finding"]["kind"] == "idle_ve_noise"


def test_profile_override_changes_mask(tmp_path, fixture_input_sha):
    """Narrowing the smoothing mask changes which cells get touched -> SHA differs."""
    tool = GpSmoothIdleCruiseVeTool()
    ctx_default = _make_ctx(tmp_path / "iter_default")
    ctx_narrow = _make_ctx(
        tmp_path / "iter_narrow",
        profile={
            "id": "seanbike",
            "tool_overrides": {TOOL_NAME: {"mask_rpm_max": 3.0}},
        },
    )
    finding = _make_finding()

    result_default = tool.apply(tool.plan(finding, ctx_default), ctx_default)
    result_narrow = tool.apply(tool.plan(finding, ctx_narrow), ctx_narrow)

    assert result_default.success and result_narrow.success
    assert result_default.sha256 == REFERENCE_OUTPUT_SHA
    assert result_narrow.sha256 != REFERENCE_OUTPUT_SHA
    # Narrower mask -> fewer cells in smoothing region -> fewer cells changed.
    assert result_narrow.cells_changed < result_default.cells_changed


# ---------------------------------------------------------------------------
# End-to-end dispatcher tests with the IdleVeNoiseDetector.
#
# Unlike the other detector tests, this one uses a real seanbike fixture
# (the noisy PC-translated tune that the GP smoother was designed for)
# rather than a planted synthetic surface. The detector reads the base
# PVV's VE tables directly via dynoai.pvv.io.parse_table.
# ---------------------------------------------------------------------------


def test_idle_ve_noise_detector_fires_on_noisy_seanbike_fixture(
    tmp_path, fixture_input_sha
):
    """The detector must flag the seanbike noisy PC-translated tune."""
    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=tmp_path / "iter_noisy",
    )
    ctx.iteration_dir.mkdir(parents=True, exist_ok=True)

    findings = detector.detect(ctx)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "idle_ve_noise"
    assert finding.source == "idle_ve_noise_detector"
    assert finding.suggested_tool == TOOL_NAME
    # Empirical: noisy fixture's max delta % is ~33 (front) / ~32 (rear).
    # Severity for ~33 in the 25-35 mild band maps to ~0.46-0.50.
    assert 0.4 <= finding.severity <= 0.55
    assert finding.confidence > 0.0
    assert finding.tool_params["mask_rpm_max"] == 4.0
    assert finding.tool_params["mask_tps_max"] == 40.0
    # Evidence captures both cylinders' metrics.
    assert finding.evidence["mask_cells"] == 130
    assert finding.evidence["front"]["max_delta_pct"] > 25.0
    assert finding.evidence["rear"]["max_delta_pct"] > 25.0


def test_idle_ve_noise_detector_quiet_on_already_smoothed_pvv(tmp_path):
    """The detector must NOT fire on the post-smoothed reference output.

    This is the discrimination check: the smoothed fixture's max-delta is
    21-23%, below the 25% threshold, so the detector should stay silent.
    """
    smoothed = (
        SESSION_DIR
        / "iterations"
        / "iter_0"
        / "patches"
        / "v_pc_advanced_translation_safeavg140_gpsmooth.pvv"
    )
    assert smoothed.exists()

    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)
    ctx = DetectionContext(
        base_pvv_path=smoothed,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=tmp_path / "iter_smoothed",
    )
    ctx.iteration_dir.mkdir(parents=True, exist_ok=True)

    findings = detector.detect(ctx)

    assert findings == []


def test_dispatcher_step_routes_noisy_fixture_to_reference_sha(
    tmp_path, fixture_input_sha
):
    """Full pipeline: seanbike noisy PVV -> detector -> dispatcher -> reference SHA."""
    tool = GpSmoothIdleCruiseVeTool()
    dispatcher = TuningDispatcher(
        detectors=[IdleVeNoiseDetector(min_max_delta_pct=25.0)],
        tools={tool.name: tool},
    )
    iter_dir = tmp_path / "iter_e2e"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=INPUT_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
    )

    decision = dispatcher.step(ctx)

    assert decision.plan is not None
    assert decision.plan.tool == TOOL_NAME
    assert decision.plan.finding.kind == "idle_ve_noise"
    # Detector tool_params match seanbike reference defaults (mask_rpm_max=4.0,
    # mask_tps_max=40.0), so the patch SHA must match exactly.
    result = dispatcher.apply(decision.plan, ctx)
    assert result.success
    assert result.sha256 == REFERENCE_OUTPUT_SHA
