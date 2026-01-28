"""
Tests for dynoai.core.log_normalizer module.

Tests verify:
- Column alias detection
- Graceful degradation for missing columns
- Confidence factor computation
"""

import pytest
import pandas as pd

from dynoai.core.log_normalizer import (
    normalize_dataframe,
    detect_columns,
    NormalizationResult,
    ChannelPresence,
    CANONICAL_COLUMNS,
)


class TestColumnAliasDetection:
    """Tests for column alias detection."""
    
    def test_detects_canonical_names(self):
        """Detects columns when using canonical names."""
        df = pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
            "tps": [40, 50, 60],
        })
        
        found = detect_columns(df)
        
        assert "rpm" in found
        assert "map_kpa" in found
        assert "tps" in found
    
    def test_detects_aliases(self):
        """Detects columns when using alias names."""
        df = pd.DataFrame({
            "engine_rpm": [3000, 3500, 4000],  # Alias for rpm
            "manifold_pressure": [60, 70, 80],  # Alias for map_kpa
            "throttle_position": [40, 50, 60],  # Alias for tps
        })
        
        found = detect_columns(df)
        
        assert "rpm" in found
        assert "map_kpa" in found
        assert "tps" in found
    
    def test_case_insensitive_detection(self):
        """Column detection is case-insensitive."""
        df = pd.DataFrame({
            "RPM": [3000, 3500, 4000],
            "MAP_KPA": [60, 70, 80],
            "TPS": [40, 50, 60],
        })
        
        found = detect_columns(df)
        
        assert "rpm" in found
        assert "map_kpa" in found
        assert "tps" in found


class TestNormalizationResult:
    """Tests for normalize_dataframe result."""
    
    @pytest.fixture
    def minimal_df(self):
        """Create DataFrame with minimal required columns."""
        return pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
        })
    
    @pytest.fixture
    def full_df(self):
        """Create DataFrame with all expected columns."""
        return pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
            "tps": [40, 50, 60],
            "iat": [90, 92, 94],
            "afr_meas_f": [13.0, 13.1, 13.2],
            "afr_meas_r": [13.0, 13.1, 13.2],
            "afr_cmd_f": [12.8, 12.8, 12.8],
            "afr_cmd_r": [12.8, 12.8, 12.8],
            "spark_f": [28, 27, 26],
            "spark_r": [27, 26, 25],
            "knock": [0, 0, 1],
        })
    
    def test_returns_normalization_result(self, minimal_df):
        """normalize_dataframe returns NormalizationResult."""
        result = normalize_dataframe(minimal_df)
        
        assert isinstance(result, NormalizationResult)
        assert hasattr(result, "df")
        assert hasattr(result, "columns_found")
        assert hasattr(result, "columns_missing")
        assert hasattr(result, "presence")
    
    def test_renames_columns_to_canonical(self):
        """Columns are renamed to canonical names."""
        df = pd.DataFrame({
            "engine_rpm": [3000, 3500, 4000],
            "manifold_pressure": [60, 70, 80],
        })
        
        result = normalize_dataframe(df)
        
        assert "rpm" in result.df.columns
        assert "map_kpa" in result.df.columns
        assert "engine_rpm" not in result.df.columns
    
    def test_tracks_found_columns(self, minimal_df):
        """Found columns are tracked in result."""
        result = normalize_dataframe(minimal_df)
        
        assert "rpm" in result.columns_found
        assert "map_kpa" in result.columns_found
    
    def test_tracks_missing_columns(self, minimal_df):
        """Missing columns are tracked in result."""
        result = normalize_dataframe(minimal_df)
        
        # TPS is optional but commonly expected
        assert any("tps" in col for col in result.columns_missing)


