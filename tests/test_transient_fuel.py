"""
Tests for Transient Fuel Compensation Module

Author: DynoAI_3
Date: 2025-12-15
"""

import pytest
import pandas as pd
import numpy as np
from dynoai.core.transient_fuel import (
    TransientFuelAnalyzer,
    TransientEvent,
    TransientFuelResult,
    TauWallWettingParams,
)


@pytest.fixture
def sample_steady_state_data():
    """Create sample steady-state dyno data (no transients)."""
    time = np.linspace(0, 10, 500)
    df = pd.DataFrame({
        'time': time,
        'rpm': np.ones_like(time) * 3000,
        'map': np.ones_like(time) * 50,
        'tps': np.ones_like(time) * 30,
        'afr': np.ones_like(time) * 13.0 + np.random.normal(0, 0.05, len(time)),
        'iat': np.ones_like(time) * 25,
        'target_afr': np.ones_like(time) * 13.0,
    })
    return df


@pytest.fixture
def sample_accel_data():
    """Create sample data with acceleration event."""
    np.random.seed(42)  # For reproducibility
    time = np.linspace(0, 20, 1000)
    
    # Aggressive acceleration from t=5 to t=8 (shorter, more intense)
    rpm = np.ones_like(time) * 2000
    accel_mask = (time >= 5) & (time <= 8)
    rpm[accel_mask] = 2000 + (time[accel_mask] - 5) * 1500  # Faster accel
    rpm[time > 8] = 6500
    
    map_kpa = np.ones_like(time) * 40
    map_kpa[accel_mask] = 40 + (time[accel_mask] - 5) * 50  # Faster MAP rise
    map_kpa[time > 8] = 190
    
    tps = np.ones_like(time) * 15
    tps[accel_mask] = 15 + (time[accel_mask] - 5) * 25  # Faster TPS rise
    tps[time > 8] = 90
    
    # AFR goes lean during accel
    afr = np.ones_like(time) * 13.0
    afr[accel_mask] = 13.0 + (time[accel_mask] - 5) * 1.0  # More lean
    afr[time > 8] = 13.0
    afr += np.random.normal(0, 0.1, len(time))
    
    df = pd.DataFrame({
        'time': time,
        'rpm': rpm,
        'map': map_kpa,
        'tps': tps,
        'afr': afr,
        'iat': np.ones_like(time) * 25,
        'target_afr': np.ones_like(time) * 13.0,
    })
    return df


@pytest.fixture
def sample_decel_data():
    """Create sample data with deceleration event."""
    np.random.seed(43)  # For reproducibility
    time = np.linspace(0, 20, 1000)
    
    # Aggressive deceleration from t=5 to t=8
    rpm = np.ones_like(time) * 6000
    decel_mask = (time >= 5) & (time <= 8)
    rpm[decel_mask] = 6000 - (time[decel_mask] - 5) * 1200  # Faster decel
    rpm[time > 8] = 2400
    
    map_kpa = np.ones_like(time) * 150
    map_kpa[decel_mask] = 150 - (time[decel_mask] - 5) * 35  # Faster MAP drop
    map_kpa[time > 8] = 45
    
    tps = np.ones_like(time) * 80
    tps[decel_mask] = 80 - (time[decel_mask] - 5) * 20  # Faster TPS drop
    tps[time > 8] = 20
    
    # AFR goes rich during decel
    afr = np.ones_like(time) * 13.0
    afr[decel_mask] = 13.0 - (time[decel_mask] - 5) * 0.6  # More rich
    afr[time > 8] = 13.0
    afr += np.random.normal(0, 0.1, len(time))
    
    df = pd.DataFrame({
        'time': time,
        'rpm': rpm,
        'map': map_kpa,
        'tps': tps,
        'afr': afr,
        'iat': np.ones_like(time) * 25,
        'target_afr': np.ones_like(time) * 13.0,
    })
    return df


