"""
Tests for dynoai.core.mode_detection module.

Tests verify:
- Mode tag assignment is deterministic
- Threshold-based classification works correctly
- Mode summary counts are accurate
"""

import pytest
import pandas as pd
import numpy as np

from dynoai.core.mode_detection import (
    ModeTag,
    ModeDetectionConfig,
    ModeLabeledFrame,
    label_modes,
    compute_derivatives,
    get_steady_state_mask,
    get_wot_mask,
    get_transient_mask,
)


class TestModeTagEnum:
    """Tests for ModeTag enumeration."""
    
    def test_all_modes_defined(self):
        """All expected modes are defined."""
        expected_modes = ["idle", "cruise", "tip_in", "tip_out", "wot", "decel", "heat_soak", "unknown"]
        
        for mode in expected_modes:
            assert hasattr(ModeTag, mode.upper())
    
    def test_mode_values_are_lowercase(self):
        """Mode values are lowercase strings."""
        for mode in ModeTag:
            assert mode.value == mode.value.lower()
    
    def test_mode_string_conversion(self):
        """ModeTag converts to string correctly."""
        assert str(ModeTag.IDLE) == "idle"
        assert str(ModeTag.WOT) == "wot"


class TestModeDetection:
    """Tests for mode detection classification."""
    
    @pytest.fixture
    def idle_df(self):
        """Create DataFrame with idle conditions."""
        return pd.DataFrame({
            "rpm": [1000, 1050, 1000, 1025, 1000],
            "map_kpa": [35, 36, 35, 34, 35],
            "tps": [2, 3, 2, 3, 2],
            "iat": [90, 91, 90, 91, 90],
        })
    
    @pytest.fixture
    def wot_df(self):
        """Create DataFrame with WOT conditions."""
        return pd.DataFrame({
            "rpm": [5000, 5200, 5400, 5600, 5800],
            "map_kpa": [95, 96, 97, 98, 99],
            "tps": [95, 96, 97, 98, 99],
            "iat": [100, 102, 104, 106, 108],
        })
    
    @pytest.fixture
    def cruise_df(self):
        """Create DataFrame with cruise conditions."""
        return pd.DataFrame({
            "rpm": [3000, 3010, 3005, 3015, 3000],
            "map_kpa": [50, 51, 50, 52, 50],
            "tps": [30, 31, 30, 32, 30],
            "iat": [85, 85, 85, 85, 85],
        })
    
    def test_detects_idle(self, idle_df):
        """Idle conditions are labeled as IDLE."""
        result = label_modes(idle_df)
        
        idle_count = (result.df["mode"] == "idle").sum()
        assert idle_count > 0
    
    def test_detects_wot(self, wot_df):
        """WOT conditions are labeled as WOT."""
        result = label_modes(wot_df)
        
        wot_count = (result.df["mode"] == "wot").sum()
        assert wot_count > 0
    
    def test_detects_cruise(self, cruise_df):
        """Cruise conditions are labeled as CRUISE."""
        result = label_modes(cruise_df)
        
        cruise_count = (result.df["mode"] == "cruise").sum()
        assert cruise_count > 0
    
    def test_deterministic_classification(self, cruise_df):
        """Mode classification is deterministic."""
        result1 = label_modes(cruise_df)
        result2 = label_modes(cruise_df)
        
        assert (result1.df["mode"] == result2.df["mode"]).all()


class TestTransientDetection:
    """Tests for transient (tip-in/tip-out) detection."""
    
    @pytest.fixture
    def tipin_df(self):
        """Create DataFrame with tip-in event."""
        # TPS jumps from 20 to 80 over 5 samples
        return pd.DataFrame({
            "rpm": [3000, 3100, 3200, 3300, 3400],
            "map_kpa": [50, 60, 70, 80, 85],
            "tps": [20, 35, 50, 65, 80],
            "iat": [85, 85, 85, 85, 85],
            "time_ms": [0, 100, 200, 300, 400],  # 100ms intervals
        })
    
    @pytest.fixture
    def tipout_df(self):
        """Create DataFrame with tip-out event."""
        # TPS drops from 80 to 20 over 5 samples
        return pd.DataFrame({
            "rpm": [4000, 3900, 3800, 3700, 3600],
            "map_kpa": [80, 70, 60, 50, 45],
            "tps": [80, 65, 50, 35, 20],
            "iat": [90, 90, 90, 90, 90],
            "time_ms": [0, 100, 200, 300, 400],
        })
    
    def test_detects_tip_in(self, tipin_df):
        """Tip-in events are detected."""
        result = label_modes(tipin_df)
        
        tipin_count = (result.df["mode"] == "tip_in").sum()
        # Should detect at least some tip-in samples
        assert tipin_count >= 1
    
    def test_detects_tip_out(self, tipout_df):
        """Tip-out events are detected."""
        result = label_modes(tipout_df)
        
        tipout_count = (result.df["mode"] == "tip_out").sum()
        # Should detect at least some tip-out samples
        assert tipout_count >= 1


