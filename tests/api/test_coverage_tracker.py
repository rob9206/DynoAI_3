"""
Tests for Coverage Tracker Service (Phase 7)

Validates cross-run coverage aggregation, gap detection, and persistence.
"""

import json
from pathlib import Path

import pytest

from api.services.coverage_tracker import (
    CumulativeCoverage,
    aggregate_run_coverage,
    get_coverage_summary,
    get_cumulative_gaps,
    get_tracker_path,
    load_cumulative_coverage,
    reset_cumulative_coverage,
    save_cumulative_coverage,
)


@pytest.fixture
def sample_surface():
    """Sample surface with hit count data."""
    return {
        "spark_f": {
            "surface_id":
            "spark_f",
            "title":
            "Front Spark Timing",
            "hit_count": [
                [5, 10, 3, 0, 0],
                [12, 15, 8, 2, 0],
                [10, 20, 15, 5, 1],
                [8, 18, 12, 3, 0],
            ],
            "values": [[25, 26, 24, 0, 0]] * 4,
        },
        "afr_error_f": {
            "surface_id":
            "afr_error_f",
            "title":
            "Front AFR Error",
            "hit_count": [
                [8, 12, 5, 1, 0],
                [15, 18, 10, 3, 0],
                [12, 22, 18, 7, 2],
                [10, 20, 15, 5, 1],
            ],
            "values": [[-0.5, -0.3, 0.2, 0, 0]] * 4,
        },
    }


@pytest.fixture
def clean_tracker_dir():
    """Ensure clean state for tests."""
    from api.services.coverage_tracker import TRACKER_DIR

    # Clean up any existing test files
    for file in TRACKER_DIR.glob("test_*.json"):
        file.unlink()

    yield

    # Clean up after tests
    for file in TRACKER_DIR.glob("test_*.json"):
        file.unlink()


class TestCumulativeCoverage:
    """Tests for CumulativeCoverage data class."""

    def test_to_dict(self):
        """Test serialization."""
        coverage = CumulativeCoverage(
            vehicle_id="test_vehicle",
            dyno_signature="dyno_123",
            total_runs=3,
            run_ids=["run1", "run2", "run3"],
            aggregated_hit_count={
                "spark_f": [[5, 10], [8, 12]],
            },
        )

        data = coverage.to_dict()

        assert data["vehicle_id"] == "test_vehicle"
        assert data["dyno_signature"] == "dyno_123"
        assert data["total_runs"] == 3
        assert len(data["run_ids"]) == 3
        assert "spark_f" in data["aggregated_hit_count"]

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "vehicle_id": "test_vehicle",
            "dyno_signature": "dyno_123",
            "total_runs": 2,
            "run_ids": ["run1", "run2"],
            "aggregated_hit_count": {
                "spark_f": [[5, 10], [8, 12]],
            },
            "last_updated": "2024-01-01T00:00:00",
            "created_at": "2024-01-01T00:00:00",
        }

        coverage = CumulativeCoverage.from_dict(data)

        assert coverage.vehicle_id == "test_vehicle"
        assert coverage.total_runs == 2
        assert len(coverage.run_ids) == 2


class TestPersistence:
    """Tests for loading/saving coverage data."""

    def test_get_tracker_path(self):
        """Test path generation."""
        path = get_tracker_path("test_vehicle")

        assert path.name == "test_vehicle.json"
        assert "coverage_tracker" in str(path)

    def test_save_and_load(self, clean_tracker_dir):
        """Test round-trip persistence."""
        coverage = CumulativeCoverage(
            vehicle_id="test_save_load",
            dyno_signature="dyno_456",
            total_runs=1,
            run_ids=["run1"],
            aggregated_hit_count={"spark_f": [[5, 10]]},
        )

        # Save
        success = save_cumulative_coverage(coverage)
        assert success

        # Load
        loaded = load_cumulative_coverage("test_save_load")
        assert loaded is not None
        assert loaded.vehicle_id == "test_save_load"
        assert loaded.total_runs == 1
        assert "spark_f" in loaded.aggregated_hit_count

    def test_load_nonexistent(self):
        """Test loading nonexistent tracker."""
        loaded = load_cumulative_coverage("nonexistent_vehicle")
        assert loaded is None

    def test_reset_coverage(self, clean_tracker_dir):
        """Test reset."""
        # Create tracker
        coverage = CumulativeCoverage(
            vehicle_id="test_reset",
            dyno_signature="dyno_789",
            total_runs=1,
        )
        save_cumulative_coverage(coverage)

        # Verify exists
        assert load_cumulative_coverage("test_reset") is not None

        # Reset
        success = reset_cumulative_coverage("test_reset")
        assert success

        # Verify deleted
        assert load_cumulative_coverage("test_reset") is None