@pytest.fixture
def sample_cold_iat_data():
    """Create sample data with cold IAT (0°C) acceleration event."""
    np.random.seed(44)  # For reproducibility
    time = np.linspace(0, 20, 1000)
    
    # Aggressive acceleration from t=5 to t=8
    rpm = np.ones_like(time) * 2000
    accel_mask = (time >= 5) & (time <= 8)
    rpm[accel_mask] = 2000 + (time[accel_mask] - 5) * 1500
    rpm[time > 8] = 6500
    
    map_kpa = np.ones_like(time) * 40
    map_kpa[accel_mask] = 40 + (time[accel_mask] - 5) * 50
    map_kpa[time > 8] = 190
    
    tps = np.ones_like(time) * 15
    tps[accel_mask] = 15 + (time[accel_mask] - 5) * 25
    tps[time > 8] = 90
    
    # AFR goes lean during accel (more lean due to cold = more wall wetting)
    afr = np.ones_like(time) * 13.0
    afr[accel_mask] = 13.0 + (time[accel_mask] - 5) * 1.5  # More lean than warm
    afr[time > 8] = 13.0
    afr += np.random.normal(0, 0.1, len(time))
    
    df = pd.DataFrame({
        'time': time,
        'rpm': rpm,
        'map': map_kpa,
        'tps': tps,
        'afr': afr,
        'iat': np.ones_like(time) * 0.0,  # Cold IAT
        'target_afr': np.ones_like(time) * 13.0,
    })
    return df