class TestHeatSoakDetection:
    """Tests for heat soak condition detection."""
    
    @pytest.fixture
    def heatsoak_df(self):
        """Create DataFrame with heat soak conditions."""
        return pd.DataFrame({
            "rpm": [1500, 1600, 1550, 1500, 1550],
            "map_kpa": [40, 42, 41, 40, 41],
            "tps": [5, 6, 5, 5, 6],
            "iat": [140, 145, 150, 155, 160],  # High IAT
        })
    
    def test_detects_heat_soak(self, heatsoak_df):
        """Heat soak conditions are labeled as HEAT_SOAK."""
        config = ModeDetectionConfig(iat_soak_threshold=130.0)
        result = label_modes(heatsoak_df, config)
        
        heat_soak_count = (result.df["mode"] == "heat_soak").sum()
        assert heat_soak_count > 0


class TestModeLabeledFrame:
    """Tests for ModeLabeledFrame result object."""
    
    @pytest.fixture
    def mixed_df(self):
        """Create DataFrame with mixed conditions."""
        np.random.seed(42)
        n = 50
        
        df = pd.DataFrame({
            "rpm": np.concatenate([
                np.full(10, 1000),  # Idle
                np.linspace(2000, 3000, 10),  # Transition
                np.full(20, 3500),  # Cruise
                np.full(10, 5500),  # WOT
            ]),
            "map_kpa": np.concatenate([
                np.full(10, 35),  # Idle MAP
                np.linspace(40, 60, 10),  # Transition
                np.full(20, 55),  # Cruise MAP
                np.full(10, 95),  # WOT MAP
            ]),
            "tps": np.concatenate([
                np.full(10, 3),  # Idle TPS
                np.linspace(10, 40, 10),  # Transition
                np.full(20, 35),  # Cruise TPS
                np.full(10, 95),  # WOT TPS
            ]),
            "iat": np.full(n, 85),
        })
        return df
    
    def test_summary_counts_accurate(self, mixed_df):
        """Summary counts reflect actual mode distribution."""
        result = label_modes(mixed_df)
        
        total_from_summary = sum(result.summary_counts.values())
        total_rows = len(mixed_df)
        
        assert total_from_summary == total_rows
    
    def test_total_samples_property(self, mixed_df):
        """total_samples property returns correct count."""
        result = label_modes(mixed_df)
        
        assert result.total_samples == len(mixed_df)
    
    def test_mode_distribution_sums_to_100(self, mixed_df):
        """Mode distribution percentages sum to ~100%."""
        result = label_modes(mixed_df)
        
        total_pct = sum(result.mode_distribution.values())
        assert abs(total_pct - 100.0) < 0.1
    
    def test_get_mode_mask_returns_boolean_series(self, mixed_df):
        """get_mode_mask returns boolean Series."""
        result = label_modes(mixed_df)
        
        mask = result.get_mode_mask(ModeTag.CRUISE)
        
        assert isinstance(mask, pd.Series)
        assert mask.dtype == bool
    
    def test_filter_by_mode_returns_subset(self, mixed_df):
        """filter_by_mode returns filtered DataFrame."""
        result = label_modes(mixed_df)
        
        cruise_df = result.filter_by_mode(ModeTag.CRUISE)
        
        assert len(cruise_df) <= len(mixed_df)
        assert (cruise_df["mode"] == "cruise").all()


