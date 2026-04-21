"""
Tests for :mod:`api.services.jetdrive.wideband_rescale`.

These tests lock the LC-1/LC-2 voltage-to-AFR math server-side so it
cannot silently drift back into the frontend (which is forbidden by
``.cursor/rules/no-physics-in-frontend.mdc``).
"""

from __future__ import annotations

import math

import pytest

from api.services.jetdrive.wideband_rescale import (
    DEFAULT_LC2_PETROL_CALIBRATION,
    WidebandCalibration,
    canonicalize_wideband_sample,
    get_active_calibration,
    match_wideband_channel,
    set_active_calibration,
)


class TestCalibrationMath:
    """Pin the Innovate LC-2 linear transfer function."""

    def test_default_endpoints(self):
        cal = DEFAULT_LC2_PETROL_CALIBRATION
        assert cal.v_min == 0.0
        assert cal.v_max == 5.0
        assert cal.afr_min == 7.35
        assert cal.afr_max == 22.39

    def test_slope_matches_prior_frontend_constant(self):
        # Prior frontend math was `value * 3.008 + 7.35`. Keep parity.
        cal = DEFAULT_LC2_PETROL_CALIBRATION
        expected_slope = (22.39 - 7.35) / (5.0 - 0.0)
        assert math.isclose(cal.slope, expected_slope, rel_tol=1e-9)
        # Documented prior constant was 3.008 (rounded). Must be within rounding.
        assert math.isclose(cal.slope, 3.008, abs_tol=1e-3)

    def test_intercept_equals_v_min_afr_endpoint(self):
        cal = DEFAULT_LC2_PETROL_CALIBRATION
        assert math.isclose(cal.intercept, 7.35, abs_tol=1e-9)

    @pytest.mark.parametrize(
        "volts, expected_afr",
        [
            (0.0, 7.35),
            (2.5, 14.87),
            (5.0, 22.39),
            (1.0, 10.358),
        ],
    )
    def test_volts_to_afr_samples(self, volts: float, expected_afr: float):
        afr = DEFAULT_LC2_PETROL_CALIBRATION.volts_to_afr(volts)
        assert math.isclose(afr, expected_afr, abs_tol=1e-3)


class TestChannelMatching:
    """Matching is conservative by design."""

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("LC2 Volts Petrol AFR1", "AFR Front"),
            ("LC2 Volts Petrol AFR2", "AFR Rear"),
            ("lc2 volts petrol afr1", "AFR Front"),
            ("Volts Petrol AFR Front", "AFR Front"),
            ("Volts Petrol AFR Rear", "AFR Rear"),
            ("Volts Petrol AFR", "AFR"),
        ],
    )
    def test_matches_lc_voltage_names(self, name: str, expected: str):
        assert match_wideband_channel(name) == expected

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "Engine RPM",
            "AFR Meas",
            "MAP kPa",
            "Torque",
            "Air/Fuel Ratio",
            "Volts AFR",
            "Petrol AFR",
            "LC2 Volts",
            "Lambda",
        ],
    )
    def test_does_not_match_non_voltage_channels(self, name: str):
        assert match_wideband_channel(name) is None

    def test_handles_non_string_inputs(self):
        assert match_wideband_channel(None) is None  # type: ignore[arg-type]
        assert match_wideband_channel(123) is None  # type: ignore[arg-type]


class TestCanonicalization:
    """End-to-end: name + raw volts -> canonical AFR sample."""

    def test_lc2_front_voltage_becomes_afr_front(self):
        result = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 2.5)
        assert result is not None
        assert result.canonical_name == "AFR Front"
        assert math.isclose(result.afr, 14.87, abs_tol=1e-3)
        assert result.units == "AFR"
        assert result.category == "afr"

    def test_lc2_rear_voltage_becomes_afr_rear(self):
        result = canonicalize_wideband_sample("LC2 Volts Petrol AFR2", 5.0)
        assert result is not None
        assert result.canonical_name == "AFR Rear"
        assert math.isclose(result.afr, 22.39, abs_tol=1e-3)

    def test_non_matching_channel_returns_none(self):
        assert canonicalize_wideband_sample("Engine RPM", 2500.0) is None
        assert canonicalize_wideband_sample("Torque", 42.0) is None

    def test_out_of_range_voltage_returns_none(self):
        # Values well outside the 0-5V rail (plus 10% pad) are rejected
        # so an already-AFR reading cannot be mistakenly rescaled again.
        assert canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 14.7) is None
        assert canonicalize_wideband_sample("LC2 Volts Petrol AFR1", -1.0) is None

    def test_voltage_just_outside_rail_is_allowed(self):
        # Brief transients at the sensor rails (within 10% pad) are OK.
        result = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 5.25)
        assert result is not None

    def test_non_numeric_value_returns_none(self):
        result = canonicalize_wideband_sample(
            "LC2 Volts Petrol AFR1",
            "not a number",  # type: ignore[arg-type]
        )
        assert result is None


class TestCalibrationOverride:
    """Custom Innovate calibrations must be respected end-to-end."""

    def test_custom_calibration_changes_output(self):
        original = get_active_calibration()
        custom = WidebandCalibration(
            name="custom",
            v_min=0.0,
            v_max=5.0,
            afr_min=10.0,
            afr_max=20.0,
        )
        try:
            set_active_calibration(custom)
            result = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 2.5)
            assert result is not None
            assert math.isclose(result.afr, 15.0, abs_tol=1e-6)
        finally:
            set_active_calibration(original)

    def test_calibration_argument_overrides_module_default(self):
        custom = WidebandCalibration(
            name="e85",
            v_min=0.0,
            v_max=5.0,
            afr_min=4.95,
            afr_max=15.08,
        )
        result = canonicalize_wideband_sample(
            "LC2 Volts Petrol AFR1", 2.5, calibration=custom
        )
        assert result is not None
        assert math.isclose(result.afr, (4.95 + 15.08) / 2, abs_tol=1e-6)


class TestRegressionScenarioForOriginalBug:
    """
    The original incident: a 2.5V sample was stored as AFR=2.5 instead of
    AFR=14.87. With target AFR=14.7, the computed AFR error was ~-12, the
    VE correction was pegged at the -10% clamp, and real tunes were flashed
    from garbage corrections.

    This test guards the scenario end-to-end: the canonicalization must
    convert the 2.5V sample to a physically plausible AFR (13-17 range)
    before any downstream consumer sees it.
    """

    def test_lc2_sample_is_in_physical_afr_range(self):
        result = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 2.5)
        assert result is not None
        assert 10.0 < result.afr < 20.0, (
            f"AFR must be in physical range, got {result.afr:.3f} "
            "(did the rescale regress?)"
        )

    def test_stoich_voltage_is_near_stoich_afr(self):
        # DynoWare analog out is calibrated so 2.375V maps to ~14.5 AFR by
        # default LC-2 spec. Check within a loose tolerance.
        result = canonicalize_wideband_sample("LC2 Volts Petrol AFR1", 2.375)
        assert result is not None
        assert 14.0 <= result.afr <= 15.5