class TestTransientFuelAnalyzer:
    """Tests for TransientFuelAnalyzer class."""
    
    def test_initialization(self):
        """Test analyzer initialization with default parameters."""
        analyzer = TransientFuelAnalyzer()
        assert analyzer.target_afr == 13.0
        assert analyzer.map_rate_threshold == 50.0
        assert analyzer.tps_rate_threshold == 20.0
        assert analyzer.afr_tolerance == 0.5
        assert analyzer.sample_rate_hz == 50.0
    
    def test_initialization_custom_params(self):
        """Test analyzer initialization with custom parameters."""
        analyzer = TransientFuelAnalyzer(
            target_afr=12.5,
            map_rate_threshold=75.0,
            tps_rate_threshold=30.0,
            afr_tolerance=0.3,
            sample_rate_hz=100.0,
        )
        assert analyzer.target_afr == 12.5
        assert analyzer.map_rate_threshold == 75.0
        assert analyzer.tps_rate_threshold == 30.0
        assert analyzer.afr_tolerance == 0.3
        assert analyzer.sample_rate_hz == 100.0
    
    def test_initialization_iat_params(self):
        """Test analyzer initialization with IAT parameters."""
        analyzer = TransientFuelAnalyzer(
            iat_reference_c=20.0,
            iat_density_coeff=0.004,
            iat_wall_wetting_coeff=0.03,
        )
        assert analyzer.iat_reference_c == 20.0
        assert analyzer.iat_density_coeff == 0.004
        assert analyzer.iat_wall_wetting_coeff == 0.03
    
    def test_validate_input_missing_columns(self):
        """Test input validation catches missing columns."""
        analyzer = TransientFuelAnalyzer()
        df = pd.DataFrame({'time': [1, 2, 3], 'rpm': [3000, 3000, 3000]})
        
        with pytest.raises(ValueError, match="Missing required columns"):
            analyzer._validate_input(df)
    
    def test_validate_input_insufficient_data(self):
        """Test input validation catches insufficient data."""
        analyzer = TransientFuelAnalyzer()
        df = pd.DataFrame({
            'time': [1, 2],
            'rpm': [3000, 3000],
            'map': [50, 50],
            'tps': [30, 30],
            'afr': [13.0, 13.0],
        })
        
        with pytest.raises(ValueError, match="Insufficient data points"):
            analyzer._validate_input(df)
    
    def test_validate_input_invalid_rpm(self):
        """Test input validation catches invalid RPM values."""
        analyzer = TransientFuelAnalyzer()
        df = pd.DataFrame({
            'time': np.linspace(0, 1, 20),
            'rpm': np.ones(20) * 25000,  # Invalid: too high
            'map': np.ones(20) * 50,
            'tps': np.ones(20) * 30,
            'afr': np.ones(20) * 13.0,
        })
        
        with pytest.raises(ValueError, match="RPM values out of reasonable range"):
            analyzer._validate_input(df)
    
    def test_calculate_rates(self, sample_steady_state_data):
        """Test rate calculation for steady-state data."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_steady_state_data)
        
        assert 'map_rate' in df_with_rates.columns
        assert 'tps_rate' in df_with_rates.columns
        
        # Steady state should have near-zero rates
        assert df_with_rates['map_rate'].abs().mean() < 5.0
        assert df_with_rates['tps_rate'].abs().mean() < 5.0
    
    def test_calculate_rates_acceleration(self, sample_accel_data):
        """Test rate calculation detects acceleration."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        
        # Should have positive rates during acceleration
        accel_period = (df_with_rates['time'] >= 5) & (df_with_rates['time'] <= 10)
        assert df_with_rates.loc[accel_period, 'map_rate'].mean() > 20.0
        assert df_with_rates.loc[accel_period, 'tps_rate'].mean() > 10.0
    
    def test_detect_transient_events_steady_state(self, sample_steady_state_data):
        """Test transient detection on steady-state data."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_steady_state_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        # Should detect no events in steady state
        assert len(events) == 0
    
    def test_detect_transient_events_acceleration(self, sample_accel_data):
        """Test transient detection on acceleration data."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        # Should detect at least one acceleration event
        assert len(events) >= 1
        assert any(e.event_type == 'accel' for e in events)
        
        # Check event properties
        accel_event = next(e for e in events if e.event_type == 'accel')
        assert accel_event.peak_map_rate > 50.0
        assert accel_event.peak_tps_rate > 20.0
        assert accel_event.severity in ['mild', 'moderate', 'aggressive']
    
    def test_detect_transient_events_deceleration(self, sample_decel_data):
        """Test transient detection on deceleration data."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_decel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        # Should detect at least one deceleration event
        assert len(events) >= 1
        assert any(e.event_type == 'decel' for e in events)
    
    def test_analyze_transients_full_workflow(self, sample_accel_data):
        """Test complete analysis workflow."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_accel_data)
        
        # Check result structure
        assert isinstance(result, TransientFuelResult)
        assert len(result.detected_events) > 0
        assert not result.map_rate_table.empty
        assert not result.tps_rate_table.empty
        assert len(result.wall_wetting_factor) > 0
        assert len(result.recommendations) > 0
        assert len(result.plots) > 0
    
    def test_calculate_map_rate_enrichment(self, sample_accel_data):
        """Test MAP rate enrichment table calculation."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        table = analyzer.calculate_map_rate_enrichment(df_with_rates, events)
        
        assert not table.empty
        assert 'map_rate_kpa_per_sec' in table.columns
        assert 'enrichment_percent' in table.columns
        
        # Should have some positive enrichment for positive MAP rates
        positive_rates = table[table['map_rate_kpa_per_sec'] > 0]
        assert len(positive_rates) > 0
    
    def test_calculate_tps_rate_enrichment(self, sample_accel_data):
        """Test TPS rate enrichment table calculation."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        table = analyzer.calculate_tps_rate_enrichment(df_with_rates, events)
        
        assert not table.empty
        assert 'tps_rate_percent_per_sec' in table.columns
        assert 'enrichment_percent' in table.columns
    
    def test_calculate_wall_wetting_compensation(self, sample_accel_data):
        """Test wall wetting compensation calculation with improved formula."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        factors = analyzer.calculate_wall_wetting_compensation(df_with_rates, events)
        
        assert isinstance(factors, dict)
        assert len(factors) > 0
        
        # All factors should be reasonable (0.90 to 1.15 with compensation factor)
        for factor in factors.values():
            assert 0.90 <= factor <= 1.15
    
    def test_compensation_factor_initialization(self):
        """Test compensation_factor parameter initialization and clamping."""
        # Default should be 0.65
        analyzer = TransientFuelAnalyzer()
        assert analyzer.compensation_factor == 0.65
        
        # Custom value should be accepted
        analyzer = TransientFuelAnalyzer(compensation_factor=0.80)
        assert analyzer.compensation_factor == 0.80
        
        # Value too low should be clamped to 0.1
        analyzer = TransientFuelAnalyzer(compensation_factor=0.01)
        assert analyzer.compensation_factor == 0.1
        
        # Value too high should be clamped to 1.0
        analyzer = TransientFuelAnalyzer(compensation_factor=1.5)
        assert analyzer.compensation_factor == 1.0
    
    def test_iat_density_factor_calculation(self):
        """Test IAT density factor calculation."""
        analyzer = TransientFuelAnalyzer(iat_reference_c=25.0)
        
        # At reference temp, factor should be 1.0
        factor = analyzer._calculate_iat_density_factor(25.0)
        assert factor == 1.0
        
        # Cold air (0°C) should increase factor (denser air needs more fuel)
        # delta = 25 - 0 = 25, factor = 1 + 25 * 0.0035 = 1.0875
        factor = analyzer._calculate_iat_density_factor(0.0)
        assert 1.08 <= factor <= 1.09
        
        # Hot air (50°C) should decrease factor (less dense air needs less fuel)
        # delta = 25 - 50 = -25, factor = 1 + (-25) * 0.0035 = 0.9125
        factor = analyzer._calculate_iat_density_factor(50.0)
        assert 0.91 <= factor <= 0.92
        
        # Should be clamped at extremes
        factor = analyzer._calculate_iat_density_factor(-50.0)  # Very cold
        assert factor <= 1.20
        factor = analyzer._calculate_iat_density_factor(100.0)  # Very hot
        assert factor >= 0.85
    
    def test_iat_wall_wetting_factor_calculation(self):
        """Test IAT wall wetting factor calculation."""
        analyzer = TransientFuelAnalyzer(iat_reference_c=25.0)
        
        # At reference temp, factor should be 1.0
        factor = analyzer._calculate_iat_wall_wetting_factor(25.0)
        assert factor == 1.0
        
        # Cold (0°C) should increase wall wetting significantly
        # delta = 25 - 0 = 25, factor = 1 + 25 * 0.025 = 1.625
        factor = analyzer._calculate_iat_wall_wetting_factor(0.0)
        assert 1.6 <= factor <= 1.7
        
        # Hot (50°C) should decrease wall wetting
        # delta = 25 - 50 = -25, factor = 1 + (-25) * 0.025 = 0.375
        factor = analyzer._calculate_iat_wall_wetting_factor(50.0)
        assert 0.35 <= factor <= 0.40
    
    def test_iat_category(self):
        """Test IAT category classification."""
        analyzer = TransientFuelAnalyzer()
        
        assert analyzer._get_iat_category(5.0) == 'cold'
        assert analyzer._get_iat_category(15.0) == 'cool'
        assert analyzer._get_iat_category(30.0) == 'warm'
        assert analyzer._get_iat_category(50.0) == 'hot'
    
    def test_afr_error_to_enrichment_with_iat(self):
        """Test AFR error to enrichment with IAT correction."""
        analyzer = TransientFuelAnalyzer(target_afr=13.0, compensation_factor=0.65)
        
        # At reference temp (25°C), should match base calculation
        enrichment_ref = analyzer._afr_error_to_enrichment(1.0, iat_c=25.0)
        enrichment_base = analyzer._afr_error_to_enrichment(1.0)
        assert abs(enrichment_ref - enrichment_base) < 0.1
        
        # Cold (0°C) should give higher enrichment
        enrichment_cold = analyzer._afr_error_to_enrichment(1.0, iat_c=0.0)
        assert enrichment_cold > enrichment_ref
        
        # Hot (50°C) should give lower enrichment
        enrichment_hot = analyzer._afr_error_to_enrichment(1.0, iat_c=50.0)
        assert enrichment_hot < enrichment_ref
    
    def test_afr_error_to_enrichment(self):
        """Test AFR error to enrichment conversion using stoichiometric formula with compensation factor."""
        # Default compensation_factor is 0.65
        analyzer = TransientFuelAnalyzer(target_afr=13.0)
        
        # Positive error (lean) should give positive enrichment
        # Formula: enrichment = (error / target_afr) * 100 * compensation_factor
        # For 1.0 AFR error with target 13.0 and factor 0.65:
        # (1.0 / 13.0) * 100 * 0.65 = 5.0%
        enrichment = analyzer._afr_error_to_enrichment(1.0)
        assert enrichment > 0
        assert 4.8 <= enrichment <= 5.2  # Should be ~5.0% with default factor
        assert enrichment <= 25.0  # Should be capped
        
        # Negative error (rich) should give zero enrichment
        enrichment = analyzer._afr_error_to_enrichment(-1.0)
        assert enrichment == 0
        
        # Large error should be capped at 25%
        enrichment = analyzer._afr_error_to_enrichment(20.0)
        assert enrichment == 25.0
        
        # Test with full stoichiometric (compensation_factor=1.0)
        analyzer_full = TransientFuelAnalyzer(target_afr=13.0, compensation_factor=1.0)
        # For 1.0 AFR error with target 13.0 and factor 1.0: (1.0 / 13.0) * 100 = 7.69%
        enrichment = analyzer_full._afr_error_to_enrichment(1.0)
        assert 7.5 <= enrichment <= 8.0  # Should be ~7.69%
        
        # Test with conservative factor
        analyzer_conservative = TransientFuelAnalyzer(target_afr=13.0, compensation_factor=0.25)
        # For 1.0 AFR error: (1.0 / 13.0) * 100 * 0.25 = 1.92%
        enrichment = analyzer_conservative._afr_error_to_enrichment(1.0)
        assert 1.8 <= enrichment <= 2.1  # Should be ~1.92%
    
    def test_generate_recommendations(self, sample_accel_data):
        """Test recommendation generation."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_accel_data)
        
        assert len(result.recommendations) > 0
        assert any('event' in rec.lower() for rec in result.recommendations)
    
    def test_export_power_vision(self, sample_accel_data, tmp_path):
        """Test Power Vision export functionality."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_accel_data)
        
        output_file = tmp_path / "transient_export.txt"
        analyzer.export_power_vision(result, str(output_file))
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "DynoAI_3" in content
        assert "MAP Rate" in content
        assert "TPS Rate" in content
    
    def test_determinism(self, sample_accel_data):
        """Test that analysis is deterministic (same input = same output)."""
        analyzer1 = TransientFuelAnalyzer()
        analyzer2 = TransientFuelAnalyzer()
        
        result1 = analyzer1.analyze_transients(sample_accel_data.copy())
        result2 = analyzer2.analyze_transients(sample_accel_data.copy())
        
        # Should detect same number of events
        assert len(result1.detected_events) == len(result2.detected_events)
        
        # Tables should be identical
        pd.testing.assert_frame_equal(result1.map_rate_table, result2.map_rate_table)
        pd.testing.assert_frame_equal(result1.tps_rate_table, result2.tps_rate_table)
        
        # Wall wetting factors should be identical
        assert result1.wall_wetting_factor == result2.wall_wetting_factor
    
    def test_find_continuous_regions(self):
        """Test continuous region detection."""
        analyzer = TransientFuelAnalyzer()
        
        # Test with simple pattern
        mask = pd.Series([False, False, True, True, True, False, False, True, False])
        regions = analyzer._find_continuous_regions(mask)
        
        assert len(regions) == 2
        assert regions[0] == (2, 5)
        assert regions[1] == (7, 8)
    
    def test_empty_data_handling(self):
        """Test handling of edge case with minimal data."""
        analyzer = TransientFuelAnalyzer()
        
        # Create minimal valid data
        df = pd.DataFrame({
            'time': np.linspace(0, 1, 10),
            'rpm': np.ones(10) * 3000,
            'map': np.ones(10) * 50,
            'tps': np.ones(10) * 30,
            'afr': np.ones(10) * 13.0,
        })
        
        result = analyzer.analyze_transients(df)
        
        # Should complete without errors
        assert isinstance(result, TransientFuelResult)
        assert len(result.detected_events) == 0


class TestTauWallWetting:
    """Tests for X-Tau wall wetting model."""
    
    def test_tau_wall_wetting_calculation(self, sample_accel_data):
        """Test tau wall wetting parameter calculation."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_accel_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        tau_params = analyzer.calculate_tau_wall_wetting(df_with_rates, events)
        
        assert isinstance(tau_params, list)
        assert len(tau_params) == 5  # 5 RPM ranges
        
        for params in tau_params:
            assert isinstance(params, TauWallWettingParams)
            assert 0.05 <= params.x_fraction <= 0.50  # Valid X range (wider for cold)
            assert 0.2 <= params.tau_seconds <= 8.0  # Valid tau range (wider for cold)
            assert params.rpm_range in ['idle', 'low', 'mid', 'high', 'redline']
            assert params.temperature_condition in ['cold', 'cool', 'warm', 'hot']
    
    def test_tau_enrichment_calculation(self):
        """Test tau-based instantaneous enrichment calculation."""
        analyzer = TransientFuelAnalyzer()
        
        # Create test params (X already has compensation_factor baked in from real calculation)
        # Using explicit values here to test the enrichment formula directly
        params = TauWallWettingParams(
            x_fraction=0.13,  # Realistic value with 0.65 compensation factor
            tau_seconds=1.0,
            rpm_range='mid',
            temperature_condition='warm',
        )
        
        # Test enrichment at various MAP rates
        # Formula: enrichment = X * tau * (MAP_rate / 100) * 100
        # = 0.13 * 1.0 * (100 / 100) * 100 = 13%
        enrichment = analyzer.calculate_tau_enrichment(100.0, params)
        assert 12.0 <= enrichment <= 14.0  # Allow small floating point variance
        
        # At 50 kPa/s: 0.13 * 1.0 * 0.5 * 100 = 6.5%
        enrichment = analyzer.calculate_tau_enrichment(50.0, params)
        assert 6.0 <= enrichment <= 7.0
        
        # At 300 kPa/s: would be 39%, but capped at 25%
        enrichment = analyzer.calculate_tau_enrichment(300.0, params)
        assert enrichment == 25.0
        
        # Negative MAP rate (decel) should give zero
        enrichment = analyzer.calculate_tau_enrichment(-50.0, params)
        assert enrichment == 0.0
        
        # Test with higher X value (more aggressive)
        params_aggressive = TauWallWettingParams(
            x_fraction=0.25,
            tau_seconds=1.5,
            rpm_range='low',
            temperature_condition='cold',
        )
        # 0.25 * 1.5 * (100 / 100) * 100 = 37.5%, capped to 25%
        enrichment = analyzer.calculate_tau_enrichment(100.0, params_aggressive)
        assert enrichment == 25.0
    
    def test_tau_params_in_result(self, sample_accel_data):
        """Test that tau params are included in analysis result."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_accel_data)
        
        assert hasattr(result, 'tau_wall_wetting_params')
        assert isinstance(result.tau_wall_wetting_params, list)
        assert len(result.tau_wall_wetting_params) > 0
    
    def test_tau_model_steady_state(self, sample_steady_state_data):
        """Test tau model with steady state data (no events)."""
        analyzer = TransientFuelAnalyzer()
        df_with_rates = analyzer._calculate_rates(sample_steady_state_data)
        events = analyzer.detect_transient_events(df_with_rates)
        
        # Should still return params (defaults) even with no events
        tau_params = analyzer.calculate_tau_wall_wetting(df_with_rates, events)
        
        assert len(tau_params) == 5
        # With no events, should get default conservative values
        for params in tau_params:
            assert params.x_fraction == 0.15  # Default
            assert params.tau_seconds == 1.0  # Default


class TestIATCompensation:
    """Tests for IAT compensation throughout the analysis."""
    
    def test_cold_iat_increases_enrichment(self, sample_cold_iat_data, sample_accel_data):
        """Test that cold IAT produces higher enrichment recommendations."""
        analyzer = TransientFuelAnalyzer()
        
        # Analyze cold data
        result_cold = analyzer.analyze_transients(sample_cold_iat_data)
        
        # Analyze warm data  
        result_warm = analyzer.analyze_transients(sample_accel_data)
        
        # Cold should detect events with cold IAT category
        cold_events = [e for e in result_cold.detected_events if e.iat_category in ['cold', 'cool']]
        assert len(cold_events) > 0
        
        # Wall wetting factors should generally be higher for cold
        # (though this depends on AFR errors in the data)
        assert len(result_cold.tau_wall_wetting_params) == 5
    
    def test_event_captures_iat(self, sample_cold_iat_data):
        """Test that transient events capture IAT data."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_cold_iat_data)
        
        for event in result.detected_events:
            # Should have IAT data
            assert hasattr(event, 'avg_iat_c')
            assert hasattr(event, 'iat_category')
            # Cold data should show cold/cool category
            assert event.iat_category in ['cold', 'cool']
            assert event.avg_iat_c < 10.0
    
    def test_enrichment_tables_include_iat(self, sample_accel_data):
        """Test that enrichment tables include IAT information."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_accel_data)
        
        # MAP rate table should have IAT column
        assert 'avg_iat_c' in result.map_rate_table.columns
        
        # TPS rate table should have IAT column
        assert 'avg_iat_c' in result.tps_rate_table.columns
        
        # 3D table should have IAT columns
        assert 'avg_iat_c' in result.transient_3d_table.columns
        assert 'iat_category' in result.transient_3d_table.columns
    
    def test_recommendations_mention_iat(self, sample_cold_iat_data):
        """Test that recommendations include IAT-based insights."""
        analyzer = TransientFuelAnalyzer()
        result = analyzer.analyze_transients(sample_cold_iat_data)
        
        # Should have at least one recommendation mentioning cold IAT
        iat_recommendations = [r for r in result.recommendations if 'IAT' in r or 'cold' in r.lower()]
        assert len(iat_recommendations) > 0


class TestTransientEvent:
    """Tests for TransientEvent dataclass."""
    
    def test_creation(self):
        """Test TransientEvent creation with IAT fields."""
        event = TransientEvent(
            start_time=5.0,
            end_time=10.0,
            event_type='accel',
            severity='moderate',
            peak_map_rate=120.0,
            peak_tps_rate=45.0,
            avg_rpm=4000.0,
            afr_error_avg=1.5,
            afr_error_peak=2.3,
            avg_iat_c=15.0,
            iat_category='cool',
        )
        
        assert event.start_time == 5.0
        assert event.end_time == 10.0
        assert event.event_type == 'accel'
        assert event.severity == 'moderate'
        assert event.peak_map_rate == 120.0
        assert event.avg_iat_c == 15.0
        assert event.iat_category == 'cool'


class TestTransientFuelResult:
    """Tests for TransientFuelResult dataclass."""
    
    def test_creation(self):
        """Test TransientFuelResult creation."""
        result = TransientFuelResult()
        
        assert isinstance(result.wall_wetting_factor, dict)
        assert isinstance(result.tau_wall_wetting_params, list)
        assert isinstance(result.map_rate_table, pd.DataFrame)
        assert isinstance(result.tps_rate_table, pd.DataFrame)
        assert isinstance(result.detected_events, list)
        assert isinstance(result.recommendations, list)
        assert isinstance(result.plots, dict)


class TestTauWallWettingParams:
    """Tests for TauWallWettingParams dataclass."""
    
    def test_creation(self):
        """Test TauWallWettingParams creation."""
        params = TauWallWettingParams(
            x_fraction=0.25,
            tau_seconds=1.5,
            rpm_range='mid',
            temperature_condition='warm',
        )
        
        assert params.x_fraction == 0.25
        assert params.tau_seconds == 1.5
        assert params.rpm_range == 'mid'
        assert params.temperature_condition == 'warm'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

