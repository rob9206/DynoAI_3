"""Integration tests for the patch recommender wire-up.

Verifies:
  1. Surface round-trip: Surface2D -> to_dict -> surface_from_dict yields
     a Surface2D the detectors can consume.
  2. build_default_dispatcher wires 4 detectors + 4 tools and returns a
     dispatcher that can run end-to-end.
  3. recommend_patches() resolves base_pvv from the seanbike layout,
     loads cached payload, runs dispatcher, returns success.
  4. The recommendation includes a real plan when surfaces contain a
     planted spark valley.
  5. Missing inputs (no cached payload, no base PVV) fail closed with a
     useful error.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats
from dynoai.diagnostics import (
    DetectionContext,
    TuningDispatcher,
    build_default_dispatcher,
    surface_from_dict,
    surfaces_from_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEANBIKE_SESSION = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
)
SEANBIKE_BASE_PVV = SEANBIKE_SESSION / "base_tune" / "base.pvv"


def _build_planted_spark_surface(cylinder: str = "front") -> Surface2D:
    """Same fixture used by test_spark_feathered_ramp_slice."""
    rpm_bins = [3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0, 6500.0, 7000.0]
    map_bins = [40.0, 60.0, 80.0, 100.0]

    def cell_value(rpm: float, map_kpa: float) -> float:
        if map_kpa < 80.0:
            return 25.0
        if 5000.0 <= rpm <= 5500.0:
            return 29.0
        return 35.0

    values: list[list[float | None]] = []
    hit_count: list[list[int]] = []
    for rpm in rpm_bins:
        row_v: list[float | None] = []
        row_h: list[int] = []
        for kpa in map_bins:
            row_v.append(cell_value(rpm, kpa))
            row_h.append(20)
        values.append(row_v)
        hit_count.append(row_h)

    return Surface2D(
        surface_id=f"spark_{cylinder}",
        title=f"Spark advance {cylinder}",
        description="planted valley fixture",
        rpm_axis=SurfaceAxis(name="rpm", unit="RPM", bins=rpm_bins),
        map_axis=SurfaceAxis(name="map", unit="kPa", bins=map_bins),
        values=values,
        hit_count=hit_count,
        stats=SurfaceStats(
            min=25.0, max=35.0, mean=30.0,
            non_nan_cells=len(rpm_bins) * len(map_bins),
            total_cells=len(rpm_bins) * len(map_bins),
            total_samples=20 * len(rpm_bins) * len(map_bins),
        ),
    )


# ---------------------------------------------------------------------------
# Surface round-trip
# ---------------------------------------------------------------------------


def test_surface_round_trip_preserves_axes_values_and_hits():
    original = _build_planted_spark_surface("front")
    d = original.to_dict()
    restored = surface_from_dict(d)

    assert restored.surface_id == original.surface_id
    assert restored.rpm_axis.bins == original.rpm_axis.bins
    assert restored.map_axis.bins == original.map_axis.bins
    assert restored.values == original.values
    assert restored.hit_count == original.hit_count
    assert restored.stats.non_nan_cells == original.stats.non_nan_cells


def test_surfaces_from_payload_extracts_all_surface_ids():
    payload = {
        "surfaces": {
            "spark_front": _build_planted_spark_surface("front").to_dict(),
            "spark_rear": _build_planted_spark_surface("rear").to_dict(),
        }
    }
    surfaces = surfaces_from_payload(payload)
    assert set(surfaces.keys()) == {"spark_front", "spark_rear"}
    for s in surfaces.values():
        assert isinstance(s, Surface2D)


def test_surfaces_from_payload_handles_missing_surfaces_key():
    assert surfaces_from_payload({}) == {}


# ---------------------------------------------------------------------------
# build_default_dispatcher
# ---------------------------------------------------------------------------


def test_build_default_dispatcher_wires_all_tools():
    dispatcher = build_default_dispatcher()
    # Inspect via the tools mapping; detectors are private to the dispatcher
    # but their effect is observable via step().
    tool_names = set(dispatcher.tools.keys())
    assert tool_names == {
        "spark_feathered_ramp",
        "spark_knock_hotspot",
        "gp_smooth_idle_cruise_ve",
        "wot_ve_graft",
        "decel_enleanment",
        "accel_enrich",
        "injector_scalar_rebase",
        "idle_ve_scale",
    }


def test_build_default_dispatcher_omits_wot_lean_when_excluded():
    # We can't directly count detectors from the public API, but we CAN
    # check behavior: with include_wot_lean=False and a lean AFR surface,
    # dispatcher.step() should NOT emit a wot_lean finding.
    from tests.unit.test_wot_ve_graft_slice import _build_planted_afr_error_surface

    dispatcher = build_default_dispatcher(include_wot_lean=False)
    surfaces = {"afr_error_front": _build_planted_afr_error_surface("front")}
    ctx = DetectionContext(
        base_pvv_path=SEANBIKE_BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=SEANBIKE_SESSION / "iterations" / "iter_0",
        surfaces=surfaces,
    )
    decision = dispatcher.step(ctx)
    wot_findings = [f for f in decision.findings if f.kind == "wot_lean"]
    assert wot_findings == []


def test_build_default_dispatcher_with_spark_valley_surface_produces_plan(tmp_path):
    """End-to-end smoke: default dispatcher with seanbike base + planted
    spark valley produces *some* plan. Several detectors fire on seanbike
    (the base PVV has aggressive decel enleanment, the planted surface
    shows a spark valley, etc.); the dispatcher picks the highest-ranked
    one. This test asserts the routing path works, not which specific
    tool wins."""
    dispatcher = build_default_dispatcher()
    surfaces = {"spark_front": _build_planted_spark_surface("front")}

    # Use the seanbike base PVV; iter_dir is a tmp output target.
    iter_dir = tmp_path / "iter_test"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=SEANBIKE_BASE_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces=surfaces,
    )
    decision = dispatcher.step(ctx)

    assert decision.plan is not None
    # Plan must come from one of the registered tools.
    assert decision.plan.tool in set(dispatcher.tools.keys())
    # And the planted spark valley must be among the findings (other
    # detectors fire too on the seanbike base; that's expected).
    spark_findings = [f for f in decision.findings if f.kind == "spark_valley"]
    assert len(spark_findings) == 1


# ---------------------------------------------------------------------------
# recommend_patches() (the workflow-level integration)
# ---------------------------------------------------------------------------


def _seanbike_request(tmp_path: Path) -> "PatchRecommendationRequest":
    from api.services.patch_recommender import PatchRecommendationRequest

    return PatchRecommendationRequest(
        run_id="test_run_id",
        vehicle_id="seanbike",
        session_id="dai_2026_0518_pcv_bake_verify",
        donor_pvv_path=None,
        include_wot_lean=False,
    )


def test_recommend_patches_returns_error_when_no_cached_payload(tmp_path):
    from api.services.patch_recommender import recommend_patches

    req = _seanbike_request(tmp_path)
    # No NextGen analysis exists for this synthetic run_id.
    with mock.patch(
        "api.services.patch_recommender.get_nextgen_workflow"
    ) as mock_workflow:
        mock_workflow.return_value.load_cached.return_value = None
        result = recommend_patches(req)

    assert result.success is False
    assert "NextGen analysis not found" in (result.error or "")


def test_recommend_patches_returns_error_when_base_pvv_missing(tmp_path):
    from api.services.patch_recommender import PatchRecommendationRequest, recommend_patches

    req = PatchRecommendationRequest(
        run_id="test_run_id",
        vehicle_id="nonexistent_vehicle",
        session_id="nonexistent_session",
        donor_pvv_path=None,
        include_wot_lean=False,
    )
    with mock.patch(
        "api.services.patch_recommender.get_nextgen_workflow"
    ) as mock_workflow:
        # Pretend the analysis exists so we exercise the next layer.
        mock_workflow.return_value.load_cached.return_value = {"surfaces": {}}
        result = recommend_patches(req)

    assert result.success is False
    assert "Base PVV not found" in (result.error or "")


def test_recommend_patches_succeeds_with_planted_spark_surface(tmp_path):
    """Full happy path: mock the cached payload to inject a planted spark valley,
    then assert the recommender returns a plan via the dispatcher."""
    from api.services.patch_recommender import recommend_patches

    if not SEANBIKE_BASE_PVV.exists():
        pytest.skip(f"seanbike base PVV fixture missing: {SEANBIKE_BASE_PVV}")

    planted_payload = {
        "surfaces": {
            "spark_front": _build_planted_spark_surface("front").to_dict(),
        }
    }
    req = _seanbike_request(tmp_path)
    with mock.patch(
        "api.services.patch_recommender.get_nextgen_workflow"
    ) as mock_workflow:
        mock_workflow.return_value.load_cached.return_value = planted_payload
        result = recommend_patches(req)

    assert result.success is True, f"recommend_patches failed: {result.error}"
    assert result.decision_dict is not None
    assert result.decision_dict["plan"] is not None
    plan = result.decision_dict["plan"]
    # Plan must come from one of the eight registered tools. The exact tool
    # depends on which detector ranks highest — seanbike's base PVV
    # legitimately has multiple issues (aggressive decel, lean accel hot
    # cells, etc.), so the planted spark valley may or may not win.
    assert plan["tool"] in {
        "spark_feathered_ramp",
        "spark_knock_hotspot",
        "gp_smooth_idle_cruise_ve",
        "wot_ve_graft",
        "decel_enleanment",
        "accel_enrich",
        "injector_scalar_rebase",
        "idle_ve_scale",
    }
    assert plan["predicted_cells_changed"] > 0
    assert result.context_meta["base_pvv_path"] == str(SEANBIKE_BASE_PVV)
    assert "spark_front" in result.context_meta["surfaces_loaded"]
    # The planted spark_valley finding must be present even if it didn't win.
    finding_kinds = {f["kind"] for f in result.decision_dict["findings"]}
    assert "spark_valley" in finding_kinds


def test_recommend_patches_serializes_finding_severity_and_confidence(tmp_path):
    """The decision dict must include severity, confidence, and rank_score."""
    from api.services.patch_recommender import recommend_patches

    if not SEANBIKE_BASE_PVV.exists():
        pytest.skip(f"seanbike base PVV fixture missing: {SEANBIKE_BASE_PVV}")

    planted_payload = {
        "surfaces": {
            "spark_front": _build_planted_spark_surface("front").to_dict(),
        }
    }
    req = _seanbike_request(tmp_path)
    with mock.patch(
        "api.services.patch_recommender.get_nextgen_workflow"
    ) as mock_workflow:
        mock_workflow.return_value.load_cached.return_value = planted_payload
        result = recommend_patches(req)

    assert result.success
    findings = result.decision_dict["findings"]
    assert len(findings) > 0
    for f in findings:
        assert "severity" in f
        assert "confidence" in f
        assert "rank_score" in f
        assert f["rank_score"] == pytest.approx(f["severity"] * f["confidence"])
