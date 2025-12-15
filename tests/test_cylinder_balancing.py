"""
Tests for cylinder_balancing module.

Tests cover:
- AFR aggregation for front and rear cylinders
- Imbalance detection and severity classification
- Correction factor calculation for different modes
- Safety clamping and limits
- CSV output generation
- End-to-end processing pipeline
"""

from pathlib import Path
from typing import Dict, List
from unittest.mock import mock_open, patch

import pytest

from dynoai.core.cylinder_balancing import (
    BalanceMode,
    CylinderData,
    ImbalanceCell,
    _afr_error_to_ve_correction,
    _clamp_correction,
    aggregate_cylinder_afr,
    analyze_imbalance,
    calculate_correction_factors,
    generate_balance_report,
    process_cylinder_balancing,
    write_correction_csv,
)
from dynoai.constants import KPA_BINS, RPM_BINS

# ============================================================================
# Test Data Helpers
# ============================================================================


def create_mock_records(
    num_records: int = 100,
    front_afr_bias: float = 0.0,  # Positive = front leaner than rear
    rear_afr_bias: float = 0.0,  # Positive = rear leaner than front
    base_afr: float = 13.8,
) -> List[Dict[str, float]]:
    """Create mock dyno records with controllable AFR bias."""
    records = []

    for i in range(num_records):
        # Cycle through RPM/KPA ranges
        rpm = 2000 + (i % 5) * 500  # 2000, 2500, 3000, 3500, 4000
        kpa = 50 + (i % 3) * 15  # 50, 65, 80

        # Front AFR with bias
        afr_f = base_afr + front_afr_bias + (i % 10) * 0.05  # Add some variation

        # Rear AFR with bias (and typically hotter = leaner)
        afr_r = base_afr + rear_afr_bias + (i % 10) * 0.05

        records.append(
            {
                "rpm": rpm,
                "kpa": kpa,
                "afr_meas_f": afr_f,
                "afr_meas_r": afr_r,
                "afr_cmd_f": base_afr,
                "afr_cmd_r": base_afr,
                "tps": 50.0,
            }
        )

    return records


def create_balanced_records(num_records: int = 100) -> List[Dict[str, Optional[float]]]:
    """Create records with perfectly balanced AFR."""
    return create_mock_records(num_records, front_afr_bias=0.0, rear_afr_bias=0.0)


def create_imbalanced_records(
    num_records: int = 100,
) -> List[Dict[str, Optional[float]]]:
    """Create records with rear running 0.8 AFR leaner than front."""
    return create_mock_records(num_records, front_afr_bias=0.0, rear_afr_bias=0.8)


# ============================================================================
# AFR Aggregation Tests
# ============================================================================


class TestAFRAggregation:
    def test_aggregate_front_cylinder(self):
        """Test aggregation of front cylinder AFR data."""
        records = create_balanced_records(50)

        front_data = aggregate_cylinder_afr(
            records, "afr_meas_f", "afr_cmd_f", min_samples=3
        )

        assert isinstance(front_data, CylinderData)
        assert len(front_data.afr_grid) == len(RPM_BINS)
        assert len(front_data.afr_grid[0]) == len(KPA_BINS)
        assert len(front_data.sample_counts) == len(RPM_BINS)

        # Check that some cells have data
        total_samples = sum(sum(row) for row in front_data.sample_counts)
        assert total_samples > 0

    def test_aggregate_rear_cylinder(self):
        """Test aggregation of rear cylinder AFR data."""
        records = create_balanced_records(50)

        rear_data = aggregate_cylinder_afr(
            records, "afr_meas_r", "afr_cmd_r", min_samples=3
        )

        assert isinstance(rear_data, CylinderData)
        total_samples = sum(sum(row) for row in rear_data.sample_counts)
        assert total_samples > 0

    def test_insufficient_samples_filtered(self):
        """Test that cells with too few samples are zeroed out."""
        # Only 2 records, but min_samples=3
        records = create_balanced_records(2)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)

        # Most cells should be zero (insufficient data)
        zero_cells = sum(1 for row in front_data.afr_grid for val in row if val == 0.0)
        assert (
            zero_cells > len(RPM_BINS) * len(KPA_BINS) * 0.8
        )  # At least 80% should be zero

    def test_bad_afr_readings_filtered(self):
        """Test that obviously bad AFR readings are filtered out."""
        records = create_balanced_records(50)

        # Inject some bad readings
        records[0]["afr_meas_f"] = 5.0  # Too low
        records[1]["afr_meas_f"] = 25.0  # Too high
        records[2]["afr_meas_f"] = None  # Missing

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)

        # Should still aggregate the good data
        total_samples = sum(sum(row) for row in front_data.sample_counts)
        assert total_samples > 0  # Good data was aggregated
        assert total_samples < 50  # Bad data was filtered

    def test_afr_cmd_grid_calculated(self):
        """Test that commanded AFR grid is calculated correctly."""
        records = create_balanced_records(50)

        front_data = aggregate_cylinder_afr(
            records, "afr_meas_f", "afr_cmd_f", min_samples=3
        )

        # Check that commanded AFR is present in some cells
        non_zero_cmd = sum(
            1 for row in front_data.afr_cmd_grid for val in row if val > 0.0
        )
        assert non_zero_cmd > 0


