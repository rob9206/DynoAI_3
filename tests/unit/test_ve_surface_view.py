"""Tests for dynoai/pvv/surface_view: PVV VE tables -> Surface2D views.

Plus the IdleVeNoiseDetector's surface-first path (it should produce the
same finding whether VE data comes from ctx.surfaces or from a direct
ctx.base_pvv_path parse).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dynoai.core.surface_builder import Surface2D
from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.detectors.idle_ve_noise import IdleVeNoiseDetector
from dynoai.pvv.surface_view import (
    DEFAULT_VE_FRONT_ID,
    DEFAULT_VE_REAR_ID,
    load_ve_surfaces,
    ve_surface_from_pvv,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
# v_pc_advanced_translation_safeavg140.pvv has both TPS-based VE tables
# and is the canonical noisy fixture used by the GP smoother tests.
NOISY_PVV = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation_safeavg140.pvv"
)
SMOOTHED_PVV = (
    REPO_ROOT
    / "vehicles"
    / "seanbike"
    / "sessions"
    / "dai_2026_0518_pcv_bake_verify"
    / "iterations"
    / "iter_0"
    / "patches"
    / "v_pc_advanced_translation_safeavg140_gpsmooth.pvv"
)


def test_load_ve_surfaces_returns_both_surfaces_when_present():
    surfaces = load_ve_surfaces(NOISY_PVV)
    assert set(surfaces.keys()) == {"ve_front", "ve_rear"}
    for key, surface in surfaces.items():
        assert isinstance(surface, Surface2D)
        assert surface.surface_id == key
        assert surface.mask_info == "pvv_tune_view"
        # Both VE tables on this fixture share shape and axes.
        assert len(surface.rpm_axis.bins) > 0
        assert len(surface.map_axis.bins) > 0


def test_load_ve_surfaces_returns_empty_for_pvv_without_tables(tmp_path):
    """A nonexistent PVV path yields {} without raising."""
    assert load_ve_surfaces(tmp_path / "does_not_exist.pvv") == {}


def test_load_ve_surfaces_partial_when_only_one_table_present():
    """Custom front_id that exists + custom rear_id that doesn't -> just front."""
    surfaces = load_ve_surfaces(
        NOISY_PVV,
        front_id=DEFAULT_VE_FRONT_ID,
        rear_id="tbl_does_not_exist",
    )
    assert set(surfaces.keys()) == {"ve_front"}


def test_ve_surface_from_pvv_returns_surface_with_expected_axes():
    surface = ve_surface_from_pvv(
        NOISY_PVV,
        table_id=DEFAULT_VE_FRONT_ID,
        surface_id="ve_front",
    )
    assert surface.surface_id == "ve_front"
    assert surface.rpm_axis.unit == "kRPM"
    assert surface.map_axis.unit == "%"
    # Sanity: stats reflect the loaded data.
    assert surface.stats.non_nan_cells > 0
    assert surface.stats.total_cells == surface.stats.non_nan_cells


def test_ve_surface_from_pvv_raises_for_unknown_table():
    with pytest.raises(ValueError, match="tbl_unknown"):
        ve_surface_from_pvv(
            NOISY_PVV,
            table_id="tbl_unknown",
            surface_id="bogus",
        )


def test_idle_ve_noise_detector_prefers_surfaces_when_present(tmp_path):
    """The detector must use ctx.surfaces when both ve_front and ve_rear
    are populated, NOT re-parse the PVV."""
    surfaces = load_ve_surfaces(NOISY_PVV)
    assert set(surfaces.keys()) == {"ve_front", "ve_rear"}

    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)
    iter_dir = tmp_path / "iter_surface"
    iter_dir.mkdir(parents=True, exist_ok=True)
    # Deliberately leave base_pvv_path pointing at a nonexistent file so
    # the only viable path is the surface route. If the detector ignores
    # surfaces and falls through to PVV, this test will produce 0 findings
    # and fail the assertion below.
    ctx = DetectionContext(
        base_pvv_path=tmp_path / "no_pvv_here.pvv",
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces=surfaces,
    )

    findings = detector.detect(ctx)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "idle_ve_noise"
    # Noisy fixture: max_delta_pct around 33, severity in mild band.
    assert finding.evidence["peak_max_delta_pct"] > 25.0


def test_idle_ve_noise_detector_falls_back_to_pvv_when_surfaces_missing(tmp_path):
    """When ctx.surfaces is empty, the detector reads the PVV directly
    (legacy/fallback path). Same finding as the surface path."""
    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)
    iter_dir = tmp_path / "iter_pvv"
    iter_dir.mkdir(parents=True, exist_ok=True)
    ctx = DetectionContext(
        base_pvv_path=NOISY_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_dir,
        surfaces={},
    )

    findings = detector.detect(ctx)

    assert len(findings) == 1
    assert findings[0].kind == "idle_ve_noise"


def test_surface_and_pvv_paths_produce_equivalent_findings(tmp_path):
    """Both detection paths must compute the same metric on the same data."""
    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)

    # Surface path
    surfaces = load_ve_surfaces(NOISY_PVV)
    iter_a = tmp_path / "iter_surface"
    iter_a.mkdir(parents=True, exist_ok=True)
    ctx_surface = DetectionContext(
        base_pvv_path=tmp_path / "no_pvv.pvv",
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_a,
        surfaces=surfaces,
    )
    f_surface = detector.detect(ctx_surface)[0]

    # PVV path
    iter_b = tmp_path / "iter_pvv"
    iter_b.mkdir(parents=True, exist_ok=True)
    ctx_pvv = DetectionContext(
        base_pvv_path=NOISY_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_b,
        surfaces={},
    )
    f_pvv = detector.detect(ctx_pvv)[0]

    # The metric must be byte-identical (same numpy ops, same input bits).
    assert f_surface.evidence["peak_max_delta_pct"] == pytest.approx(
        f_pvv.evidence["peak_max_delta_pct"]
    )
    assert f_surface.severity == pytest.approx(f_pvv.severity)
    assert f_surface.confidence == pytest.approx(f_pvv.confidence)


def test_smoothed_pvv_quiet_in_both_paths(tmp_path):
    """Smoothed PVV (gp_smooth output) must produce no findings via either
    path (max_delta_pct ~22, below the 25% threshold)."""
    detector = IdleVeNoiseDetector(min_max_delta_pct=25.0)

    surfaces = load_ve_surfaces(SMOOTHED_PVV)
    iter_a = tmp_path / "iter_smoothed_surface"
    iter_a.mkdir(parents=True, exist_ok=True)
    ctx_surface = DetectionContext(
        base_pvv_path=tmp_path / "no_pvv.pvv",
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_a,
        surfaces=surfaces,
    )
    assert detector.detect(ctx_surface) == []

    iter_b = tmp_path / "iter_smoothed_pvv"
    iter_b.mkdir(parents=True, exist_ok=True)
    ctx_pvv = DetectionContext(
        base_pvv_path=SMOOTHED_PVV,
        vehicle_profile={"id": "seanbike", "tool_overrides": {}},
        iteration_dir=iter_b,
        surfaces={},
    )
    assert detector.detect(ctx_pvv) == []
