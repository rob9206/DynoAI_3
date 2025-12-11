"""
Tests for synthetic WinPEP8 curve generation.

Verifies that generated curves are physically plausible and
match the specified peak values within tolerance.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from synthetic.winpep8_from_peaks import (
    CurveParams,
    PeakInfo,
    generate_winpep8_like_run,
    write_run_csv,
)


class TestPeakInfo:
    """Tests for PeakInfo dataclass validation."""

    def test_valid_peak_info(self) -> None:
        """Test creating valid PeakInfo."""
        peak = PeakInfo(
            hp_peak=164.0,
            hp_peak_rpm=5800.0,
            tq_peak=160.0,
            tq_peak_rpm=3800.0,
        )
        assert peak.hp_peak == 164.0
        assert peak.hp_peak_rpm == 5800.0
        assert peak.tq_peak == 160.0
        assert peak.tq_peak_rpm == 3800.0

    def test_invalid_hp_peak(self) -> None:
        """Test that negative hp_peak raises ValueError."""
        with pytest.raises(ValueError, match="hp_peak must be positive"):
            PeakInfo(
                hp_peak=-10.0, hp_peak_rpm=5800.0, tq_peak=160.0, tq_peak_rpm=3800.0
            )

    def test_invalid_tq_peak(self) -> None:
        """Test that zero tq_peak raises ValueError."""
        with pytest.raises(ValueError, match="tq_peak must be positive"):
            PeakInfo(hp_peak=164.0, hp_peak_rpm=5800.0, tq_peak=0.0, tq_peak_rpm=3800.0)


class TestCurveGeneration:
    """Tests for generate_winpep8_like_run function."""

    @pytest.fixture
    def m8_peak(self) -> PeakInfo:
        """Typical M8 131″ peak values."""
        return PeakInfo(
            hp_peak=164.0,
            hp_peak_rpm=5800.0,
            tq_peak=160.0,
            tq_peak_rpm=3800.0,
        )

    @pytest.fixture
    def twin_cam_peak(self) -> PeakInfo:
        """Typical Twin Cam 110″ peak values."""
        return PeakInfo(
            hp_peak=110.0,
            hp_peak_rpm=5200.0,
            tq_peak=115.0,
            tq_peak_rpm=3200.0,
        )

    def test_dataframe_columns(self, m8_peak: PeakInfo) -> None:
        """Test that DataFrame has required WinPEP8 columns."""
        df = generate_winpep8_like_run(m8_peak)

        assert "Engine RPM" in df.columns
        assert "Torque" in df.columns
        assert "Horsepower" in df.columns

    def test_dataframe_shape(self, m8_peak: PeakInfo) -> None:
        """Test that DataFrame has expected number of rows."""
        df = generate_winpep8_like_run(m8_peak, num_points=400)
        assert len(df) == 400

        df = generate_winpep8_like_run(m8_peak, num_points=200)
        assert len(df) == 200

    def test_rpm_range(self, m8_peak: PeakInfo) -> None:
        """Test that RPM range matches requested values."""
        df = generate_winpep8_like_run(m8_peak, rpm_min=2000, rpm_max=6000)

        assert df["Engine RPM"].min() == pytest.approx(2000.0, rel=0.01)
        assert df["Engine RPM"].max() == pytest.approx(6000.0, rel=0.01)

    def test_max_hp_close_to_peak(self, m8_peak: PeakInfo) -> None:
        """Test that max HP is close to specified hp_peak."""
        df = generate_winpep8_like_run(m8_peak)

        max_hp = df["Horsepower"].max()
        # Allow 5% tolerance
        assert max_hp == pytest.approx(m8_peak.hp_peak, rel=0.05)

    def test_max_tq_close_to_peak(self, m8_peak: PeakInfo) -> None:
        """Test that max torque is close to specified tq_peak."""
        df = generate_winpep8_like_run(m8_peak)

        max_tq = df["Torque"].max()
        # Allow 5% tolerance
        assert max_tq == pytest.approx(m8_peak.tq_peak, rel=0.05)

    def test_hp_tq_relationship(self, m8_peak: PeakInfo) -> None:
        """Test that HP = TQ * RPM / 5252 holds within small epsilon."""
        df = generate_winpep8_like_run(m8_peak)

        calculated_hp = df["Torque"] * df["Engine RPM"] / 5252.0
        actual_hp = df["Horsepower"]

        # Should match within 1% for all points
        np.testing.assert_allclose(actual_hp, calculated_hp, rtol=0.01)

    def test_deterministic_output(self, m8_peak: PeakInfo) -> None:
        """Test that output is deterministic (no randomness)."""
        df1 = generate_winpep8_like_run(m8_peak)
        df2 = generate_winpep8_like_run(m8_peak)

        pd.testing.assert_frame_equal(df1, df2)

    def test_torque_peaks_before_hp(self, m8_peak: PeakInfo) -> None:
        """Test that torque peaks at lower RPM than horsepower."""
        df = generate_winpep8_like_run(m8_peak)

        tq_peak_idx = df["Torque"].idxmax()
        hp_peak_idx = df["Horsepower"].idxmax()

        tq_peak_rpm = df.loc[tq_peak_idx, "Engine RPM"]
        hp_peak_rpm = df.loc[hp_peak_idx, "Engine RPM"]

        # Torque should peak at lower RPM than HP (typical V-twin behavior)
        assert tq_peak_rpm <= hp_peak_rpm

    def test_reasonable_curve_shape(self, m8_peak: PeakInfo) -> None:
        """Test that curve has reasonable shape (no negative values, smooth)."""
        df = generate_winpep8_like_run(m8_peak)

        # No negative values
        assert (df["Torque"] > 0).all()
        assert (df["Horsepower"] > 0).all()

        # Values start low, rise, then potentially fall
        # First quartile should be lower than max
        first_quarter_hp = df.iloc[: len(df) // 4]["Horsepower"].mean()
        assert first_quarter_hp < df["Horsepower"].max()


class TestEngineFamily:
    """Tests for engine family-specific curve generation."""

    def test_m8_params(self) -> None:
        """Test M8 engine family produces reasonable curves."""
        peak = PeakInfo(
            hp_peak=150.0, hp_peak_rpm=5500.0, tq_peak=145.0, tq_peak_rpm=3500.0
        )
        df = generate_winpep8_like_run(peak, engine_family="M8")

        # M8 should have broad torque plateau
        mid_range = df[(df["Engine RPM"] > 3000) & (df["Engine RPM"] < 5000)]
        torque_variation = mid_range["Torque"].std() / mid_range["Torque"].mean()

        # Torque should be relatively flat in mid-range
        assert torque_variation < 0.15

    def test_twin_cam_params(self) -> None:
        """Test Twin Cam engine family produces reasonable curves."""
        peak = PeakInfo(
            hp_peak=110.0, hp_peak_rpm=5200.0, tq_peak=115.0, tq_peak_rpm=3200.0
        )
        df = generate_winpep8_like_run(peak, engine_family="Twin Cam")

        assert df["Horsepower"].max() == pytest.approx(peak.hp_peak, rel=0.05)

    def test_sportster_params(self) -> None:
        """Test Sportster engine family produces reasonable curves."""
        peak = PeakInfo(
            hp_peak=85.0, hp_peak_rpm=6000.0, tq_peak=75.0, tq_peak_rpm=4000.0
        )
        df = generate_winpep8_like_run(peak, engine_family="Sportster")

        assert df["Horsepower"].max() == pytest.approx(peak.hp_peak, rel=0.05)


class TestWriteRunCSV:
    """Tests for write_run_csv function."""

    def test_write_creates_file(self) -> None:
        """Test that write_run_csv creates file in correct location."""
        peak = PeakInfo(
            hp_peak=100.0, hp_peak_rpm=5500.0, tq_peak=100.0, tq_peak_rpm=3500.0
        )
        df = generate_winpep8_like_run(peak, num_points=50)

        # Use a test-specific run_id
        run_id = "test_synthetic/test_run"
        path = write_run_csv(run_id, df)

        assert Path(path).exists()
        assert path.endswith("run.csv")

        # Clean up
        Path(path).unlink()
        Path(path).parent.rmdir()
        Path(path).parent.parent.rmdir()

    def test_csv_readable(self) -> None:
        """Test that written CSV can be read back correctly."""
        peak = PeakInfo(
            hp_peak=100.0, hp_peak_rpm=5500.0, tq_peak=100.0, tq_peak_rpm=3500.0
        )
        df = generate_winpep8_like_run(peak, num_points=50)

        run_id = "test_synthetic/csv_read_test"
        path = write_run_csv(run_id, df)

        # Read back
        df_read = pd.read_csv(path)

        pd.testing.assert_frame_equal(df, df_read)

        # Clean up
        Path(path).unlink()
        Path(path).parent.rmdir()
        Path(path).parent.parent.rmdir()
