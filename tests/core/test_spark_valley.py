"""
Tests for dynoai.core.spark_valley module.

Tests verify:
- Valley detection with known synthetic data
- rpm_center matches expected location
- depth_deg approximately matches expected depth
- rpm_band bounds are sensible
"""

import pytest

from dynoai.core.spark_valley import (
    SparkValleyFinding,
    detect_spark_valley,
    detect_valleys_multi_cylinder,
)
from dynoai.core.surface_builder import Surface2D, SurfaceAxis, SurfaceStats


def create_synthetic_surface(
    rpm_bins: list,
    map_bins: list,
    timing_func,
    surface_id: str = "spark_test",
    min_hits: int = 5,
) -> Surface2D:
    """
    Create a synthetic Surface2D with controlled timing values.

    Args:
        rpm_bins: List of RPM bin values
        map_bins: List of MAP bin values
        timing_func: Function(rpm, map_kpa) -> timing value
        surface_id: Surface identifier
        min_hits: Hit count to assign to each cell

    Returns:
        Surface2D with computed values
    """
    values = []
    hit_count = []

    for rpm in rpm_bins:
        row_values = []
        row_hits = []
        for map_kpa in map_bins:
            val = timing_func(rpm, map_kpa)
            row_values.append(val)
            row_hits.append(min_hits)
        values.append(row_values)
        hit_count.append(row_hits)

    # Compute stats
    flat_values = [v for row in values for v in row if v is not None]
    stats = SurfaceStats(
        min=min(flat_values) if flat_values else None,
        max=max(flat_values) if flat_values else None,
        mean=sum(flat_values) / len(flat_values) if flat_values else None,
        non_nan_cells=len(flat_values),
        total_cells=len(rpm_bins) * len(map_bins),
        total_samples=len(flat_values) * min_hits,
    )

    return Surface2D(
        surface_id=surface_id,
        title=f"Test {surface_id}",
        description="Synthetic test surface",
        rpm_axis=SurfaceAxis(name="RPM", unit="rpm", bins=rpm_bins),
        map_axis=SurfaceAxis(name="MAP", unit="kPa", bins=map_bins),
        values=values,
        hit_count=hit_count,
        stats=stats,
    )


