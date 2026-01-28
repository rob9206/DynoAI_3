"""
Tests for dynoai.core.surface_builder module.

Tests verify:
- Surface shapes match bin dimensions
- min_samples_per_cell masks low-hit cells to None
- Aggregation methods work correctly
"""

import numpy as np
import pandas as pd
import pytest

from dynoai.core.mode_detection import ModeTag
from dynoai.core.surface_builder import (
    Surface2D,
    SurfaceSpec,
    build_standard_surfaces,
    build_surface,
)


class TestSurfaceBuilderShapes:
    """Tests for surface shape validation."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame with known values."""
        np.random.seed(42)  # Deterministic
        n_samples = 500

        # Create data that spans the RPM/MAP grid
        rpm_values = np.linspace(1500, 6500, n_samples)
        map_values = np.linspace(30, 100, n_samples)

        df = pd.DataFrame({
            "rpm":
            rpm_values,
            "map_kpa":
            map_values,
            "tps":
            np.linspace(10, 90, n_samples),
            "spark_f":
            25 - np.abs(rpm_values - 4000) * 0.002,
            "spark_r":
            24 - np.abs(rpm_values - 3800) * 0.002,
            "afr_error_f":
            np.random.uniform(-0.5, 0.5, n_samples),
            "afr_error_r":
            np.random.uniform(-0.5, 0.5, n_samples),
            "mode":
            "cruise",  # All cruise for simplicity
        })
        return df

    def test_surface_values_shape_matches_bins(self, sample_df):
        """Surface values matrix shape matches (rpm_bins, map_bins)."""
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        map_bins = [40, 60, 80, 100]

        spec = SurfaceSpec(
            value_column="spark_f",
            filter_modes=[ModeTag.CRUISE],
            min_samples_per_cell=1,
        )

        surface = build_surface(sample_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        assert len(surface.values) == len(rpm_bins)
        assert len(surface.values[0]) == len(map_bins)
        assert surface.shape == (len(rpm_bins), len(map_bins))

    def test_hit_count_shape_matches_values(self, sample_df):
        """Hit count matrix has same shape as values matrix."""
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        map_bins = [40, 60, 80, 100]

        spec = SurfaceSpec(
            value_column="spark_f",
            min_samples_per_cell=1,
        )

        surface = build_surface(sample_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        assert len(surface.hit_count) == len(surface.values)
        assert len(surface.hit_count[0]) == len(surface.values[0])

    def test_axis_bins_stored_correctly(self, sample_df):
        """Surface axis bins match input bins."""
        rpm_bins = [1500, 2500, 3500, 4500, 5500]
        map_bins = [35, 50, 65, 80, 95]

        spec = SurfaceSpec(
            value_column="spark_f",
            min_samples_per_cell=1,
        )

        surface = build_surface(sample_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        assert surface.rpm_axis.bins == rpm_bins
        assert surface.map_axis.bins == map_bins


class TestMinSamplesPerCell:
    """Tests for min_samples_per_cell masking behavior."""

    @pytest.fixture
    def sparse_df(self):
        """Create DataFrame with sparse data coverage."""
        np.random.seed(42)  # Set seed FIRST for consistency

        # Only populate specific cells with enough data
        data_rows = []

        # Cell at (3000, 60) with many samples - bins to (3000, 60)
        for _ in range(10):
            data_rows.append({
                "rpm": 3000,  # Exact bin value
                "map_kpa": 60,  # Exact bin value
                "spark_f": 25.0,
                "mode": "cruise",
            })

        # Cell at (4000, 80) with many samples - bins to (4000, 80)
        for _ in range(10):
            data_rows.append({
                "rpm": 4000,  # Exact bin value
                "map_kpa": 80,  # Exact bin value
                "spark_f": 22.0,
                "mode": "cruise",
            })

        # Cell at (5000, 60) with only 2 samples (below threshold)
        for _ in range(2):
            data_rows.append({
                "rpm": 5000,  # Exact bin value
                "map_kpa": 60,  # Exact bin value
                "spark_f": 20.0,
                "mode": "cruise",
            })

        return pd.DataFrame(data_rows)

    def test_low_hit_cells_masked_to_none(self, sparse_df):
        """Cells with fewer samples than min_samples_per_cell are None."""
        # Use bins that exactly match our data points
        rpm_bins = [3000, 4000, 5000]
        map_bins = [60, 80]

        spec = SurfaceSpec(
            value_column="spark_f",
            min_samples_per_cell=5,  # Require at least 5 samples
        )

        surface = build_surface(sparse_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        # Count non-None cells
        non_none_count = sum(1 for row in surface.values for val in row
                             if val is not None)

        # Should have 2 cells with enough data:
        # - (3000, 60) has 10 samples
        # - (4000, 80) has 10 samples
        # The (5000, 60) cell has only 2 samples, should be None
        assert non_none_count == 2

    def test_high_hit_cells_have_values(self, sparse_df):
        """Cells with enough samples have computed values."""
        rpm_bins = [3000, 4000, 5000]
        map_bins = [60, 80]

        spec = SurfaceSpec(
            value_column="spark_f",
            min_samples_per_cell=3,
        )

        surface = build_surface(sparse_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        # Find cells with values
        cells_with_values = [(r, c, surface.values[r][c])
                             for r in range(len(surface.values))
                             for c in range(len(surface.values[r]))
                             if surface.values[r][c] is not None]

        # Should have some non-None values (at least the 2 high-hit cells)
        assert len(cells_with_values) >= 2

    def test_min_samples_zero_includes_all(self, sparse_df):
        """Setting min_samples_per_cell=0 includes all cells with any data."""
        rpm_bins = [3000, 4000, 5000]
        map_bins = [60, 80]

        spec = SurfaceSpec(
            value_column="spark_f",
            min_samples_per_cell=0,  # Include all
        )

        surface = build_surface(sparse_df,
                                spec,
                                rpm_bins=rpm_bins,
                                map_bins=map_bins)

        # Count non-None cells
        non_none_count = sum(1 for row in surface.values for val in row
                             if val is not None)

        # Should include the sparse cell now (3 cells total have data)
        assert non_none_count >= 3


class TestSurfaceAggregation:
    """Tests for different aggregation methods."""

    @pytest.fixture
    def multi_value_df(self):
        """Create DataFrame with multiple values per cell for aggregation testing."""
        np.random.seed(42)

        # Create data with known values at specific cell
        data_rows = []
        values = [10, 20, 30, 40, 50]  # Known values to aggregate

        for val in values:
            data_rows.append({
                "rpm": 3000,
                "map_kpa": 60,
                "test_val": val,
                "mode": "cruise",
            })

        return pd.DataFrame(data_rows)

    def test_mean_aggregation(self, multi_value_df):
        """Mean aggregation computes average."""
        spec = SurfaceSpec(
            value_column="test_val",
            aggregation="mean",
            min_samples_per_cell=1,
        )

        surface = build_surface(
            multi_value_df,
            spec,
            rpm_bins=[3000],
            map_bins=[60],
        )

        # Mean of [10, 20, 30, 40, 50] = 30
        val = surface.values[0][0]
        assert val is not None
        assert abs(val - 30) < 1  # Allow for weighting effects

    def test_max_aggregation(self, multi_value_df):
        """Max aggregation returns maximum value."""
        spec = SurfaceSpec(
            value_column="test_val",
            aggregation="max",
            min_samples_per_cell=1,
        )

        surface = build_surface(
            multi_value_df,
            spec,
            rpm_bins=[3000],
            map_bins=[60],
        )

        val = surface.values[0][0]
        assert val is not None
        assert val == 50  # Max of [10, 20, 30, 40, 50]

    def test_min_aggregation(self, multi_value_df):
        """Min aggregation returns minimum value."""
        spec = SurfaceSpec(
            value_column="test_val",
            aggregation="min",
            min_samples_per_cell=1,
        )

        surface = build_surface(
            multi_value_df,
            spec,
            rpm_bins=[3000],
            map_bins=[60],
        )

        val = surface.values[0][0]
        assert val is not None
        assert val == 10  # Min of [10, 20, 30, 40, 50]


class TestBuildStandardSurfaces:
    """Tests for build_standard_surfaces convenience function."""

    @pytest.fixture
    def full_df(self):
        """Create DataFrame with all expected columns."""
        np.random.seed(42)
        n = 100

        df = pd.DataFrame({
            "rpm": np.linspace(2000, 6000, n),
            "map_kpa": np.linspace(40, 90, n),
            "tps": np.linspace(20, 80, n),
            "spark_f": np.full(n, 25.0),
            "spark_r": np.full(n, 24.0),
            "afr_error_f": np.random.uniform(-0.3, 0.3, n),
            "afr_error_r": np.random.uniform(-0.3, 0.3, n),
            "mode": "cruise",
        })
        return df

    def test_builds_spark_surfaces(self, full_df):
        """build_standard_surfaces creates spark surfaces when available."""
        surfaces = build_standard_surfaces(full_df)

        assert "spark_front" in surfaces
        assert "spark_rear" in surfaces

    def test_builds_afr_error_surfaces(self, full_df):
        """build_standard_surfaces creates AFR error surfaces when available."""
        surfaces = build_standard_surfaces(full_df)

        assert "afr_error_front" in surfaces
        assert "afr_error_rear" in surfaces

    def test_surface_ids_match_keys(self, full_df):
        """Surface IDs in objects match dictionary keys."""
        surfaces = build_standard_surfaces(full_df)

        for key, surface in surfaces.items():
            assert surface.surface_id == key


class TestSurfaceStatistics:
    """Tests for surface statistics computation."""

    @pytest.fixture
    def known_values_df(self):
        """Create DataFrame with known values for statistics validation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

        data_rows = []
        for val in values:
            data_rows.append({
                "rpm": 3000,
                "map_kpa": 60,
                "test_val": val,
                "mode": "cruise",
            })

        return pd.DataFrame(data_rows)

    def test_stats_computed_correctly(self, known_values_df):
        """Surface statistics are computed from actual values."""
        spec = SurfaceSpec(
            value_column="test_val",
            min_samples_per_cell=1,
        )

        surface = build_surface(
            known_values_df,
            spec,
            rpm_bins=[3000],
            map_bins=[60],
        )

        stats = surface.stats

        # With weighted binning, exact values may vary slightly
        assert stats.total_samples > 0
        assert stats.non_nan_cells == 1
        assert stats.total_cells == 1
        assert stats.coverage_pct == 100.0