# ============================================================================
# Imbalance Analysis Tests
# ============================================================================


class TestImbalanceAnalysis:
    def test_analyze_balanced_cylinders(self):
        """Test that balanced cylinders show no imbalance."""
        records = create_balanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)

        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        assert analysis.cells_analyzed > 0
        # With perfectly balanced data, should have few or no imbalanced cells
        assert (
            analysis.cells_imbalanced < analysis.cells_analyzed * 0.2
        )  # Less than 20%
        assert analysis.max_delta < 0.6  # Small natural variation

    def test_analyze_imbalanced_cylinders(self):
        """Test that imbalanced cylinders are detected."""
        records = create_imbalanced_records(100)  # Rear 0.8 AFR leaner

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)

        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        assert analysis.cells_imbalanced > 0
        assert analysis.max_delta >= 0.7  # Should detect the 0.8 AFR bias
        assert len(analysis.imbalanced_cells) > 0

    def test_imbalance_cell_severity(self):
        """Test severity classification of imbalance cells."""
        # Create high severity imbalance
        cell_high = ImbalanceCell(
            rpm_idx=0,
            kpa_idx=0,
            rpm=2000,
            kpa=50,
            front_afr=13.0,
            rear_afr=14.2,
            delta=1.2,
            front_samples=10,
            rear_samples=10,
        )
        assert cell_high.severity() == "high"

        # Medium severity
        cell_medium = ImbalanceCell(
            rpm_idx=0,
            kpa_idx=0,
            rpm=2000,
            kpa=50,
            front_afr=13.0,
            rear_afr=13.8,
            delta=0.8,
            front_samples=10,
            rear_samples=10,
        )
        assert cell_medium.severity() == "medium"

        # Low severity
        cell_low = ImbalanceCell(
            rpm_idx=0,
            kpa_idx=0,
            rpm=2000,
            kpa=50,
            front_afr=13.0,
            rear_afr=13.5,
            delta=0.5,
            front_samples=10,
            rear_samples=10,
        )
        assert cell_low.severity() == "low"

    def test_analysis_summary(self):
        """Test that analysis summary statistics are correct."""
        records = create_imbalanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)

        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)
        summary = analysis.summary()

        assert "cells_analyzed" in summary
        assert "cells_imbalanced" in summary
        assert "imbalance_percentage" in summary
        assert "max_afr_delta" in summary
        assert "severity_breakdown" in summary
        assert summary["cells_analyzed"] > 0


# ============================================================================
# Correction Calculation Tests
# ============================================================================


