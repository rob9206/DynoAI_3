"""
Tests for Environmental Corrections Module

Author: DynoAI_3
Date: 2025-12-15
"""

import pytest
import math
from dynoai.core.environmental import (
    EnvironmentalCorrector,
    EnvironmentalConditions,
    StandardConditions,
    CorrectionStandard,
    EnvironmentalCorrectionResult,
    estimate_altitude_from_baro,
    estimate_baro_from_altitude,
    calculate_altitude_correction,
    calculate_density_altitude,
    calculate_sae_j1349_correction,
    STANDARD_CONDITIONS,
)


class TestEnvironmentalConditions:
    """Tests for EnvironmentalConditions dataclass."""
    
    def test_default_values(self):
        """Test default standard conditions."""
        conditions = EnvironmentalConditions()
        assert conditions.barometric_pressure_inhg == 29.92
        assert conditions.ambient_temp_f == 77.0
        assert conditions.humidity_percent == 0.0
    
    def test_altitude_calculated_from_baro(self):
        """Test that altitude is auto-calculated from barometric pressure."""
        # Sea level
        conditions = EnvironmentalConditions(barometric_pressure_inhg=29.92)
        assert conditions.altitude_ft is not None
        assert abs(conditions.altitude_ft) < 100  # Near sea level
        
        # ~5000 ft
        conditions = EnvironmentalConditions(barometric_pressure_inhg=24.89)
        assert 4500 < conditions.altitude_ft < 5500
    
    def test_explicit_altitude_preserved(self):
        """Test that explicit altitude is not overwritten."""
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=29.92,
            altitude_ft=1000.0,
        )
        assert conditions.altitude_ft == 1000.0


class TestAltitudeEstimation:
    """Tests for altitude/barometric conversion functions."""
    
    def test_sea_level(self):
        """Test sea level altitude from standard pressure."""
        altitude = estimate_altitude_from_baro(29.92)
        assert abs(altitude) < 50  # Should be near 0
    
    def test_common_altitudes(self):
        """Test altitude estimation at common elevations."""
        # Denver, CO (~5280 ft)
        altitude = estimate_altitude_from_baro(24.63)
        assert 5000 < altitude < 5600
        
        # Mexico City (~7350 ft)
        altitude = estimate_altitude_from_baro(22.65)
        assert 7000 < altitude < 7700
    
    def test_round_trip_conversion(self):
        """Test baro -> altitude -> baro round trip."""
        original_baro = 26.5
        altitude = estimate_altitude_from_baro(original_baro)
        recovered_baro = estimate_baro_from_altitude(altitude)
        assert abs(original_baro - recovered_baro) < 0.01
    
    def test_altitude_to_baro(self):
        """Test altitude to barometric pressure conversion."""
        # Sea level
        baro = estimate_baro_from_altitude(0)
        assert abs(baro - 29.92) < 0.01
        
        # 5000 ft
        baro = estimate_baro_from_altitude(5000)
        assert 24.5 < baro < 25.0