class TestAggregation:
    """Tests for coverage aggregation."""

    def test_aggregate_single_run(self, clean_tracker_dir, sample_surface):
        """Test aggregating first run."""
        coverage = aggregate_run_coverage(
            vehicle_id="test_agg_single",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_abc",
        )

        assert coverage.total_runs == 1
        assert "run1" in coverage.run_ids
        assert "spark_f" in coverage.aggregated_hit_count
        assert "afr_error_f" in coverage.aggregated_hit_count

        # Check hit counts match input
        spark_hits = coverage.aggregated_hit_count["spark_f"]
        assert spark_hits[0][0] == 5
        assert spark_hits[1][1] == 15

    def test_aggregate_multiple_runs(self, clean_tracker_dir, sample_surface):
        """Test aggregating multiple runs."""
        # First run
        coverage1 = aggregate_run_coverage(
            vehicle_id="test_agg_multi",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_def",
        )

        assert coverage1.total_runs == 1

        # Second run (same surfaces)
        coverage2 = aggregate_run_coverage(
            vehicle_id="test_agg_multi",
            run_id="run2",
            surfaces=sample_surface,
            dyno_signature="dyno_def",
        )

        assert coverage2.total_runs == 2
        assert len(coverage2.run_ids) == 2

        # Hit counts should be doubled
        spark_hits = coverage2.aggregated_hit_count["spark_f"]
        assert spark_hits[0][0] == 10  # 5 + 5
        assert spark_hits[1][1] == 30  # 15 + 15

    def test_aggregate_duplicate_run_id(self, clean_tracker_dir,
                                        sample_surface):
        """Test aggregating same run ID twice doesn't duplicate in run_ids list."""
        # First aggregate
        aggregate_run_coverage(
            vehicle_id="test_agg_dup",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_ghi",
        )

        # Aggregate again with same run_id
        coverage = aggregate_run_coverage(
            vehicle_id="test_agg_dup",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_ghi",
        )

        # run_ids should only have one entry
        assert coverage.run_ids.count("run1") == 1
        assert coverage.total_runs == 2  # But total_runs increments


class TestGapDetection:
    """Tests for coverage gap detection."""

    def test_get_cumulative_gaps(self, clean_tracker_dir, sample_surface):
        """Test gap detection."""
        # Aggregate a run
        aggregate_run_coverage(
            vehicle_id="test_gaps",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_jkl",
        )

        # Get gaps
        gaps = get_cumulative_gaps("test_gaps", min_hits=5)

        assert isinstance(gaps, list)
        # Should have gaps in regions with < 5 hits

        # Check gap structure
        if len(gaps) > 0:
            gap = gaps[0]
            assert "surface_id" in gap
            assert "region_name" in gap
            assert "rpm_range" in gap
            assert "map_range" in gap
            assert "empty_cells" in gap
            assert "total_cells" in gap
            assert "coverage_pct" in gap
            assert "impact" in gap

    def test_gaps_no_tracker(self):
        """Test gap detection for nonexistent vehicle."""
        gaps = get_cumulative_gaps("nonexistent_vehicle")
        assert gaps == []


class TestCoverageSummary:
    """Tests for coverage summary."""

    def test_get_coverage_summary(self, clean_tracker_dir, sample_surface):
        """Test summary generation."""
        # Aggregate runs
        aggregate_run_coverage(
            vehicle_id="test_summary",
            run_id="run1",
            surfaces=sample_surface,
            dyno_signature="dyno_mno",
        )

        aggregate_run_coverage(
            vehicle_id="test_summary",
            run_id="run2",
            surfaces=sample_surface,
            dyno_signature="dyno_mno",
        )

        # Get summary
        summary = get_coverage_summary("test_summary")

        assert summary is not None
        assert summary["vehicle_id"] == "test_summary"
        assert summary["total_runs"] == 2
        assert len(summary["run_ids"]) == 2
        assert summary["dyno_signature"] == "dyno_mno"
        assert "surfaces" in summary
        assert "total_cells" in summary
        assert "covered_cells" in summary
        assert "coverage_pct" in summary
        assert summary["coverage_pct"] >= 0
        assert summary["coverage_pct"] <= 100

    def test_summary_no_tracker(self):
        """Test summary for nonexistent vehicle."""
        summary = get_coverage_summary("nonexistent_vehicle")
        assert summary is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_surfaces(self, clean_tracker_dir):
        """Test aggregating with empty surfaces."""
        coverage = aggregate_run_coverage(
            vehicle_id="test_empty",
            run_id="run1",
            surfaces={},
            dyno_signature="dyno_pqr",
        )

        assert coverage.total_runs == 1
        assert len(coverage.aggregated_hit_count) == 0

    def test_surface_without_hit_count(self, clean_tracker_dir):
        """Test surface without hit_count field."""
        surfaces = {
            "spark_f": {
                "surface_id": "spark_f",
                "title": "Spark",
                "values": [[1, 2], [3, 4]],
                # No hit_count
            }
        }

        coverage = aggregate_run_coverage(
            vehicle_id="test_no_hits",
            run_id="run1",
            surfaces=surfaces,
            dyno_signature="dyno_stu",
        )

        # Should not crash, but spark_f won't be in aggregated_hit_count
        assert "spark_f" not in coverage.aggregated_hit_count

    def test_mismatched_matrix_sizes(self, clean_tracker_dir):
        """Test handling of mismatched matrix sizes across runs."""
        # First run with 2x2 matrix
        surfaces1 = {
            "spark_f": {
                "surface_id": "spark_f",
                "hit_count": [[5, 10], [8, 12]],
            }
        }

        aggregate_run_coverage(
            vehicle_id="test_mismatch",
            run_id="run1",
            surfaces=surfaces1,
            dyno_signature="dyno_vwx",
        )

        # Second run with 3x3 matrix (shouldn't crash)
        surfaces2 = {
            "spark_f": {
                "surface_id": "spark_f",
                "hit_count": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            }
        }

        coverage = aggregate_run_coverage(
            vehicle_id="test_mismatch",
            run_id="run2",
            surfaces=surfaces2,
            dyno_signature="dyno_vwx",
        )

        # Should have aggregated without crashing
        assert coverage.total_runs == 2