class TestCorrectionCalculation:
    def test_afr_error_to_ve_correction(self):
        """Test AFR error to VE correction conversion."""
        # Lean (+1.0 AFR) needs more fuel = +VE
        correction = _afr_error_to_ve_correction(1.0)
        assert correction == pytest.approx(0.07, abs=0.01)

        # Rich (-1.0 AFR) needs less fuel = -VE
        correction = _afr_error_to_ve_correction(-1.0)
        assert correction == pytest.approx(-0.07, abs=0.01)

        # No error = no correction
        correction = _afr_error_to_ve_correction(0.0)
        assert correction == 0.0

    def test_clamp_correction_within_limits(self):
        """Test that corrections within limits pass through."""
        max_pct = 3.0

        # Within limit
        assert _clamp_correction(0.02, max_pct) == pytest.approx(0.02)  # 2%
        assert _clamp_correction(-0.025, max_pct) == pytest.approx(-0.025)  # -2.5%

    def test_clamp_correction_exceeds_max(self):
        """Test that excessive corrections are clamped."""
        max_pct = 3.0

        # Exceeds max_pct
        assert _clamp_correction(0.05, max_pct) == pytest.approx(0.03)  # Clamped to 3%
        assert _clamp_correction(-0.06, max_pct) == pytest.approx(
            -0.03
        )  # Clamped to -3%

    def test_clamp_correction_absolute_maximum(self):
        """Test that absolute maximum is enforced even if max_pct is higher."""
        max_pct = 10.0  # Allow 10%, but absolute max is 5%

        assert _clamp_correction(0.08, max_pct) == pytest.approx(0.05)  # Absolute max
        assert _clamp_correction(-0.12, max_pct) == pytest.approx(-0.05)  # Absolute max

    def test_calculate_corrections_equalize_mode(self):
        """Test correction calculation in equalize mode."""
        records = create_imbalanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)
        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        front_factors, rear_factors = calculate_correction_factors(
            analysis, BalanceMode.EQUALIZE, max_correction_pct=3.0
        )

        assert len(front_factors) == len(RPM_BINS)
        assert len(rear_factors) == len(RPM_BINS)

        # Both cylinders should get corrections in equalize mode
        front_corrections = sum(1 for row in front_factors for val in row if val != 0.0)
        rear_corrections = sum(1 for row in rear_factors for val in row if val != 0.0)

        assert front_corrections > 0 or rear_corrections > 0

    def test_calculate_corrections_match_front_mode(self):
        """Test correction calculation in match_front mode."""
        records = create_imbalanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)
        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        front_factors, rear_factors = calculate_correction_factors(
            analysis, BalanceMode.MATCH_FRONT, max_correction_pct=3.0
        )

        # In match_front mode, only rear should get corrections
        front_corrections = sum(1 for row in front_factors for val in row if val != 0.0)
        rear_corrections = sum(1 for row in rear_factors for val in row if val != 0.0)

        assert front_corrections == 0
        assert rear_corrections > 0

    def test_calculate_corrections_match_rear_mode(self):
        """Test correction calculation in match_rear mode."""
        records = create_imbalanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)
        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        front_factors, rear_factors = calculate_correction_factors(
            analysis, BalanceMode.MATCH_REAR, max_correction_pct=3.0
        )

        # In match_rear mode, only front should get corrections
        front_corrections = sum(1 for row in front_factors for val in row if val != 0.0)
        rear_corrections = sum(1 for row in rear_factors for val in row if val != 0.0)

        assert front_corrections > 0
        assert rear_corrections == 0


# ============================================================================
# Output Generation Tests
# ============================================================================


