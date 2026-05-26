"""End-to-end slice test for the IdleVeScale tool.

Reference output captured by running tools/seanbike/patch_idle_ve.py on
v_pc_advanced_translation.pvv (the seanbike fixture with TPS-based VE
tables).

Asserts:
  1. Byte-identical SHA against the seanbike reference.
  2. Idempotency.
  3. plan/apply parity.
  4. Only the two VE tables change.
  5. Out-of-range idle_scale raises in plan().
  6. Manifest captures policy + table stats.
  7. Profile override on idle_scale changes the SHA.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.tools.idle_ve_scale import (
    DEFAULT_VE_FRONT_ID,
    DEFAULT_VE_REAR_ID,
    IdleVeScaleTool,
    TOOL_NAME,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_PVV = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation.pvv"
)
REFERENCE_INPUT_SHA = (
    "bbeec7f4d22aa49aa1daed0a193d2c12e2c020f0088fff85c393a41153362fae"
)
REFERENCE_OUTPUT_SHA = (
    "69431df7019f5365fa87bdbe512c226f02b1acd650d201a865f791d8a55d540e"
)
REFERENCE_CELLS_CHANGED = 72  # across both front + rear


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def fixture_input_sha() -> str:
    assert INPUT_PVV.exists(), f"missing fixture: {INPUT_PVV}"
    sha = _sha256(INPUT_PVV)
    assert sha == REFERENCE_INPUT_SHA, (
        f"input drifted: got {sha}, expected {REFERENCE_INPUT_SHA}"
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
        "kind": "idle_rich",
        "severity": 0.65,
        "confidence": 0.85,
        "evidence": {"idle_scale": 0.75},
        "suggested_tool": TOOL_NAME,
        "tool_params": {},
        "source": "idle_rich_detector",
    }
    params.update(overrides)
    return Finding(**params)


def test_lifted_tool_matches_seanbike_reference_sha(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx = _make_ctx(tmp_path / "iter_ref")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success, f"apply failed: {result.gates_failed}"
    assert result.sha256 == REFERENCE_OUTPUT_SHA, (
        f"byte drift from seanbike idle_ve reference: got {result.sha256}, "
        f"expected {REFERENCE_OUTPUT_SHA}"
    )
    assert result.cells_changed == REFERENCE_CELLS_CHANGED


def test_idempotent_apply_produces_same_sha(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx_a = _make_ctx(tmp_path / "iter_a")
    ctx_b = _make_ctx(tmp_path / "iter_b")
    finding = _make_finding()

    result_a = tool.apply(tool.plan(finding, ctx_a), ctx_a)
    result_b = tool.apply(tool.plan(finding, ctx_b), ctx_b)

    assert result_a.success and result_b.success
    assert result_a.sha256 == result_b.sha256


def test_plan_apply_parity(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx = _make_ctx(tmp_path / "iter_parity")
    finding = _make_finding()

    plan = tool.plan(finding, ctx)
    result = tool.apply(plan, ctx)

    assert result.success
    assert plan.predicted_cells_changed == result.cells_changed


def test_only_ve_tables_change(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx = _make_ctx(tmp_path / "iter_integrity")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    assert set(result.extra["changed_ids"]) == {
        DEFAULT_VE_FRONT_ID,
        DEFAULT_VE_REAR_ID,
    }


def test_sanity_range_rejects_extreme_idle_scale(tmp_path, fixture_input_sha):
    """idle_scale must be in [0.50, 0.95]. Out-of-range raises in plan()."""
    tool = IdleVeScaleTool()
    ctx = _make_ctx(tmp_path / "iter_sanity")
    finding = _make_finding(tool_params={"idle_scale": 0.30})

    with pytest.raises(ValueError, match="idle_scale"):
        tool.plan(finding, ctx)


def test_manifest_captures_policy(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx = _make_ctx(tmp_path / "iter_manifest")
    finding = _make_finding()

    result = tool.apply(tool.plan(finding, ctx), ctx)

    assert result.success
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "idle_ve_scale_patch"
    assert manifest["output"]["sha256"] == REFERENCE_OUTPUT_SHA
    assert manifest["policy"]["idle_scale"] == 0.75
    assert manifest["policy"]["idle_rpm_max"] == 1.5
    assert manifest["policy"]["idle_tps_max"] == 10.0
    assert manifest["policy"]["trans_rpm_max"] == 2.0
    assert manifest["policy"]["trans_tps_max"] == 20.0
    assert manifest["summary"]["total_cells_changed"] == REFERENCE_CELLS_CHANGED
    assert len(manifest["summary"]["table_stats"]) == 2
    assert manifest["finding"]["kind"] == "idle_rich"


def test_profile_override_changes_idle_scale(tmp_path, fixture_input_sha):
    tool = IdleVeScaleTool()
    ctx_default = _make_ctx(tmp_path / "iter_default")
    ctx_override = _make_ctx(
        tmp_path / "iter_override",
        profile={
            "id": "seanbike",
            "tool_overrides": {TOOL_NAME: {"idle_scale": 0.85}},
        },
    )
    finding = _make_finding()

    result_default = tool.apply(tool.plan(finding, ctx_default), ctx_default)
    result_override = tool.apply(tool.plan(finding, ctx_override), ctx_override)

    assert result_default.success and result_override.success
    assert result_default.sha256 == REFERENCE_OUTPUT_SHA
    assert result_override.sha256 != REFERENCE_OUTPUT_SHA
    # Less aggressive reduction (0.85 vs 0.75) -> smaller delta per cell.
    assert result_override.extra["table_stats"][0]["delta_max_abs"] < (
        result_default.extra["table_stats"][0]["delta_max_abs"]
    )
