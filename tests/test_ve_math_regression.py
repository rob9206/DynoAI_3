"""
VE Math v2.0.0 Regression Test Suite

This test suite validates the integration of the v2.0.0 ratio model
across all DynoAI components to ensure consistent behavior.

Tests:
1. Component Integration - All components use same calculation
2. Version Consistency - v1.0.0 and v2.0.0 produce expected results
3. Cross-Component Agreement - Different code paths give same results
4. Golden File Comparison - Results match known-good outputs
5. Boundary Conditions - Edge cases handled correctly
6. Performance - No regression in calculation speed

Run with: pytest tests/test_ve_math_regression.py -v
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Core VE math module
from dynoai.core.ve_math import (
    AFR_MAX,
    AFR_MIN,
    MathConfig,
    MathVersion,
    calculate_ve_correction,
    calculate_ve_correction_batch,
    compare_versions,
    correction_to_percentage,
    get_default_config,
)


# =============================================================================
# Test Fixtures - Golden Values
# =============================================================================

@pytest.fixture
def golden_test_cases() -> List[Dict]:
    """
    Golden test cases with known-good expected values.
    
    These values were calculated manually and verified to be correct
    for both v1.0.0 and v2.0.0 formulas.
    """
    return [
        # Format: {measured, target, v1_expected, v2_expected, scenario}
        {"measured": 13.0, "target": 13.0, "v1": 1.0, "v2": 1.0, "scenario": "On target"},
        {"measured": 14.0, "target": 13.0, "v1": 1.07, "v2": 14.0/13.0, "scenario": "1 AFR lean"},
        {"measured": 15.0, "target": 13.0, "v1": 1.14, "v2": 15.0/13.0, "scenario": "2 AFR lean"},
        {"measured": 16.0, "target": 13.0, "v1": 1.21, "v2": 16.0/13.0, "scenario": "3 AFR lean"},
        {"measured": 12.0, "target": 13.0, "v1": 0.93, "v2": 12.0/13.0, "scenario": "1 AFR rich"},
        {"measured": 11.0, "target": 13.0, "v1": 0.86, "v2": 11.0/13.0, "scenario": "2 AFR rich"},
        {"measured": 10.0, "target": 13.0, "v1": 0.79, "v2": 10.0/13.0, "scenario": "3 AFR rich"},
        # Different targets
        {"measured": 14.7, "target": 14.7, "v1": 1.0, "v2": 1.0, "scenario": "Stoich"},
        {"measured": 13.0, "target": 12.5, "v1": 1.035, "v2": 13.0/12.5, "scenario": "WOT lean"},
        {"measured": 12.0, "target": 12.5, "v1": 0.965, "v2": 12.0/12.5, "scenario": "WOT rich"},
    ]


@pytest.fixture
def sample_dyno_data() -> pd.DataFrame:
    """Sample dyno run data for integration testing."""
    np.random.seed(42)  # Reproducible
    
    data = []
    for rpm in range(2000, 6500, 500):
        for _ in range(10):  # 10 samples per RPM
            afr = 13.0 + np.random.normal(0, 0.5)  # Normal around 13.0
            map_kpa = 50 + (rpm - 2000) / 100  # MAP increases with RPM
            data.append({
                "RPM": rpm + np.random.uniform(-50, 50),
                "AFR": afr,
                "MAP_kPa": map_kpa + np.random.uniform(-5, 5),
            })
    
    return pd.DataFrame(data)


# =============================================================================
# Test 1: Golden Value Regression
# =============================================================================

class TestGoldenValues:
    """Validate calculations against known-good golden values."""
    
    def test_v1_golden_values(self, golden_test_cases):
        """v1.0.0 should match golden values exactly."""
        for case in golden_test_cases:
            result = calculate_ve_correction(
                case["measured"],
                case["target"],
                version=MathVersion.V1_0_0,
                clamp=False
            )
            expected = case["v1"]
            assert abs(result - expected) < 0.0001, \
                f"v1.0.0 failed for {case['scenario']}: expected {expected}, got {result}"
    
    def test_v2_golden_values(self, golden_test_cases):
        """v2.0.0 should match golden values exactly."""
        for case in golden_test_cases:
            result = calculate_ve_correction(
                case["measured"],
                case["target"],
                version=MathVersion.V2_0_0,
                clamp=False
            )
            expected = case["v2"]
            assert abs(result - expected) < 1e-10, \
                f"v2.0.0 failed for {case['scenario']}: expected {expected}, got {result}"
    
    def test_ratio_formula_exact(self, golden_test_cases):
        """v2.0.0 must equal measured/target exactly."""
        for case in golden_test_cases:
            result = calculate_ve_correction(
                case["measured"],
                case["target"],
                version=MathVersion.V2_0_0,
                clamp=False
            )
            expected = case["measured"] / case["target"]
            
            # Must be bit-exact
            assert result == expected, \
                f"Ratio formula not exact for {case['scenario']}"


# =============================================================================
# Test 2: Version Consistency
# =============================================================================

class TestVersionConsistency:
    """Ensure version behavior is consistent and documented."""
    
    def test_default_version_is_v2(self):
        """Default math version should be v2.0.0."""
        config = get_default_config()
        assert config.version == MathVersion.V2_0_0
    
    def test_version_override_works(self):
        """Version parameter should override config."""
        config = MathConfig(version=MathVersion.V1_0_0)
        
        # Use v2 despite v1 config
        result = calculate_ve_correction(
            14.0, 13.0, version=MathVersion.V2_0_0, config=config
        )
        
        # Should be v2 result (ratio), not v1 (linear)
        assert abs(result - 14.0/13.0) < 1e-10
    
    def test_versions_differ_at_large_errors(self):
        """v1 and v2 should diverge at large AFR errors."""
        # At 3 AFR point deviation
        v1 = calculate_ve_correction(16.0, 13.0, MathVersion.V1_0_0, clamp=False)
        v2 = calculate_ve_correction(16.0, 13.0, MathVersion.V2_0_0, clamp=False)
        
        # v1 = 1.21, v2 = 1.2308
        # Difference should be > 1%
        diff_pct = abs(v2 - v1) / v2 * 100
        assert diff_pct > 1.0, f"Versions should differ by >1% at 3 AFR points, got {diff_pct:.2f}%"
    
    def test_versions_similar_at_small_errors(self):
        """v1 and v2 should be similar at small AFR errors."""
        # At 0.5 AFR point deviation
        v1 = calculate_ve_correction(13.5, 13.0, MathVersion.V1_0_0, clamp=False)
        v2 = calculate_ve_correction(13.5, 13.0, MathVersion.V2_0_0, clamp=False)
        
        # Difference should be < 0.5%
        diff_pct = abs(v2 - v1) / v2 * 100
        assert diff_pct < 0.5, f"Versions should be within 0.5% at small errors, got {diff_pct:.2f}%"


# =============================================================================
# Test 3: Cross-Component Agreement
# =============================================================================

class TestCrossComponentAgreement:
    """Ensure all components calculate VE corrections identically."""
    
    def test_cylinder_balancing_uses_ve_math(self):
        """cylinder_balancing.py should use ve_math module."""
        from dynoai.core.cylinder_balancing import _calculate_ve_correction_decimal
        
        # Test with v2.0.0
        result = _calculate_ve_correction_decimal(14.0, 13.0, MathVersion.V2_0_0)
        expected = (14.0 / 13.0) - 1.0  # Returns decimal, not multiplier
        
        assert abs(result - expected) < 1e-10
    
    def test_jetdrive_autotune_config(self):
        """jetdrive_autotune.py should support math version config."""
        from scripts.jetdrive_autotune import TuneConfig
        
        config = TuneConfig()
        assert config.math_version == MathVersion.V2_0_0
        
        config_v1 = TuneConfig(math_version=MathVersion.V1_0_0)
        assert config_v1.math_version == MathVersion.V1_0_0
    
    def test_autotune_workflow_config(self):
        """autotune_workflow.py should support math version config."""
        from api.services.autotune_workflow import AutoTuneWorkflow
        
        workflow = AutoTuneWorkflow()
        assert workflow.math_version == MathVersion.V2_0_0
        
        workflow_v1 = AutoTuneWorkflow(math_version=MathVersion.V1_0_0)
        assert workflow_v1.math_version == MathVersion.V1_0_0


# =============================================================================
# Test 4: Determinism Regression
# =============================================================================

class TestDeterminismRegression:
    """Ensure determinism guarantees are maintained."""
    
    def test_same_inputs_same_outputs_v2(self):
        """v2.0.0 must be deterministic."""
        results = set()
        for _ in range(1000):
            r = calculate_ve_correction(14.123456, 13.654321, MathVersion.V2_0_0)
            results.add(r)
        
        assert len(results) == 1, "v2.0.0 not deterministic!"
    
    def test_batch_matches_individual(self):
        """Batch calculation must match individual calculations."""
        measured = [14.0, 13.5, 13.0, 12.5, 12.0]
        targets = [13.0, 13.0, 13.0, 13.0, 13.0]
        
        batch = calculate_ve_correction_batch(measured, targets)
        individual = [calculate_ve_correction(m, t) for m, t in zip(measured, targets)]
        
        for i, (b, ind) in enumerate(zip(batch, individual)):
            assert b == ind, f"Batch/individual mismatch at index {i}"
    
    def test_no_state_between_calls(self):
        """Each call should be independent."""
        # Call many times with different values
        for measured in np.linspace(10, 18, 100):
            calculate_ve_correction(measured, 13.0)
        
        # Final call should not be affected
        result = calculate_ve_correction(14.0, 13.0)
        expected = 14.0 / 13.0
        
        assert abs(result - expected) < 1e-10


# =============================================================================
# Test 5: Boundary Conditions
# =============================================================================

class TestBoundaryConditions:
    """Test edge cases and boundary conditions."""
    
    def test_minimum_afr_accepted(self):
        """Minimum valid AFR should be accepted."""
        result = calculate_ve_correction(AFR_MIN, 13.0, clamp=False)
        assert result is not None
        assert abs(result - AFR_MIN / 13.0) < 1e-10
    
    def test_maximum_afr_accepted(self):
        """Maximum valid AFR should be accepted."""
        result = calculate_ve_correction(AFR_MAX, 13.0, clamp=False)
        assert result is not None
        assert abs(result - AFR_MAX / 13.0) < 1e-10
    
    def test_clamping_works_lean(self):
        """Extreme lean should be clamped."""
        config = MathConfig(max_correction_pct=15.0)
        result = calculate_ve_correction(18.0, 12.0, config=config, clamp=True)
        
        # 18/12 = 1.5 (50%) should be clamped to 1.15 (15%)
        assert result <= 1.15 + 1e-10
    
    def test_clamping_works_rich(self):
        """Extreme rich should be clamped."""
        config = MathConfig(max_correction_pct=15.0)
        result = calculate_ve_correction(10.0, 14.0, config=config, clamp=True)
        
        # 10/14 = 0.714 (-28.6%) should be clamped to 0.85 (-15%)
        assert result >= 0.85 - 1e-10
    
    def test_equal_afr_gives_one(self):
        """Equal measured and target should give exactly 1.0."""
        for afr in [10.0, 12.0, 13.0, 14.0, 14.7, 16.0, 18.0]:
            result = calculate_ve_correction(afr, afr)
            assert result == 1.0, f"AFR {afr}/{afr} should give 1.0, got {result}"


# =============================================================================
# Test 6: Real-World Scenarios
# =============================================================================

class TestRealWorldScenarios:
    """Test scenarios that match real tuning situations."""
    
    def test_typical_wot_tuning(self):
        """Typical WOT tuning scenario."""
        # Target 12.5:1 at WOT, running 13.5:1 (lean)
        correction = calculate_ve_correction(13.5, 12.5)
        pct = correction_to_percentage(correction)
        
        # Should recommend ~8% more fuel
        assert 7.0 < pct < 9.0, f"WOT lean correction should be ~8%, got {pct:.1f}%"
    
    def test_typical_cruise_tuning(self):
        """Typical cruise tuning scenario."""
        # Target 14.7:1 at cruise, running 13.5:1 (rich)
        correction = calculate_ve_correction(13.5, 14.7)
        pct = correction_to_percentage(correction)
        
        # Should recommend ~8% less fuel
        assert -9.0 < pct < -7.0, f"Cruise rich correction should be ~-8%, got {pct:.1f}%"
    
    def test_fine_tuning_scenario(self):
        """Fine-tuning with small adjustments."""
        # Target 13.0, running 13.2 (slightly lean)
        correction = calculate_ve_correction(13.2, 13.0)
        pct = correction_to_percentage(correction)
        
        # Should recommend ~1.5% more fuel
        assert 1.0 < pct < 2.0, f"Fine-tune correction should be ~1.5%, got {pct:.1f}%"
    
    def test_cylinder_balance_scenario(self):
        """Per-cylinder balancing scenario."""
        # Front running 13.0, rear running 13.5 (0.5 AFR imbalance)
        avg_afr = (13.0 + 13.5) / 2  # 13.25
        
        front_correction = calculate_ve_correction(13.0, avg_afr)  # rich vs avg
        rear_correction = calculate_ve_correction(13.5, avg_afr)   # lean vs avg
        
        # Front needs less fuel (rich), rear needs more (lean)
        assert front_correction < 1.0
        assert rear_correction > 1.0
        
        # Corrections should be roughly equal magnitude
        front_pct = abs(correction_to_percentage(front_correction))
        rear_pct = abs(correction_to_percentage(rear_correction))
        assert abs(front_pct - rear_pct) < 0.5


# =============================================================================
# Test 7: Comparison Function
# =============================================================================

class TestCompareVersions:
    """Test the version comparison utility."""
    
    def test_compare_returns_all_fields(self):
        """compare_versions should return all expected fields."""
        result = compare_versions(14.0, 13.0)
        
        expected_fields = [
            "afr_measured", "afr_target",
            "v1_0_0", "v2_0_0",
            "v1_0_0_pct", "v2_0_0_pct",
            "difference", "difference_pct"
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_compare_calculates_difference(self):
        """compare_versions should calculate difference correctly."""
        result = compare_versions(16.0, 13.0)
        
        # Manual calculation
        v1 = 1 + (16.0 - 13.0) * 0.07  # 1.21
        v2 = 16.0 / 13.0  # 1.2308
        expected_diff = abs(v2 - v1)
        
        assert abs(result["difference"] - expected_diff) < 1e-10


# =============================================================================
# Test 8: Performance Regression
# =============================================================================

class TestPerformance:
    """Ensure no performance regression."""
    
    def test_single_calculation_speed(self):
        """Single calculation should be < 0.1ms."""
        import time
        
        start = time.perf_counter()
        for _ in range(10000):
            calculate_ve_correction(14.0, 13.0)
        elapsed = time.perf_counter() - start
        
        # 10000 calculations in < 100ms = < 0.01ms each
        assert elapsed < 0.1, f"10k calculations took {elapsed:.3f}s (too slow)"
    
    def test_batch_not_slower(self):
        """Batch should not be slower than individual."""
        import time
        
        measured = [14.0] * 1000
        targets = [13.0] * 1000
        
        # Individual
        start = time.perf_counter()
        for m, t in zip(measured, targets):
            calculate_ve_correction(m, t)
        individual_time = time.perf_counter() - start
        
        # Batch
        start = time.perf_counter()
        calculate_ve_correction_batch(measured, targets)
        batch_time = time.perf_counter() - start
        
        # Batch should be similar or faster
        assert batch_time <= individual_time * 2, \
            f"Batch ({batch_time:.4f}s) much slower than individual ({individual_time:.4f}s)"


# =============================================================================
# Test 9: Integration with Real Data
# =============================================================================

class TestIntegrationWithRealData:
    """Test with realistic data patterns."""
    
    def test_analyze_sample_data(self, sample_dyno_data):
        """Should correctly analyze sample dyno data."""
        df = sample_dyno_data
        
        corrections = []
        for _, row in df.iterrows():
            measured = row["AFR"]
            target = 13.0  # Fixed target for simplicity
            correction = calculate_ve_correction(measured, target)
            corrections.append(correction)
        
        # Most corrections should be near 1.0 (data is centered on 13.0)
        mean_correction = np.mean(corrections)
        assert 0.95 < mean_correction < 1.05, \
            f"Mean correction {mean_correction:.3f} too far from 1.0"
    
    def test_grid_analysis(self, sample_dyno_data):
        """Should work with grid-based analysis."""
        df = sample_dyno_data
        
        # Simple grid analysis
        rpm_bins = [2000, 3000, 4000, 5000, 6000]
        results = {}
        
        for rpm_bin in rpm_bins:
            mask = (df["RPM"] >= rpm_bin - 500) & (df["RPM"] < rpm_bin + 500)
            bin_data = df[mask]
            
            if len(bin_data) >= 3:
                mean_afr = bin_data["AFR"].mean()
                correction = calculate_ve_correction(mean_afr, 13.0)
                results[rpm_bin] = correction
        
        # Should have results for most bins
        assert len(results) >= 4, f"Expected at least 4 bins with data, got {len(results)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