class TestOutputGeneration:
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_write_correction_csv(self, mock_mkdir, mock_file_open):
        """Test writing correction factors to CSV."""
        # Create full-size grid matching RPM_BINS x KPA_BINS
        factors = [[0.0 for _ in KPA_BINS] for _ in RPM_BINS]

        # Set a few test values
        factors[0][0] = 0.03  # +3% at first cell
        factors[1][1] = -0.02  # -2% at second row, second col
        factors[2][2] = -0.01  # -1%

        output_path = Path("test_output/Front_Balance_Factor.csv")
        write_correction_csv(factors, output_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file_open.assert_called_once()

        # Verify write calls contain correct data
        handle = mock_file_open()
        written_content = "".join(
            [call.args[0] for call in handle.write.call_args_list]
        )

        # Should contain header
        assert "RPM" in written_content

        # Should contain multipliers (1 + factor)
        assert "1.03" in written_content or "1.0300" in written_content  # 0.03 → 1.03
        assert "0.98" in written_content or "0.9800" in written_content  # -0.02 → 0.98

    def test_generate_balance_report(self):
        """Test balance report generation."""
        records = create_imbalanced_records(100)

        front_data = aggregate_cylinder_afr(records, "afr_meas_f", min_samples=3)
        rear_data = aggregate_cylinder_afr(records, "afr_meas_r", min_samples=3)
        analysis = analyze_imbalance(front_data, rear_data, afr_threshold=0.5)

        front_factors, rear_factors = calculate_correction_factors(
            analysis, BalanceMode.EQUALIZE, max_correction_pct=3.0
        )

        report = generate_balance_report(
            analysis,
            front_factors,
            rear_factors,
            BalanceMode.EQUALIZE,
            "test_input.csv",
        )

        assert "timestamp_utc" in report
        assert "input_file" in report
        assert report["input_file"] == "test_input.csv"
        assert "balance_mode" in report
        assert report["balance_mode"] == "equalize"
        assert "analysis" in report
        assert "corrections" in report
        assert "imbalanced_zones" in report


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


class TestProcessCylinderBalancing:
    @patch("cylinder_balancing.write_correction_csv")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_process_balanced_cylinders(
        self, mock_mkdir, mock_file_open, mock_write_csv
    ):
        """Test full pipeline with balanced cylinders."""
        records = create_balanced_records(100)

        result = process_cylinder_balancing(
            records=records,
            output_dir="test_output",
            mode="equalize",
            max_correction_pct=3.0,
        )

        assert "cells_analyzed" in result
        assert "cells_imbalanced" in result
        assert "max_afr_delta" in result
        assert "mode_used" in result
        assert result["mode_used"] == "equalize"

        # With balanced cylinders, should have minimal corrections
        assert result["cells_imbalanced"] < result["cells_analyzed"] * 0.3

    @patch("cylinder_balancing.write_correction_csv")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_process_imbalanced_cylinders(
        self, mock_mkdir, mock_file_open, mock_write_csv
    ):
        """Test full pipeline with imbalanced cylinders."""
        records = create_imbalanced_records(100)

        result = process_cylinder_balancing(
            records=records,
            output_dir="test_output",
            mode="equalize",
            max_correction_pct=3.0,
        )

        assert result["cells_imbalanced"] > 0
        assert result["max_afr_delta"] > 0.5
        assert (
            result["front_corrections_applied"] + result["rear_corrections_applied"] > 0
        )

    @patch("cylinder_balancing.write_correction_csv")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_process_invalid_mode_fallback(
        self, mock_mkdir, mock_file_open, mock_write_csv
    ):
        """Test that invalid mode falls back to equalize."""
        records = create_balanced_records(100)

        result = process_cylinder_balancing(
            records=records,
            output_dir="test_output",
            mode="invalid_mode",  # Invalid mode
            max_correction_pct=3.0,
        )

        # Should fallback to equalize
        assert result["mode_used"] == "equalize"

    @patch("cylinder_balancing.write_correction_csv")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_process_creates_output_files(
        self, mock_mkdir, mock_file_open, mock_write_csv
    ):
        """Test that all expected output files are created."""
        records = create_imbalanced_records(100)

        result = process_cylinder_balancing(
            records=records, output_dir="test_output", mode="equalize"
        )

        assert "output_files" in result
        assert "front_factors" in result["output_files"]
        assert "rear_factors" in result["output_files"]
        assert "report" in result["output_files"]

        # CSV writer should be called twice (front + rear)
        assert mock_write_csv.call_count == 2

    @patch("cylinder_balancing.write_correction_csv")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_process_respects_max_correction(
        self, mock_mkdir, mock_file_open, mock_write_csv
    ):
        """Test that max_correction_pct is respected."""
        # Create severe imbalance
        records = create_mock_records(100, front_afr_bias=0.0, rear_afr_bias=3.0)

        _ = process_cylinder_balancing(
            records=records,
            output_dir="test_output",
            mode="equalize",
            max_correction_pct=2.0,  # Strict limit
        )

        # Verify write_correction_csv was called with clamped values
        for call in mock_write_csv.call_args_list:
            factors = call.args[0]
            max_factor = max(abs(val) for row in factors for val in row)
            # Should be clamped to 2% max (0.02)
            assert max_factor <= 0.021  # Small tolerance for floating point