class TestGracefulDegradation:
    """Tests for graceful degradation when columns are missing."""
    
    def test_global_afr_used_when_per_cylinder_missing(self):
        """Global AFR used when per-cylinder AFR missing."""
        df = pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
            "afr_meas": [13.0, 13.1, 13.2],  # Global only
            "afr_cmd": [12.8, 12.8, 12.8],
        })
        
        result = normalize_dataframe(df)
        
        # Should create synthetic per-cylinder columns
        assert "afr_meas_f" in result.df.columns
        assert "afr_meas_r" in result.df.columns
        assert "afr_meas_f" in result.columns_derived
    
    def test_stoich_default_when_afr_cmd_missing(self):
        """Stoichiometric (14.7) used when commanded AFR missing."""
        df = pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
            "afr_meas_f": [13.0, 13.1, 13.2],
            "afr_meas_r": [13.0, 13.1, 13.2],
            # No afr_cmd columns
        })
        
        result = normalize_dataframe(df)
        
        # Should use stoich default
        assert "afr_cmd_f" in result.df.columns
        assert result.df["afr_cmd_f"].iloc[0] == 14.7
        assert any("stoich" in w.lower() or "14.7" in w for w in result.warnings)
    
    def test_afr_error_computed(self):
        """AFR error columns are computed from measured - commanded."""
        df = pd.DataFrame({
            "rpm": [3000, 3500, 4000],
            "map_kpa": [60, 70, 80],
            "afr_meas_f": [13.5, 13.6, 13.7],
            "afr_meas_r": [13.4, 13.5, 13.6],
            "afr_cmd_f": [13.0, 13.0, 13.0],
            "afr_cmd_r": [13.0, 13.0, 13.0],
        })
        
        result = normalize_dataframe(df)
        
        assert "afr_error_f" in result.df.columns
        assert "afr_error_r" in result.df.columns
        # First row: 13.5 - 13.0 = 0.5
        assert abs(result.df["afr_error_f"].iloc[0] - 0.5) < 0.01


class TestChannelPresence:
    """Tests for channel presence detection."""
    
    def test_has_required_true_when_present(self):
        """has_required is True when rpm and map_kpa present."""
        df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
        })
        
        result = normalize_dataframe(df)
        
        assert result.presence.has_required is True
    
    def test_has_required_false_when_missing(self):
        """has_required is False when rpm or map_kpa missing."""
        df = pd.DataFrame({
            "rpm": [3000],
            # map_kpa missing
        })
        
        result = normalize_dataframe(df)
        
        assert result.presence.has_required is False
    
    def test_has_per_cylinder_afr_detected(self):
        """Per-cylinder AFR detection works."""
        df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
            "afr_meas_f": [13.0],
            "afr_meas_r": [13.0],
        })
        
        result = normalize_dataframe(df)
        
        assert result.presence.has_per_cylinder_afr is True
    
    def test_has_knock_detected(self):
        """Knock channel detection works."""
        df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
            "knock": [0],
        })
        
        result = normalize_dataframe(df)
        
        assert result.presence.has_knock is True


class TestConfidenceFactor:
    """Tests for confidence factor computation."""
    
    def test_confidence_factor_zero_without_required(self):
        """Confidence is 0 when required columns missing."""
        df = pd.DataFrame({
            "rpm": [3000],
            # map_kpa missing
        })
        
        result = normalize_dataframe(df)
        
        assert result.confidence_factor == 0.0
    
    def test_confidence_factor_increases_with_channels(self):
        """Confidence increases with more available channels."""
        minimal_df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
        })
        
        full_df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
            "tps": [40],
            "iat": [90],
            "afr_meas_f": [13.0],
            "afr_meas_r": [13.0],
            "spark_f": [28],
            "spark_r": [27],
            "knock": [0],
        })
        
        minimal_result = normalize_dataframe(minimal_df)
        full_result = normalize_dataframe(full_df)
        
        assert full_result.confidence_factor > minimal_result.confidence_factor
    
    def test_confidence_factor_max_one(self):
        """Confidence factor is capped at 1.0."""
        df = pd.DataFrame({
            "rpm": [3000],
            "map_kpa": [60],
            "tps": [40],
            "iat": [90],
            "afr_meas_f": [13.0],
            "afr_meas_r": [13.0],
            "spark_f": [28],
            "spark_r": [27],
            "knock": [0],
            "ect": [180],
            "vbatt": [13.8],
        })
        
        result = normalize_dataframe(df)
        
        assert result.confidence_factor <= 1.0