class TestSparkValleyDetection:
    """Tests for spark valley detection with synthetic data."""

    @pytest.fixture
    def valley_surface(self):
        """
        Create surface with a known valley at 4000 RPM.

        Timing profile:
        - Starts at 30° at low RPM
        - Dips to 22° at 4000 RPM (valley)
        - Rises back to 28° at high RPM
        """
        rpm_bins = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000]
        map_bins = [60, 70, 80, 90]  # High MAP for valley detection

        def timing_with_valley(rpm: float, map_kpa: float) -> float:
            """Generate timing with valley at 4000 RPM."""
            # Base timing decreases with MAP (more retard at high load)
            base = 32 - (map_kpa - 60) * 0.1

            # Add valley centered at 4000 RPM
            # Valley depth is ~8 degrees
            valley_depth = 8 * (1 - abs(rpm - 4000) / 2000)
            valley_depth = max(0, valley_depth)

            return base - valley_depth

        return create_synthetic_surface(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            timing_func=timing_with_valley,
            surface_id="spark_front",
        )

    def test_detects_valley_at_expected_rpm(self, valley_surface):
        """Valley detection finds valley near 4000 RPM."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        # Valley should be detected near 4000 RPM (within 500 RPM tolerance)
        assert abs(finding.rpm_center - 4000) <= 500

    def test_valley_depth_approximately_correct(self, valley_surface):
        """Detected valley depth is approximately correct."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        # Valley depth should be around 6-10 degrees
        assert 4 <= finding.depth_deg <= 12

    def test_rpm_band_contains_center(self, valley_surface):
        """Valley rpm_band contains rpm_center."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        low, high = finding.rpm_band
        assert low <= finding.rpm_center <= high

    def test_rpm_band_bounds_sensible(self, valley_surface):
        """Valley rpm_band has sensible bounds."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        low, high = finding.rpm_band

        # Band should be at least 500 RPM wide
        assert high - low >= 500
        # Band should be within data range
        assert low >= 2000
        assert high <= 6000

    def test_confidence_score_valid(self, valley_surface):
        """Confidence score is between 0 and 1."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        assert 0.0 <= finding.confidence <= 1.0

    def test_evidence_list_populated(self, valley_surface):
        """Evidence list contains analysis notes."""
        findings = detect_spark_valley(valley_surface, high_map_min_kpa=80.0)

        assert len(findings) >= 1

        finding = findings[0]
        assert len(finding.evidence) > 0


class TestNoValleyDetection:
    """Tests for cases where no valley should be detected."""

    @pytest.fixture
    def flat_surface(self):
        """Create surface with flat (no valley) timing."""
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        map_bins = [60, 70, 80, 90]

        def flat_timing(rpm: float, map_kpa: float) -> float:
            """Constant timing - no valley."""
            return 28.0

        return create_synthetic_surface(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            timing_func=flat_timing,
            surface_id="spark_flat",
        )

    @pytest.fixture
    def monotonic_surface(self):
        """Create surface with monotonically increasing timing."""
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        map_bins = [60, 70, 80, 90]

        def increasing_timing(rpm: float, map_kpa: float) -> float:
            """Timing increases with RPM - no valley."""
            return 20 + (rpm - 2000) * 0.002

        return create_synthetic_surface(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            timing_func=increasing_timing,
            surface_id="spark_increasing",
        )

    def test_no_valley_in_flat_timing(self, flat_surface):
        """No valley detected in flat timing surface."""
        findings = detect_spark_valley(flat_surface, high_map_min_kpa=80.0)

        # Should find no valleys (flat line has no minimum)
        assert len(findings) == 0

    def test_no_valley_in_monotonic_timing(self, monotonic_surface):
        """No valley detected in monotonically increasing timing."""
        findings = detect_spark_valley(monotonic_surface,
                                       high_map_min_kpa=80.0)

        # Should find no valleys (monotonic has no local minimum)
        assert len(findings) == 0


class TestMultiCylinderValley:
    """Tests for detect_valleys_multi_cylinder function."""

    @pytest.fixture
    def cylinder_surfaces(self):
        """Create front and rear surfaces with different valley locations."""
        rpm_bins = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000]
        map_bins = [70, 80, 90]

        def front_timing(rpm: float, map_kpa: float) -> float:
            """Front cylinder valley at 4000 RPM."""
            base = 30 - (map_kpa - 70) * 0.1
            valley_depth = 7 * (1 - abs(rpm - 4000) / 2000)
            return base - max(0, valley_depth)

        def rear_timing(rpm: float, map_kpa: float) -> float:
            """Rear cylinder valley at 3800 RPM (slightly earlier)."""
            base = 29 - (map_kpa - 70) * 0.1
            valley_depth = 8 * (1 - abs(rpm - 3800) / 2000)
            return base - max(0, valley_depth)

        return {
            "spark_front":
            create_synthetic_surface(
                rpm_bins=rpm_bins,
                map_bins=map_bins,
                timing_func=front_timing,
                surface_id="spark_front",
            ),
            "spark_rear":
            create_synthetic_surface(
                rpm_bins=rpm_bins,
                map_bins=map_bins,
                timing_func=rear_timing,
                surface_id="spark_rear",
            ),
        }

    def test_finds_valleys_for_both_cylinders(self, cylinder_surfaces):
        """Multi-cylinder detection finds valleys for front and rear."""
        findings = detect_valleys_multi_cylinder(cylinder_surfaces)

        cylinders_found = {f.cylinder for f in findings}
        assert "front" in cylinders_found
        assert "rear" in cylinders_found

    def test_cylinder_labels_correct(self, cylinder_surfaces):
        """Each finding has correct cylinder label."""
        findings = detect_valleys_multi_cylinder(cylinder_surfaces)

        front_findings = [f for f in findings if f.cylinder == "front"]
        rear_findings = [f for f in findings if f.cylinder == "rear"]

        assert len(front_findings) >= 1
        assert len(rear_findings) >= 1


class TestValleySerialization:
    """Tests for SparkValleyFinding serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict includes all required fields."""
        finding = SparkValleyFinding(
            cylinder="front",
            rpm_center=4000,
            rpm_band=(3500, 4500),
            depth_deg=8.5,
            valley_min_deg=22.0,
            pre_valley_deg=30.0,
            post_valley_deg=28.0,
            map_band_used=85.0,
            confidence=0.85,
            evidence=["Test evidence 1", "Test evidence 2"],
        )

        d = finding.to_dict()

        assert d["cylinder"] == "front"
        assert d["rpm_center"] == 4000
        assert d["rpm_band"] == [3500, 4500]
        assert d["depth_deg"] == 8.5
        assert d["valley_min_deg"] == 22.0
        assert d["pre_valley_deg"] == 30.0
        assert d["post_valley_deg"] == 28.0
        assert d["map_band_used"] == 85.0
        assert d["confidence"] == 0.85
        assert d["evidence"] == ["Test evidence 1", "Test evidence 2"]

    def test_to_dict_is_json_serializable(self):
        """to_dict output can be serialized to JSON."""
        import json

        finding = SparkValleyFinding(
            cylinder="rear",
            rpm_center=3800,
            rpm_band=(3300, 4300),
            depth_deg=7.2,
            valley_min_deg=23.0,
            pre_valley_deg=29.5,
            post_valley_deg=27.0,
            map_band_used=90.0,
            confidence=0.78,
            evidence=["Evidence"],
        )

        d = finding.to_dict()
        json_str = json.dumps(d)

        assert isinstance(json_str, str)
        assert len(json_str) > 0


class TestEdgeCases:
    """Tests for edge cases in valley detection."""

    @pytest.fixture
    def sparse_surface(self):
        """Create surface with missing high-MAP data."""
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        map_bins = [40, 50, 60, 70, 80]

        def timing_func(rpm: float, map_kpa: float) -> float:
            return 28.0 - (rpm - 2000) * 0.001

        surface = create_synthetic_surface(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            timing_func=timing_func,
            surface_id="spark_sparse",
            min_hits=5,
        )

        # Set high-MAP cells to None (sparse data)
        for i in range(len(rpm_bins)):
            surface.values[i][-1] = None
            surface.hit_count[i][-1] = 0

        return surface

    def test_handles_sparse_high_map_data(self, sparse_surface):
        """Valley detection handles sparse high-MAP data gracefully."""
        # Should not crash
        findings = detect_spark_valley(sparse_surface, high_map_min_kpa=80.0)

        # May or may not find valley, but should not error
        assert isinstance(findings, list)

    @pytest.fixture
    def narrow_surface(self):
        """Create surface with minimal RPM bins."""
        rpm_bins = [3000, 4000, 5000]  # Only 3 bins
        map_bins = [80, 90]

        def timing_func(rpm: float, map_kpa: float) -> float:
            # Valley at 4000
            valley = 5 * (1 - abs(rpm - 4000) / 1000)
            return 28 - max(0, valley)

        return create_synthetic_surface(
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            timing_func=timing_func,
            surface_id="spark_narrow",
        )

    def test_handles_narrow_rpm_range(self, narrow_surface):
        """Valley detection handles narrow RPM ranges."""
        findings = detect_spark_valley(narrow_surface, high_map_min_kpa=80.0)

        # May not detect valley with so few bins, but should not error
        assert isinstance(findings, list)
