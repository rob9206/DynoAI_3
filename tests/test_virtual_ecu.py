"""
Tests for Virtual ECU simulation.

Tests cover:
- VE table lookup and interpolation
- AFR target lookup
- Air mass calculation
- Fuel delivery calculation
- Resulting AFR calculation (key tuning function)
- Helper functions for table generation
"""

import numpy as np
import pytest

from api.services.virtual_ecu import (
    VirtualECU,
    create_afr_target_table,
    create_baseline_ve_table,
    create_intentionally_wrong_ve_table,
)


class TestVirtualECU:
    """Tests for VirtualECU class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create standard tables
        self.ve_table = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)
        self.afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

        # Create ECU
        self.ecu = VirtualECU(
            ve_table_front=self.ve_table,
            ve_table_rear=self.ve_table,
            afr_target_table=self.afr_table,
        )

    def test_initialization(self):
        """Test ECU initializes correctly."""
        assert self.ecu is not None
        assert self.ecu.ve_table_front.shape == (11, 9)
        assert self.ecu.ve_table_rear.shape == (11, 9)
        assert self.ecu.afr_target_table.shape == (11, 9)
        assert self.ecu._interp_ve_front is not None
        assert self.ecu._interp_ve_rear is not None
        assert self.ecu._interp_afr_target is not None

    def test_ve_lookup_at_grid_points(self):
        """Test VE lookup at exact grid points."""
        # Lookup at grid point
        ve = self.ecu.lookup_ve(rpm=4000, map_kpa=80, cylinder="front")

        # Should be close to peak VE at peak RPM and high MAP
        assert 0.7 < ve < 1.0
        assert isinstance(ve, float)

    def test_ve_lookup_interpolation(self):
        """Test VE lookup between grid points (interpolation)."""
        # Lookup between grid points
        ve1 = self.ecu.lookup_ve(rpm=3500, map_kpa=75, cylinder="front")
        ve2 = self.ecu.lookup_ve(rpm=4000, map_kpa=80, cylinder="front")

        # Both should be valid
        assert 0.3 < ve1 < 1.5
        assert 0.3 < ve2 < 1.5

        # Should be different (not same grid point)
        assert ve1 != ve2

    def test_afr_target_lookup(self):
        """Test AFR target lookup."""
        # Light load (low MAP) - should be lean
        afr_cruise = self.ecu.lookup_target_afr(rpm=3000, map_kpa=30)

        # Heavy load (high MAP) - should be rich
        afr_wot = self.ecu.lookup_target_afr(rpm=3000, map_kpa=90)

        # Cruise should be leaner than WOT
        assert afr_cruise > afr_wot
        assert 12.0 < afr_wot < 13.5
        assert 13.0 < afr_cruise < 15.0

    def test_air_mass_calculation(self):
        """Test air mass calculation using ideal gas law."""
        # Calculate air mass at typical operating point
        air_mass = self.ecu.calculate_air_mass_mg(rpm=3000, map_kpa=80)

        # Should be reasonable for M8 114ci engine
        # Rough estimate: ~500-1500 mg per combustion event
        assert 200 < air_mass < 2000
        assert isinstance(air_mass, float)

    def test_air_mass_increases_with_map(self):
        """Test that air mass increases with MAP (more boost/less vacuum)."""
        air_low = self.ecu.calculate_air_mass_mg(rpm=3000, map_kpa=30)
        air_high = self.ecu.calculate_air_mass_mg(rpm=3000, map_kpa=90)

        # Higher MAP = more air
        assert air_high > air_low
        assert air_high / air_low > 2.0  # Should be roughly 3x

    def test_required_fuel_calculation(self):
        """Test required fuel calculation for target AFR."""
        # Calculate required fuel
        fuel = self.ecu.calculate_required_fuel_mg(rpm=3000, map_kpa=80)

        # Should be reasonable
        assert 20 < fuel < 200
        assert isinstance(fuel, float)

    def test_delivered_fuel_with_ve(self):
        """Test that delivered fuel scales with VE."""
        # Get delivered fuel at a point
        fuel = self.ecu.calculate_delivered_fuel_mg(
            rpm=4000, map_kpa=80, cylinder="front"
        )

        # Should be reasonable
        assert 20 < fuel < 200

        # Fuel should scale with VE
        ve = self.ecu.lookup_ve(rpm=4000, map_kpa=80, cylinder="front")
        base_fuel = self.ecu.calculate_required_fuel_mg(rpm=4000, map_kpa=80)

        # Delivered fuel ≈ base fuel × VE
        assert abs(fuel - base_fuel * ve) < 1.0  # Within 1mg

    def test_resulting_afr_perfect_ve(self):
        """Test resulting AFR when ECU VE matches actual VE."""
        # When ECU VE = actual VE, AFR should be on target
        rpm, map_kpa = 4000, 80

        # Get ECU's VE
        ecu_ve = self.ecu.lookup_ve(rpm, map_kpa, "front")

        # Calculate resulting AFR with same VE
        resulting_afr = self.ecu.calculate_resulting_afr(
            rpm, map_kpa, actual_ve=ecu_ve, cylinder="front"
        )

        # Get target AFR
        target_afr = self.ecu.lookup_target_afr(rpm, map_kpa)

        # Should be very close (within 0.01)
        assert abs(resulting_afr - target_afr) < 0.01

    def test_resulting_afr_high_actual_ve(self):
        """Test resulting AFR when actual VE > ECU VE (lean condition)."""
        rpm, map_kpa = 4000, 80

        # Get ECU's VE
        ecu_ve = self.ecu.lookup_ve(rpm, map_kpa, "front")

        # Actual VE is higher (engine breathes better than ECU knows)
        actual_ve = ecu_ve * 1.1  # 10% higher

        # Calculate resulting AFR
        resulting_afr = self.ecu.calculate_resulting_afr(
            rpm, map_kpa, actual_ve=actual_ve, cylinder="front"
        )

        # Get target AFR
        target_afr = self.ecu.lookup_target_afr(rpm, map_kpa)

        # Should be LEAN (higher AFR than target)
        assert resulting_afr > target_afr

        # Should be approximately 10% leaner
        assert abs((resulting_afr / target_afr) - 1.1) < 0.01

    def test_resulting_afr_low_actual_ve(self):
        """Test resulting AFR when actual VE < ECU VE (rich condition)."""
        rpm, map_kpa = 4000, 80

        # Get ECU's VE
        ecu_ve = self.ecu.lookup_ve(rpm, map_kpa, "front")

        # Actual VE is lower (engine breathes worse than ECU thinks)
        actual_ve = ecu_ve * 0.9  # 10% lower

        # Calculate resulting AFR
        resulting_afr = self.ecu.calculate_resulting_afr(
            rpm, map_kpa, actual_ve=actual_ve, cylinder="front"
        )

        # Get target AFR
        target_afr = self.ecu.lookup_target_afr(rpm, map_kpa)

        # Should be RICH (lower AFR than target)
        assert resulting_afr < target_afr

        # Should be approximately 10% richer
        assert abs((resulting_afr / target_afr) - 0.9) < 0.01

    def test_ve_error_calculation(self):
        """Test VE error percentage calculation."""
        rpm, map_kpa = 4000, 80

        # Get ECU's VE
        ecu_ve = self.ecu.lookup_ve(rpm, map_kpa, "front")

        # Test with 10% higher actual VE
        actual_ve = ecu_ve * 1.1
        error_pct = self.ecu.get_ve_error_pct(rpm, map_kpa, actual_ve, "front")

        # Should be approximately +10%
        assert abs(error_pct - 10.0) < 0.1

    def test_front_rear_independence(self):
        """Test that front and rear cylinders can have different VE."""
        # Create ECU with different front/rear VE
        ve_front = create_baseline_ve_table(peak_ve=0.85)
        ve_rear = create_baseline_ve_table(peak_ve=0.80)  # 5% lower

        ecu = VirtualECU(
            ve_table_front=ve_front,
            ve_table_rear=ve_rear,
            afr_target_table=self.afr_table,
        )

        rpm, map_kpa = 4000, 80

        # Lookup VE for both cylinders
        ve_f = ecu.lookup_ve(rpm, map_kpa, "front")
        ve_r = ecu.lookup_ve(rpm, map_kpa, "rear")

        # Rear should be lower
        assert ve_r < ve_f
        assert abs((ve_r / ve_f) - (0.80 / 0.85)) < 0.05


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_baseline_ve_table(self):
        """Test baseline VE table creation."""
        ve_table = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)

        # Check shape
        assert ve_table.shape == (11, 9)

        # Check range
        assert np.all(ve_table >= 0.3)
        assert np.all(ve_table <= 1.5)

        # Check peak is reasonable
        assert np.max(ve_table) >= 0.80
        assert np.max(ve_table) <= 1.0

    def test_create_afr_target_table(self):
        """Test AFR target table creation."""
        afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

        # Check shape
        assert afr_table.shape == (11, 9)

        # Check range
        assert np.all(afr_table >= 12.0)
        assert np.all(afr_table <= 15.0)

        # Low MAP should be leaner
        assert afr_table[0, 0] > afr_table[0, -1]

    def test_create_intentionally_wrong_ve_table(self):
        """Test creation of intentionally wrong VE table."""
        # Create baseline
        baseline = create_baseline_ve_table(peak_ve=0.85)

        # Create wrong version (10% too low)
        wrong = create_intentionally_wrong_ve_table(
            baseline, error_pct_mean=-10.0, error_pct_std=2.0, seed=42
        )

        # Check shape
        assert wrong.shape == baseline.shape

        # Check that it's different
        assert not np.allclose(wrong, baseline)

        # Check that mean error is approximately -10%
        error_pct = ((wrong - baseline) / baseline) * 100
        mean_error = np.mean(error_pct)
        assert abs(mean_error - (-10.0)) < 2.0  # Within 2% of target

    def test_wrong_ve_table_reproducibility(self):
        """Test that wrong VE table is reproducible with same seed."""
        baseline = create_baseline_ve_table(peak_ve=0.85)

        # Create two tables with same seed
        wrong1 = create_intentionally_wrong_ve_table(baseline, seed=42)
        wrong2 = create_intentionally_wrong_ve_table(baseline, seed=42)

        # Should be identical
        assert np.allclose(wrong1, wrong2)


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_tuning_scenario(self):
        """Test a complete tuning scenario: wrong VE → AFR errors → corrections."""
        # Create correct VE
        correct_ve = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)

        # Create wrong VE (ECU thinks VE is 10% lower)
        wrong_ve = correct_ve * 0.9

        # Create ECU with wrong VE
        afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)
        ecu = VirtualECU(
            ve_table_front=wrong_ve,
            ve_table_rear=wrong_ve,
            afr_target_table=afr_table,
        )

        # Test at WOT condition
        rpm, map_kpa = 4000, 80

        # Calculate resulting AFR with correct actual VE
        actual_ve = correct_ve[5, 7]  # Approximate grid indices for 4000 RPM, 80 kPa
        resulting_afr = ecu.calculate_resulting_afr(rpm, map_kpa, actual_ve, "front")

        # Get target
        target_afr = ecu.lookup_target_afr(rpm, map_kpa)

        # AFR should be lean (actual VE > ECU VE)
        afr_error = resulting_afr - target_afr
        assert afr_error > 0  # Lean

        # Calculate required VE correction
        # VE correction = AFR_measured / AFR_target (v2.0.0 formula)
        ve_correction = resulting_afr / target_afr

        # Correction should be approximately 1.11 (need 11% more fuel)
        # Allow wider tolerance due to interpolation effects
        assert abs(ve_correction - 1.11) < 0.05

        # Apply correction to ECU's VE table
        corrected_ve = wrong_ve * ve_correction

        # Corrected VE should be close to actual (within 5%)
        assert abs(corrected_ve[5, 7] - actual_ve) < 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
