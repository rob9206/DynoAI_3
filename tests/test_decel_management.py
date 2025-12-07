"""
Unit tests for DynoAI Decel Fuel Management module.

Tests cover:
- Decel event detection from TPS rate of change
- AFR analysis during decel events
- Enrichment calculation with severity presets
- VE overlay generation
- Report generation
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from decel_management import (
    BASE_ENRICHMENT,
    DECEL_KPA_MAX,
    DEFAULT_DECEL_CONFIG,
    MAX_ENRICHMENT_PCT,
    MIN_ENRICHMENT_PCT,
    DecelAnalysisReport,
    DecelEvent,
    DecelSeverity,
    analyze_decel_afr,
    calculate_decel_enrichment,
    detect_decel_events,
    generate_decel_overlay,
    generate_decel_report,
    process_decel_management,
    write_decel_analysis_report,
    write_decel_overlay_csv,
)
from dynoai.constants import KPA_BINS, RPM_BINS

# ============================================================================
# Test Fixtures
# ============================================================================


def create_test_records(
    rpm_values: List[float],
    tps_values: List[float],
    afr_values: Optional[List[float]] = None,
) -> List[Dict[str, Optional[float]]]:
    """Create test records with given RPM and TPS profiles."""
    records = []
    for i in range(len(rpm_values)):
        record: Dict[str, Optional[float]] = {
            "rpm": rpm_values[i],
            "tps": tps_values[i],
        }
        if afr_values and i < len(afr_values):
            record["afr_meas_f"] = afr_values[i]
            record["afr_meas_r"] = afr_values[i]
        records.append(record)
    return records


def create_decel_scenario(
    start_tps: float = 50.0,
    end_tps: float = 2.0,
    rpm: float = 3000.0,
    duration_samples: int = 50,
    steady_before: int = 20,
    steady_after: int = 20,
) -> List[Dict[str, Optional[float]]]:
    """Create a realistic decel event scenario."""
    records = []

    # Steady state before decel
    for _ in range(steady_before):
        records.append({"rpm": rpm, "tps": start_tps})

    # Decel event (linear TPS drop)
    tps_step = (start_tps - end_tps) / duration_samples
    for i in range(duration_samples):
        tps = start_tps - (tps_step * i)
        records.append({"rpm": rpm - (i * 10), "tps": tps})  # RPM drops slightly

    # Steady state after decel
    for _ in range(steady_after):
        records.append({"rpm": rpm - 500, "tps": end_tps})

    return records


# ============================================================================
# Tests: Decel Event Detection
# ============================================================================


class TestDecelEventDetection:
    """Tests for detect_decel_events function."""

    def test_detect_single_decel_event(self):
        """Single throttle closure detected as decel event."""
        records = create_decel_scenario(
            start_tps=50.0,
            end_tps=2.0,
            rpm=3000.0,
            duration_samples=50,
        )

        events = detect_decel_events(records, sample_rate_ms=10.0)

        assert len(events) >= 1, "Should detect at least one decel event"
        event = events[0]
        assert event.end_tps < 7.0, "Event should end at low TPS"
        assert event.tps_rate < 0, "TPS rate should be negative (closing)"

    def test_no_event_steady_throttle(self):
        """No event detected with steady throttle."""
        # Steady throttle at 50%
        records = [{"rpm": 3000.0, "tps": 50.0} for _ in range(100)]

        events = detect_decel_events(records, sample_rate_ms=10.0)

        assert len(events) == 0, "Should not detect events with steady throttle"

    def test_no_event_throttle_opening(self):
        """No event detected when throttle is opening."""
        # Throttle opening from 10% to 80%
        records = []
        for i in range(100):
            tps = 10.0 + (i * 0.7)  # Linear opening
            records.append({"rpm": 3000.0 + (i * 10), "tps": tps})

        events = detect_decel_events(records, sample_rate_ms=10.0)

        assert len(events) == 0, "Should not detect events when throttle opens"

    def test_event_duration_filter_too_short(self):
        """Events too short are filtered out."""
        # Very rapid throttle snap (< 200ms)
        records = create_decel_scenario(
            start_tps=50.0,
            end_tps=2.0,
            rpm=3000.0,
            duration_samples=10,  # Only 100ms at 10ms sample rate
        )

        events = detect_decel_events(records, sample_rate_ms=10.0)

        # With 10 samples at 10ms = 100ms, below 200ms threshold
        assert len(events) == 0, "Events shorter than 200ms should be filtered"

    def test_event_rpm_range_filter(self):
        """Events outside RPM range are filtered."""
        # Decel at very low RPM (below 1500)
        records = create_decel_scenario(
            start_tps=50.0,
            end_tps=2.0,
            rpm=1200.0,  # Below minimum
            duration_samples=50,
        )

        events = detect_decel_events(records, sample_rate_ms=10.0)

        assert len(events) == 0, "Events below 1500 RPM should be filtered"

    def test_multiple_decel_events(self):
        """Multiple decel events in sequence are detected."""
        # Two decel events with steady state between
        records = []
        records.extend(create_decel_scenario(rpm=3000.0))
        records.extend([{"rpm": 2500.0, "tps": 30.0} for _ in range(50)])  # Steady
        records.extend(create_decel_scenario(rpm=4000.0))

        events = detect_decel_events(records, sample_rate_ms=10.0)

        assert len(events) >= 2, "Should detect multiple decel events"


# ============================================================================
# Tests: AFR Analysis
# ============================================================================


class TestAFRAnalysis:
    """Tests for analyze_decel_afr function."""

    def test_afr_analysis_lean_spike(self):
        """AFR excursion detected and scored correctly."""
        # Create decel with lean AFR spike
        records = create_decel_scenario()

        # Add AFR values - lean spike during decel
        for i, r in enumerate(records):
            if i < 20:
                r["afr_meas_f"] = 13.5  # Normal before
            elif i < 70:
                r["afr_meas_f"] = 16.5  # Lean during decel
            else:
                r["afr_meas_f"] = 14.0  # Normal after

        events = detect_decel_events(records, sample_rate_ms=10.0)
        assert len(events) >= 1

        events = analyze_decel_afr(records, events, "afr_meas_f")

        event = events[0]
        assert event.afr_max is not None, "Should detect AFR max"
        assert event.afr_max >= 16.0, "Should detect lean spike"
        assert event.pop_likelihood > 0.5, "High pop likelihood for lean spike"

    def test_afr_analysis_rich_mixture(self):
        """Rich AFR during decel results in low pop likelihood."""
        records = create_decel_scenario()

        # Add rich AFR values during decel
        for r in records:
            r["afr_meas_f"] = 12.5  # Rich throughout

        events = detect_decel_events(records, sample_rate_ms=10.0)
        if events:  # May or may not detect depending on scenario
            events = analyze_decel_afr(records, events, "afr_meas_f")

            for event in events:
                assert event.pop_likelihood < 0.1, (
                    "Rich mixture should have low pop likelihood"
                )

    def test_afr_analysis_missing_data(self):
        """Missing AFR data handled gracefully."""
        records = create_decel_scenario()
        # No AFR data added

        events = detect_decel_events(records, sample_rate_ms=10.0)
        events = analyze_decel_afr(records, events, "afr_meas_f")

        for event in events:
            assert event.afr_min is None, "AFR min should be None with missing data"
            assert event.pop_likelihood == 0.0, (
                "Pop likelihood should be 0 with missing data"
            )


# ============================================================================
# Tests: Enrichment Calculation
# ============================================================================


class TestEnrichmentCalculation:
    """Tests for calculate_decel_enrichment function."""

    def test_base_enrichment_applied(self):
        """Base enrichment table applied to zones."""
        events: List[DecelEvent] = []  # No events

        enrichment = calculate_decel_enrichment(events, DecelSeverity.MEDIUM)

        # Check all base zones are present
        assert len(enrichment) == len(BASE_ENRICHMENT)

        # Check enrichment values are positive
        for zone, value in enrichment.items():
            assert value > 0, f"Enrichment should be positive for zone {zone}"

    def test_severity_low_scaling(self):
        """LOW severity scales enrichment down."""
        events: List[DecelEvent] = []

        medium = calculate_decel_enrichment(events, DecelSeverity.MEDIUM)
        low = calculate_decel_enrichment(events, DecelSeverity.LOW)

        # Low should be <= medium (accounting for minimum floor)
        # Zones with higher base enrichment should show clear difference
        high_base_zones = [z for z in medium if medium[z] > 0.10]
        for zone in high_base_zones:
            assert low[zone] <= medium[zone], f"LOW should be <= MEDIUM for {zone}"

        # At least some zones should show actual difference
        different_zones = [z for z in medium if low[z] < medium[z]]
        assert len(different_zones) > 0, (
            "Some zones should show LOW < MEDIUM difference"
        )

    def test_severity_high_scaling(self):
        """HIGH severity scales enrichment up."""
        events: List[DecelEvent] = []

        medium = calculate_decel_enrichment(events, DecelSeverity.MEDIUM)
        high = calculate_decel_enrichment(events, DecelSeverity.HIGH)

        # High should be ~130% of medium
        for zone in medium:
            assert high[zone] > medium[zone], (
                f"HIGH should be greater than MEDIUM for {zone}"
            )

    def test_enrichment_clamping_max(self):
        """Enrichment capped at maximum."""
        # Create event with very high pop likelihood
        event = DecelEvent(
            start_idx=0,
            end_idx=50,
            start_rpm=3000.0,
            end_rpm=2500.0,
            start_tps=50.0,
            end_tps=1.0,
            tps_rate=-50.0,
            duration_ms=500,
            pop_likelihood=1.0,  # Maximum
        )

        enrichment = calculate_decel_enrichment([event] * 10, DecelSeverity.HIGH)

        for zone, value in enrichment.items():
            assert value <= MAX_ENRICHMENT_PCT, (
                f"Enrichment should not exceed {MAX_ENRICHMENT_PCT}"
            )

    def test_enrichment_minimum_floor(self):
        """Enrichment has minimum floor in decel zone."""
        events: List[DecelEvent] = []

        enrichment = calculate_decel_enrichment(events, DecelSeverity.LOW)

        for zone, value in enrichment.items():
            assert value >= MIN_ENRICHMENT_PCT, (
                f"Enrichment should be at least {MIN_ENRICHMENT_PCT}"
            )


# ============================================================================
# Tests: VE Overlay Generation
# ============================================================================


class TestOverlayGeneration:
    """Tests for generate_decel_overlay function."""

    def test_overlay_dimensions(self):
        """Overlay has correct dimensions."""
        enrichment = calculate_decel_enrichment([], DecelSeverity.MEDIUM)
        overlay = generate_decel_overlay(enrichment)

        assert len(overlay) == len(RPM_BINS), "Overlay should have correct row count"
        for row in overlay:
            assert len(row) == len(KPA_BINS), "Overlay should have correct column count"

    def test_overlay_low_kpa_only(self):
        """Enrichment only applied to low-MAP cells."""
        enrichment = calculate_decel_enrichment([], DecelSeverity.MEDIUM)
        overlay = generate_decel_overlay(enrichment)

        for i, rpm in enumerate(RPM_BINS):
            for j, kpa in enumerate(KPA_BINS):
                if kpa > DECEL_KPA_MAX:
                    assert overlay[i][j] == 0.0, (
                        f"High kPa cell ({rpm}, {kpa}) should have 0 enrichment"
                    )

    def test_overlay_decel_zone_has_values(self):
        """Decel zone cells have enrichment values."""
        enrichment = calculate_decel_enrichment([], DecelSeverity.MEDIUM)
        overlay = generate_decel_overlay(enrichment)

        has_enrichment = False
        for i, rpm in enumerate(RPM_BINS):
            for j, kpa in enumerate(KPA_BINS):
                if kpa <= DECEL_KPA_MAX and overlay[i][j] > 0:
                    has_enrichment = True
                    break

        assert has_enrichment, "Decel zone should have enrichment values"


# ============================================================================
# Tests: Output Files
# ============================================================================


class TestOutputFiles:
    """Tests for output file generation."""

    def test_write_overlay_csv(self):
        """Overlay CSV written correctly."""
        enrichment = calculate_decel_enrichment([], DecelSeverity.MEDIUM)
        overlay = generate_decel_overlay(enrichment)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_overlay.csv"
            result_path = write_decel_overlay_csv(overlay, output_path)

            assert Path(result_path).exists(), "Output file should exist"

            # Read and verify
            with open(result_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == len(RPM_BINS) + 1, "CSV should have header + data rows"
            assert "RPM" in lines[0], "Header should contain RPM"

    def test_write_analysis_report(self):
        """Analysis report JSON written correctly."""
        report = DecelAnalysisReport(
            input_file="test.csv",
            events_detected=5,
            avg_pop_likelihood=0.42,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.json"
            result_path = write_decel_analysis_report(report, output_path)

            assert Path(result_path).exists(), "Output file should exist"

            # Read and verify JSON
            with open(result_path, "r") as f:
                data = json.load(f)

            assert data["version"] == "1.0"
            assert data["input_file"] == "test.csv"
            assert data["summary"]["events_detected"] == 5


# ============================================================================
# Tests: Full Pipeline
# ============================================================================


class TestFullPipeline:
    """Tests for complete decel management pipeline."""

    def test_process_decel_management_with_events(self):
        """Full pipeline processes log with decel events."""
        records = create_decel_scenario(
            start_tps=60.0,
            end_tps=1.5,
            rpm=3500.0,
            duration_samples=60,
        )

        # Add AFR data with lean spike
        for i, r in enumerate(records):
            if 20 <= i <= 80:
                r["afr_meas_f"] = 16.0
            else:
                r["afr_meas_f"] = 13.5

        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_decel_management(
                records,
                output_dir=tmpdir,
                severity="medium",
                sample_rate_ms=10.0,
                input_file="test_log.csv",
            )

            assert "events_detected" in result
            assert "output_files" in result
            assert Path(result["output_files"]["overlay"]).exists()
            assert Path(result["output_files"]["report"]).exists()

    def test_process_decel_management_no_events(self):
        """Pipeline handles log with no decel events."""
        # Steady state log - no decel
        records = [{"rpm": 3000.0, "tps": 50.0, "afr_meas_f": 13.5} for _ in range(100)]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_decel_management(
                records,
                output_dir=tmpdir,
                severity="medium",
            )

            assert result["events_detected"] == 0
            # Should still generate overlay with base enrichment
            assert Path(result["output_files"]["overlay"]).exists()


# ============================================================================
# Tests: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_records(self):
        """Empty records handled gracefully."""
        events = detect_decel_events([], sample_rate_ms=10.0)
        assert events == []

    def test_missing_tps_data(self):
        """Records with missing TPS handled."""
        records = [{"rpm": 3000.0} for _ in range(50)]  # No TPS

        events = detect_decel_events(records, sample_rate_ms=10.0)
        assert events == []  # Should not crash

    def test_invalid_severity_string(self):
        """Invalid severity string defaults to medium."""
        records = create_decel_scenario()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not crash with invalid severity
            result = process_decel_management(
                records,
                output_dir=tmpdir,
                severity="invalid_severity",
            )

            assert result["severity_used"] == "medium"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