class TestMaskHelpers:
    """Tests for mask helper functions."""
    
    @pytest.fixture
    def labeled_df(self):
        """Create pre-labeled DataFrame."""
        return pd.DataFrame({
            "rpm": [1000, 3000, 5000, 3500, 3600],
            "map_kpa": [35, 55, 95, 60, 55],
            "tps": [3, 35, 95, 50, 40],
            "iat": [85, 85, 85, 85, 85],
            "mode": ["idle", "cruise", "wot", "tip_in", "tip_out"],
        })
    
    def test_steady_state_mask_excludes_transients(self, labeled_df):
        """Steady state mask excludes tip_in and tip_out."""
        mask = get_steady_state_mask(labeled_df)
        
        # tip_in and tip_out should be False
        assert not mask.iloc[3]  # tip_in
        assert not mask.iloc[4]  # tip_out
        
        # Others should be True (idle, cruise, wot)
        assert mask.iloc[0]  # idle
        assert mask.iloc[1]  # cruise
        assert mask.iloc[2]  # wot
    
    def test_wot_mask_selects_wot_only(self, labeled_df):
        """WOT mask only selects WOT samples."""
        mask = get_wot_mask(labeled_df)
        
        assert mask.iloc[2]  # wot
        assert not mask.iloc[0]  # idle
        assert not mask.iloc[1]  # cruise
    
    def test_transient_mask_selects_tip_events(self, labeled_df):
        """Transient mask selects tip_in and tip_out."""
        mask = get_transient_mask(labeled_df)
        
        assert mask.iloc[3]  # tip_in
        assert mask.iloc[4]  # tip_out
        assert not mask.iloc[0]  # idle
        assert not mask.iloc[1]  # cruise


class TestDerivativeComputation:
    """Tests for TPS/MAP derivative computation."""
    
    def test_computes_tps_dot(self):
        """TPS derivative is computed correctly."""
        df = pd.DataFrame({
            "rpm": [3000, 3000, 3000, 3000, 3000],
            "map_kpa": [50, 50, 50, 50, 50],
            "tps": [20, 30, 40, 50, 60],  # 10%/sample increase
            "time_ms": [0, 100, 200, 300, 400],  # 100ms intervals = 100%/s rate
        })
        
        config = ModeDetectionConfig()
        result_df = compute_derivatives(df, config)
        
        assert "tps_dot" in result_df.columns
        # Rate should be positive (increasing TPS)
        assert result_df["tps_dot"].iloc[-1] > 0
    
    def test_computes_map_dot(self):
        """MAP derivative is computed correctly."""
        df = pd.DataFrame({
            "rpm": [3000, 3000, 3000, 3000, 3000],
            "map_kpa": [50, 55, 60, 65, 70],  # 5 kPa/sample increase
            "tps": [40, 40, 40, 40, 40],
            "time_ms": [0, 100, 200, 300, 400],
        })
        
        config = ModeDetectionConfig()
        result_df = compute_derivatives(df, config)
        
        assert "map_dot" in result_df.columns
        # Rate should be positive (increasing MAP)
        assert result_df["map_dot"].iloc[-1] > 0
    
    def test_handles_missing_time_column(self):
        """Derivatives computed using default sample rate when time missing."""
        df = pd.DataFrame({
            "rpm": [3000, 3000, 3000],
            "map_kpa": [50, 60, 70],
            "tps": [30, 40, 50],
            # No time_ms column
        })
        
        config = ModeDetectionConfig(default_sample_rate_hz=100.0)
        result_df = compute_derivatives(df, config)
        
        assert "tps_dot" in result_df.columns
        assert "map_dot" in result_df.columns


class TestCustomConfig:
    """Tests for custom ModeDetectionConfig."""
    
    def test_custom_wot_threshold(self):
        """Custom WOT threshold is respected."""
        df = pd.DataFrame({
            "rpm": [5000, 5000, 5000],
            "map_kpa": [80, 80, 80],
            "tps": [75, 80, 85],  # Near threshold
            "iat": [85, 85, 85],
        })
        
        # With default 85% threshold, only last sample is WOT
        default_config = ModeDetectionConfig(tps_wot_threshold=85.0)
        result1 = label_modes(df, default_config)
        
        # With lower 70% threshold, more samples are WOT
        custom_config = ModeDetectionConfig(tps_wot_threshold=70.0)
        result2 = label_modes(df, custom_config)
        
        wot_count1 = (result1.df["mode"] == "wot").sum()
        wot_count2 = (result2.df["mode"] == "wot").sum()
        
        assert wot_count2 >= wot_count1
    
    def test_custom_idle_threshold(self):
        """Custom idle thresholds are respected."""
        df = pd.DataFrame({
            "rpm": [1100, 1100, 1100],
            "map_kpa": [40, 40, 40],
            "tps": [4, 4, 4],
            "iat": [85, 85, 85],
        })
        
        # With default 1200 RPM ceiling, these are idle
        default_config = ModeDetectionConfig(rpm_idle_ceiling=1200.0)
        result1 = label_modes(df, default_config)
        
        # With lower 1000 RPM ceiling, these are not idle
        custom_config = ModeDetectionConfig(rpm_idle_ceiling=1000.0)
        result2 = label_modes(df, custom_config)
        
        idle_count1 = (result1.df["mode"] == "idle").sum()
        idle_count2 = (result2.df["mode"] == "idle").sum()
        
        assert idle_count1 > idle_count2