class TestEnvironmentalCorrector:
    """Tests for EnvironmentalCorrector class."""
    
    def test_default_initialization(self):
        """Test corrector with default parameters."""
        corrector = EnvironmentalCorrector()
        assert corrector.standard == CorrectionStandard.SAE_J1349
        assert corrector.enable_pressure is True
        assert corrector.enable_temperature is True
        assert corrector.enable_humidity is True
        assert corrector.enable_ect is True
    
    def test_standard_day_no_correction(self):
        """Test that standard conditions give correction of 1.0."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions()  # Standard conditions
        result = corrector.calculate(conditions)
        
        assert result.is_standard_day is True
        assert 0.99 < result.total_correction < 1.01
    
    def test_high_altitude_reduces_fuel(self):
        """Test that high altitude requires less fuel."""
        corrector = EnvironmentalCorrector()
        
        # 5000 ft altitude
        conditions = EnvironmentalConditions(barometric_pressure_inhg=24.89)
        result = corrector.calculate(conditions)
        
        # Should need ~15-20% less fuel
        assert result.total_correction < 0.90
        assert result.pressure_correction < 1.0
    
    def test_hot_temperature_reduces_fuel(self):
        """Test that hot temperatures require less fuel."""
        corrector = EnvironmentalCorrector()
        
        # Hot day (95°F vs standard 77°F)
        conditions = EnvironmentalConditions(ambient_temp_f=95.0)
        result = corrector.calculate(conditions)
        
        # Should need less fuel (hot air is less dense)
        assert result.temperature_correction < 1.0
        assert result.total_correction < 1.0
    
    def test_cold_temperature_increases_fuel(self):
        """Test that cold temperatures require more fuel."""
        corrector = EnvironmentalCorrector()
        
        # Cold day (40°F vs standard 77°F)
        conditions = EnvironmentalConditions(ambient_temp_f=40.0)
        result = corrector.calculate(conditions)
        
        # Should need more fuel (cold air is denser)
        assert result.temperature_correction > 1.0
        assert result.total_correction > 1.0
    
    def test_high_humidity_reduces_fuel(self):
        """Test that high humidity requires slightly less fuel."""
        corrector = EnvironmentalCorrector()
        
        # Humid day (80% RH)
        conditions = EnvironmentalConditions(humidity_percent=80.0)
        result = corrector.calculate(conditions)
        
        # Should need slightly less fuel (water vapor displaces oxygen)
        assert result.humidity_correction < 1.0
    
    def test_cold_engine_increases_fuel(self):
        """Test that cold engine requires enrichment."""
        corrector = EnvironmentalCorrector()
        
        # Cold engine (120°F)
        conditions = EnvironmentalConditions(ect_f=120.0)
        result = corrector.calculate(conditions)
        
        # Should need more fuel (cold engine enrichment)
        assert result.ect_correction > 1.0
        assert result.ect_correction > 1.10  # At least 10% enrichment
    
    def test_warm_engine_no_correction(self):
        """Test that warm engine needs no correction."""
        corrector = EnvironmentalCorrector()
        
        # Warm engine (190°F)
        conditions = EnvironmentalConditions(ect_f=190.0)
        result = corrector.calculate(conditions)
        
        assert result.ect_correction == 1.0
    
    def test_transitional_ect(self):
        """Test ECT correction during warmup."""
        corrector = EnvironmentalCorrector()
        
        # Mid-warmup (170°F - between cold and warm thresholds)
        conditions = EnvironmentalConditions(ect_f=170.0)
        result = corrector.calculate(conditions)
        
        # Should have some enrichment, but less than cold
        assert 1.0 < result.ect_correction < 1.15
    
    def test_combined_conditions(self):
        """Test combined environmental effects."""
        corrector = EnvironmentalCorrector()
        
        # Denver hot day: 5000 ft altitude, 95°F, 30% humidity
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=24.89,
            ambient_temp_f=95.0,
            humidity_percent=30.0,
        )
        result = corrector.calculate(conditions)
        
        # All factors reduce fuel requirement
        assert result.total_correction < 0.90
        assert result.pressure_correction < 1.0
        assert result.temperature_correction < 1.0
        assert result.humidity_correction < 1.0
    
    def test_corrections_multiplicative(self):
        """Test that corrections are applied multiplicatively."""
        corrector = EnvironmentalCorrector(enable_ect=False)
        
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=27.0,  # ~3000 ft
            ambient_temp_f=85.0,  # Warm
            humidity_percent=50.0,  # Moderate humidity
        )
        result = corrector.calculate(conditions)
        
        # Total should be product of individual corrections
        expected = (
            result.pressure_correction *
            result.temperature_correction *
            result.humidity_correction
        )
        assert abs(result.total_correction - expected) < 0.001
    
    def test_safety_clamping(self):
        """Test that extreme corrections are clamped."""
        corrector = EnvironmentalCorrector(max_correction=1.20)
        
        # Extreme conditions (very high altitude + very cold)
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=18.0,  # ~15000 ft
            ambient_temp_f=0.0,  # Very cold
        )
        result = corrector.calculate(conditions)
        
        # Should be clamped
        assert result.total_correction >= 1.0 / 1.20
        assert result.total_correction <= 1.20
    
    def test_disable_individual_corrections(self):
        """Test disabling individual correction factors."""
        corrector = EnvironmentalCorrector(
            enable_pressure=False,
            enable_humidity=False,
            enable_ect=False,
        )
        
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=24.89,  # Would normally affect
            humidity_percent=80.0,  # Would normally affect
            ect_f=120.0,  # Would normally affect
            ambient_temp_f=90.0,  # Still enabled
        )
        result = corrector.calculate(conditions)
        
        # Only temperature should affect result
        assert result.pressure_correction == 1.0
        assert result.humidity_correction == 1.0
        assert result.ect_correction == 1.0
        assert result.temperature_correction != 1.0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_calculate_altitude_correction(self):
        """Test altitude-only correction function."""
        # Sea level
        corr = calculate_altitude_correction(0)
        assert abs(corr - 1.0) < 0.01
        
        # 5000 ft
        corr = calculate_altitude_correction(5000)
        assert 0.80 < corr < 0.90
    
    def test_calculate_density_altitude(self):
        """Test density altitude calculation."""
        # Standard day at 5000 ft
        # ISA temp at 5000 ft = 59 - (5000/1000 * 3.5) = 41.5°F
        da = calculate_density_altitude(5000, 41.5)
        assert abs(da - 5000) < 200  # Should be close to pressure altitude
        
        # Hot day at 5000 ft (95°F vs ISA 41.5°F = +53.5°F deviation)
        da = calculate_density_altitude(5000, 95)
        # DA = 5000 + (120 * 53.5) = 5000 + 6420 = 11420 ft
        assert da > 10000  # Much higher than pressure altitude
    
    def test_calculate_sae_j1349_correction(self):
        """Test SAE J1349 correction function."""
        # Standard conditions
        corr = calculate_sae_j1349_correction(29.92, 77.0, 0.0)
        assert abs(corr - 1.0) < 0.01
        
        # High altitude, hot, humid
        corr = calculate_sae_j1349_correction(24.89, 95.0, 60.0)
        assert corr < 0.90  # Significant reduction


class TestCorrectionStandards:
    """Tests for different correction standards."""
    
    def test_sae_vs_din_reference_temp(self):
        """Test different reference temps between standards."""
        sae = STANDARD_CONDITIONS[CorrectionStandard.SAE_J1349]
        din = STANDARD_CONDITIONS[CorrectionStandard.DIN_70020]
        
        assert sae.temp_f == 77.0  # 25°C
        assert din.temp_f == 68.0  # 20°C
    
    def test_different_standards_give_different_results(self):
        """Test that different standards produce different corrections."""
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=28.0,
            ambient_temp_f=85.0,
        )
        
        sae_corrector = EnvironmentalCorrector(standard=CorrectionStandard.SAE_J1349)
        din_corrector = EnvironmentalCorrector(standard=CorrectionStandard.DIN_70020)
        
        sae_result = sae_corrector.calculate(conditions)
        din_result = din_corrector.calculate(conditions)
        
        # Results should differ due to different reference temps
        assert sae_result.total_correction != din_result.total_correction


class TestCorrectionSummary:
    """Tests for human-readable summary output."""
    
    def test_summary_generation(self):
        """Test that summary is generated correctly."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=26.0,
            ambient_temp_f=85.0,
            humidity_percent=40.0,
            ect_f=185.0,
        )
        
        summary = corrector.get_correction_summary(conditions)
        
        assert "Environmental Correction Summary" in summary
        assert "Barometric:" in summary
        assert "Altitude:" in summary
        assert "Ambient Temp:" in summary
        assert "Humidity:" in summary
        assert "TOTAL CORRECTION:" in summary


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_humidity(self):
        """Test zero humidity (dry air)."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(humidity_percent=0.0)
        result = corrector.calculate(conditions)
        
        assert result.humidity_correction == 1.0
    
    def test_no_ect_data(self):
        """Test when ECT data is not available."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(ect_f=None)
        result = corrector.calculate(conditions)
        
        assert result.ect_correction == 1.0
    
    def test_very_low_pressure(self):
        """Test extremely low barometric pressure."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(barometric_pressure_inhg=15.0)  # ~18000 ft
        result = corrector.calculate(conditions)
        
        # Should be clamped but still valid
        assert result.total_correction > 0
        assert result.total_correction <= corrector.max_correction
    
    def test_extreme_temperatures(self):
        """Test extreme temperature values."""
        corrector = EnvironmentalCorrector()
        
        # Very cold
        cold = EnvironmentalConditions(ambient_temp_f=-20.0)
        cold_result = corrector.calculate(cold)
        assert cold_result.temperature_correction > 1.0
        
        # Very hot
        hot = EnvironmentalConditions(ambient_temp_f=120.0)
        hot_result = corrector.calculate(hot)
        assert hot_result.temperature_correction < 1.0


class TestIntegrationScenarios:
    """Integration tests with real-world scenarios."""
    
    def test_denver_summer(self):
        """Test Denver, CO summer conditions."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=24.63,  # 5280 ft
            ambient_temp_f=88.0,
            humidity_percent=25.0,
        )
        result = corrector.calculate(conditions)
        
        # Should need significantly less fuel
        assert 0.80 < result.total_correction < 0.90
    
    def test_florida_summer(self):
        """Test Florida summer conditions (sea level, hot, humid)."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=30.0,  # Sea level, high pressure
            ambient_temp_f=95.0,
            humidity_percent=85.0,
        )
        result = corrector.calculate(conditions)
        
        # Hot and humid reduce fuel need, but high pressure increases it
        # Net effect is small reduction
        assert 0.90 < result.total_correction < 1.0
    
    def test_cold_start_scenario(self):
        """Test cold start in cold weather."""
        corrector = EnvironmentalCorrector()
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=30.1,
            ambient_temp_f=35.0,  # Cold day
            humidity_percent=60.0,
            ect_f=80.0,  # Very cold engine
        )
        result = corrector.calculate(conditions)
        
        # Cold air + cold engine = significant enrichment needed
        assert result.total_correction > 1.15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])








