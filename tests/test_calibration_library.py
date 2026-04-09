"""Tests for calibration-library ingest, matching, and corpus health stats."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dynoai_v3.calibration_library import CalibrationLibrary
from dynoai_v3.template_library import HardwareConfig


def _hardware_config(engine_family: str = "m8_114", displacement_ci: int = 114) -> HardwareConfig:
    return HardwareConfig(
        engine_family=engine_family,
        displacement_ci=displacement_ci,
        cam_spec="stock",
        exhaust_type="2into1",
        air_cleaner="high_flow",
    )


def _table(rows: int, cols: int, base: float = 85.0) -> list[list[float]]:
    arr = np.full((rows, cols), base, dtype=np.float64)
    for r_idx in range(rows):
        for c_idx in range(cols):
            arr[r_idx, c_idx] += (r_idx * 0.5) + (c_idx * 0.25)
    return arr.tolist()


def test_ingest_from_parsed_is_idempotent_for_same_source(tmp_path: Path) -> None:
    lib = CalibrationLibrary(tmp_path / "library")
    cfg = _hardware_config()
    rpm_bins = [1500.0, 2000.0, 2500.0]
    map_bins = [40.0, 60.0, 80.0]
    front = _table(3, 3)
    rear = _table(3, 3, base=84.0)
    afr_targets = {40: 14.2, 60: 13.7, 80: 13.0}

    first_id = lib.ingest_from_parsed(
        config=cfg,
        ve_front=front,
        ve_rear=rear,
        afr_targets=afr_targets,
        rpm_bins=rpm_bins,
        map_bins=map_bins,
        source_name="mastertune:C:/cal/bikeA.mt8",
        source_path="C:/cal/bikeA.mt8",
        notes="test-import",
    )
    second_id = lib.ingest_from_parsed(
        config=cfg,
        ve_front=front,
        ve_rear=rear,
        afr_targets=afr_targets,
        rpm_bins=rpm_bins,
        map_bins=map_bins,
        source_name="mastertune:C:/cal/bikeA.mt8",
        source_path="C:/cal/bikeA.mt8",
        notes="test-import-rerun",
    )

    assert first_id == second_id
    listing = lib.list_entries(engine_family=cfg.engine_family, limit=50, offset=0)
    assert listing["total"] == 1
    entry = lib.get_entry(first_id)
    assert int(entry.metadata.get("ingest_count", 0)) == 2
    assert str(entry.metadata.get("source_identity", "")).strip() != ""


def test_find_matches_respects_min_similarity(tmp_path: Path) -> None:
    lib = CalibrationLibrary(tmp_path / "library")
    cfg = _hardware_config(engine_family="tc_110", displacement_ci=110)
    rpm_bins = [1500.0, 2500.0, 3500.0]
    map_bins = [40.0, 60.0, 80.0]
    lib.ingest_from_parsed(
        config=cfg,
        ve_front=_table(3, 3, base=88.0),
        ve_rear=None,
        afr_targets={40: 14.1, 60: 13.8, 80: 13.2},
        rpm_bins=rpm_bins,
        map_bins=map_bins,
        source_name="mastertune:C:/cal/tc110_a.mt8",
        source_path="C:/cal/tc110_a.mt8",
    )

    weak_query = HardwareConfig(
        engine_family="tc_110",
        displacement_ci=110,
        cam_spec="other",
        exhaust_type="open",
        air_cleaner="velocity_stack",
        compression_ratio=11.8,
    )
    strict_matches = lib.find_matches(weak_query, top_n=5, min_similarity=0.95)
    assert strict_matches == []

    exact_matches = lib.find_matches(cfg, top_n=5, min_similarity=0.95)
    assert len(exact_matches) == 1
    assert exact_matches[0].similarity_score >= 0.95


def test_stats_reports_corpus_health_fields(tmp_path: Path) -> None:
    lib = CalibrationLibrary(tmp_path / "library")
    cfg = _hardware_config(engine_family="m8_117", displacement_ci=117)
    lib.ingest_from_parsed(
        config=cfg,
        ve_front=_table(2, 2, base=90.0),
        ve_rear=None,
        afr_targets={},
        rpm_bins=[2000.0, 3000.0],
        map_bins=[50.0, 80.0],
        source_name="mastertune:C:/cal/m8_117_a.mt8",
        source_path="C:/cal/m8_117_a.mt8",
    )

    stats = lib.stats()
    assert stats["total_entries"] == 1
    assert stats["by_family"]["m8_117"] == 1
    assert stats["missing_rear_count"] == 1
    assert stats["missing_afr_targets_count"] == 1
    assert stats["bad_shape_count"] == 0
    assert stats["duplicate_source_identities"] == 0


def test_family_alias_matches_twin_cam_via_tc_prefix(tmp_path: Path) -> None:
    """tc_103 query should find entries stored under twin_cam via _FAMILY_ALIASES."""
    lib = CalibrationLibrary(tmp_path / "library")
    stored_cfg = HardwareConfig(
        engine_family="twin_cam",
        displacement_ci=103,
        cam_spec="stock",
        exhaust_type="slip_on",
    )
    rpm_bins = [1500.0, 2500.0, 3500.0]
    map_bins = [40.0, 60.0, 80.0]
    lib.ingest_from_parsed(
        config=stored_cfg,
        ve_front=_table(3, 3, base=87.0),
        ve_rear=_table(3, 3, base=86.0),
        afr_targets={40: 14.0, 60: 13.5, 80: 12.8},
        rpm_bins=rpm_bins,
        map_bins=map_bins,
        source_name="mastertune:test.mt8",
        source_path="test.mt8",
    )

    query = HardwareConfig(
        engine_family="tc_103",
        displacement_ci=103,
        cam_spec="stock",
        exhaust_type="slip_on",
    )
    matches = lib.find_matches(query, top_n=5, min_similarity=0.0)
    assert len(matches) == 1
    assert matches[0].similarity_score > 0.5


def test_policy_defaults_are_within_validated_ranges() -> None:
    """Ensure default policy config stays within shadow-validated safe ranges."""
    from api.config import CalibrationLibraryPolicyConfig

    policy = CalibrationLibraryPolicyConfig()
    assert 1 <= policy.top_n <= 10, f"top_n={policy.top_n} outside [1,10]"
    assert 0.40 <= policy.min_similarity <= 0.80, (
        f"min_similarity={policy.min_similarity} outside validated [0.40,0.80]"
    )
    assert 1 <= policy.min_matches <= 5, f"min_matches={policy.min_matches} outside [1,5]"
