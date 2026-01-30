"""
Comprehensive test suite for DynoAI VE Math Module (v2.0.0)

This test suite validates:
1. v2.0.0 ratio model correctness
2. v1.0.0 legacy model backwards compatibility
3. Comparison between versions
4. Edge cases and error handling
5. Determinism guarantees
6. Safety clamping behavior

Run with: pytest tests/test_ve_math.py -v
"""

import pytest
import math
import random
from typing import List, Tuple

from dynoai.core.ve_math import (
    MathVersion,
    MathConfig,
    calculate_ve_correction,
    calculate_ve_correction_batch,
    get_default_config,
    get_legacy_config,
    compare_versions,
    correction_to_percentage,
    percentage_to_correction,
    get_version_info,
    VEMathError,
    AFRValidationError,
    AFR_MIN,
    AFR_MAX,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def default_config():
    """Default v2.0.0 configuration."""
    return get_default_config()


@pytest.fixture
def legacy_config():
    """Legacy v1.0.0 configuration."""
    return get_legacy_config()


@pytest.fixture
def typical_test_cases() -> List[Tuple[float, float, float, float]]:
    """
    Typical test cases with expected values.
    
    Format: (afr_measured, afr_target, expected_v1, expected_v2)
    """
    return [
        # On target - no correction
        (13.0, 13.0, 1.0, 1.0),
        (14.7, 14.7, 1.0, 1.0),
        (12.5, 12.5, 1.0, 1.0),
        
        # Lean cases - need more fuel
        (14.0, 13.0, 1.07, 14.0/13.0),
        (15.0, 13.0, 1.14, 15.0/13.0),
        (14.0, 12.5, 1.105, 14.0/12.5),
        (15.0, 12.5, 1.175, 15.0/12.5),
        
        # Rich cases - need less fuel
        (12.0, 13.0, 0.93, 12.0/13.0),
        (11.0, 13.0, 0.86, 11.0/13.0),
        (12.0, 14.0, 0.86, 12.0/14.0),
        (11.5, 13.5, 0.86, 11.5/13.5),
    ]


# =============================================================================
# Test v2.0.0 Ratio Model
# =============================================================================

class TestV2RatioModel:
    """Tests for v2.0.0 ratio model correctness."""
    
    def test_on_target_no_correction(self):
        """When measured equals target, correction should be exactly 1.0."""
        test_targets = [12.0, 12.5, 13.0, 13.5, 14.0, 14.7, 15.0]
        
        for target in test_targets:
            correction = calculate_ve_correction(
                target, target, version=MathVersion.V2_0_0
            )
            assert correction == 1.0, f"Expected 1.0 for AFR {target}/{target}, got {correction}"
    
    def test_lean_increases_fuel(self):
        """Lean condition (measured > target) should increase VE (correction > 1)."""
        # Various lean scenarios
        lean_cases = [
            (14.0, 13.0),
            (15.0, 13.0),
            (14.5, 12.5),
            (16.0, 14.0),
        ]
        
        for measured, target in lean_cases:
            correction = calculate_ve_correction(
                measured, target, version=MathVersion.V2_0_0
            )
            assert correction > 1.0, f"Lean ({measured}/{target}) should give correction > 1.0, got {correction}"
    
    def test_rich_decreases_fuel(self):
        """Rich condition (measured < target) should decrease VE (correction < 1)."""
        # Various rich scenarios
        rich_cases = [
            (12.0, 13.0),
            (11.0, 13.0),
            (12.5, 14.0),
            (11.0, 14.7),
        ]
        
        for measured, target in rich_cases:
            correction = calculate_ve_correction(
                measured, target, version=MathVersion.V2_0_0
            )
            assert correction < 1.0, f"Rich ({measured}/{target}) should give correction < 1.0, got {correction}"
    
    def test_ratio_formula_exact(self):
        """Verify ratio formula: correction = measured / target (exactly)."""
        test_cases = [
            (14.0, 13.0),
            (15.0, 12.5),
            (11.0, 14.0),
            (13.5, 13.5),
            (12.123, 13.456),
            (14.789, 12.345),
        ]
        
        for measured, target in test_cases:
            correction = calculate_ve_correction(
                measured, target, version=MathVersion.V2_0_0, clamp=False
            )
            expected = measured / target
            
            # Should be exactly equal (not approximate)
            assert abs(correction - expected) < 1e-15, \
                f"For {measured}/{target}: expected {expected}, got {correction}"
    
    def test_correction_magnitude_proportional_to_error(self):
        """Larger AFR errors should produce proportionally larger corrections."""
        target = 13.0
        
        # Lean scenarios (increasing deviation)
        prev_correction = 1.0
        for measured in [13.5, 14.0, 14.5, 15.0, 15.5]:
            correction = calculate_ve_correction(
                measured, target, version=MathVersion.V2_0_0, clamp=False
            )
            assert correction > prev_correction, \
                f"Correction should increase monotonically for lean. AFR={measured}"
            prev_correction = correction
        
        # Rich scenarios (increasing deviation)
        prev_correction = 1.0
        for measured in [12.5, 12.0, 11.5, 11.0, 10.5]:
            correction = calculate_ve_correction(
                measured, target, version=MathVersion.V2_0_0, clamp=False
            )
            assert correction < prev_correction, \
                f"Correction should decrease monotonically for rich. AFR={measured}"
            prev_correction = correction


# =============================================================================
# Test v1.0.0 Legacy Model
# =============================================================================

class TestV1LegacyModel:
    """Tests for v1.0.0 legacy model backwards compatibility."""
    
    def test_on_target_no_correction(self):
        """When measured equals target, correction should be exactly 1.0."""
        test_targets = [12.0, 13.0, 14.0, 14.7]
        
        for target in test_targets:
            correction = calculate_ve_correction(
                target, target, version=MathVersion.V1_0_0
            )
            assert correction == 1.0, f"Expected 1.0 for AFR {target}/{target}, got {correction}"
    
    def test_7_percent_per_afr_point(self):
        """Verify v1.0.0 uses 7% per AFR point formula."""
        target = 13.0
        
        # +1 AFR point (lean) -> +7%
        correction = calculate_ve_correction(
            14.0, target, version=MathVersion.V1_0_0
        )
        assert abs(correction - 1.07) < 0.0001
        
        # +2 AFR points (very lean) -> +14%
        correction = calculate_ve_correction(
            15.0, target, version=MathVersion.V1_0_0
        )
        assert abs(correction - 1.14) < 0.0001
        
        # -1 AFR point (rich) -> -7%
        correction = calculate_ve_correction(
            12.0, target, version=MathVersion.V1_0_0
        )
        assert abs(correction - 0.93) < 0.0001
        
        # -2 AFR points (very rich) -> -14%
        correction = calculate_ve_correction(
            11.0, target, version=MathVersion.V1_0_0
        )
        assert abs(correction - 0.86) < 0.0001
    
    def test_linear_relationship(self):
        """v1.0.0 should show linear relationship between error and correction."""
        target = 13.0
        
        # Calculate corrections for a range of measured values
        corrections = []
        for measured in [11.0, 12.0, 13.0, 14.0, 15.0]:
            c = calculate_ve_correction(
                measured, target, version=MathVersion.V1_0_0, clamp=False
            )
            corrections.append(c)
        
        # Check that differences between consecutive corrections are equal (linear)
        diffs = [corrections[i+1] - corrections[i] for i in range(len(corrections)-1)]
        
        for i, diff in enumerate(diffs):
            assert abs(diff - 0.07) < 0.0001, \
                f"v1.0.0 should be linear (7% per point), got diff={diff}"


# =============================================================================
# Test Version Comparison
# =============================================================================

class TestVersionComparison:
    """Tests comparing v1.0.0 and v2.0.0 results."""
    
    def test_small_error_similar(self):
        """At small AFR errors, v1 and v2 should be within 1% relative difference."""
        targets = [12.5, 13.0, 13.5, 14.0, 14.7]
        small_deltas = [-0.5, -0.3, 0.3, 0.5]
        
        for target in targets:
            for delta in small_deltas:
                measured = target + delta
                if not (AFR_MIN <= measured <= AFR_MAX):
                    continue
                    
                v1 = calculate_ve_correction(measured, target, MathVersion.V1_0_0, clamp=False)
                v2 = calculate_ve_correction(measured, target, MathVersion.V2_0_0, clamp=False)
                
                relative_diff = abs(v1 - v2) / v2 if v2 != 0 else 0
                assert relative_diff < 0.01, \
                    f"At small error ({measured}/{target}), versions should be within 1%. Got {relative_diff*100:.2f}%"
    
    def test_large_error_diverges(self):
        """At large AFR errors, v2 should give larger absolute corrections than v1."""
        # Very lean case
        v1_lean = calculate_ve_correction(16.0, 12.5, MathVersion.V1_0_0, clamp=False)
        v2_lean = calculate_ve_correction(16.0, 12.5, MathVersion.V2_0_0, clamp=False)
        
        # v2 should give a larger correction (more accurate)
        assert v2_lean > v1_lean, \
            f"v2 should give larger correction for lean. v1={v1_lean}, v2={v2_lean}"
        
        # Very rich case
        v1_rich = calculate_ve_correction(10.0, 13.0, MathVersion.V1_0_0, clamp=False)
        v2_rich = calculate_ve_correction(10.0, 13.0, MathVersion.V2_0_0, clamp=False)
        
        # v2 should give a more negative correction
        assert v2_rich < v1_rich, \
            f"v2 should give more negative correction for rich. v1={v1_rich}, v2={v2_rich}"
    
    def test_compare_versions_function(self):
        """Test the compare_versions utility function."""
        result = compare_versions(14.0, 13.0)
        
        assert "v1_0_0" in result
        assert "v2_0_0" in result
        assert "difference" in result
        assert "difference_pct" in result
        
        # v2 should be larger for lean condition
        assert result["v2_0_0"] > result["v1_0_0"]
    
    def test_v1_underestimates_large_corrections(self):
        """Demonstrate that v1.0.0 underestimates at large deviations."""
        # At 3 AFR points deviation
        measured = 16.0
        target = 13.0
        
        v1 = calculate_ve_correction(measured, target, MathVersion.V1_0_0, clamp=False)
        v2 = calculate_ve_correction(measured, target, MathVersion.V2_0_0, clamp=False)
        
        # v1: 1 + (3 * 0.07) = 1.21
        # v2: 16/13 = 1.2308
        # Difference: ~2%
        
        assert abs(v1 - 1.21) < 0.001
        assert abs(v2 - (16.0/13.0)) < 0.0001
        
        # v1 underestimates the required correction
        underestimate = (v2 - v1) / v2 * 100
        assert underestimate > 1.5, \
            f"v1 should underestimate by >1.5% at 3 AFR points. Got {underestimate:.2f}%"


# =============================================================================
# Test Input Validation
# =============================================================================

class TestInputValidation:
    """Tests for input validation and error handling."""
    
    def test_afr_too_low_raises(self):
        """AFR below minimum should raise AFRValidationError."""
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(5.0, 13.0)  # measured too low
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(13.0, 5.0)  # target too low
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(8.9, 13.0)  # just below minimum
    
    def test_afr_too_high_raises(self):
        """AFR above maximum should raise AFRValidationError."""
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(25.0, 13.0)  # measured too high
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(13.0, 25.0)  # target too high
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(20.1, 13.0)  # just above maximum
    
    def test_afr_zero_raises(self):
        """AFR of zero should raise AFRValidationError."""
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(0, 13.0)
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(13.0, 0)
    
    def test_afr_none_raises(self):
        """AFR of None should raise AFRValidationError."""
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(None, 13.0)
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(13.0, None)
    
    def test_afr_nan_raises(self):
        """AFR of NaN should raise AFRValidationError."""
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(float('nan'), 13.0)
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction(13.0, float('nan'))
    
    def test_boundary_values_accepted(self):
        """Boundary AFR values should be accepted."""
        # Minimum boundary
        correction = calculate_ve_correction(AFR_MIN, 13.0)
        assert correction is not None
        
        # Maximum boundary
        correction = calculate_ve_correction(AFR_MAX, 13.0)
        assert correction is not None
        
        # Both at boundaries
        correction = calculate_ve_correction(AFR_MIN, AFR_MIN)
        assert correction == 1.0


# =============================================================================
# Test Safety Clamping
# =============================================================================

class TestSafetyClamping:
    """Tests for safety clamping behavior."""
    
    def test_default_clamp_15_percent(self):
        """Default clamping should limit to ±15%."""
        config = get_default_config()
        assert config.max_correction_pct == 15.0
        
        # Very lean - would be ~23% but clamped to 15%
        correction = calculate_ve_correction(16.0, 13.0, clamp=True)
        assert correction <= 1.15
        
        # Very rich - would be ~-23% but clamped to -15%
        correction = calculate_ve_correction(10.0, 13.0, clamp=True)
        assert correction >= 0.85
    
    def test_clamp_disabled(self):
        """With clamp=False, corrections should not be limited."""
        # Very lean
        correction = calculate_ve_correction(16.0, 13.0, clamp=False)
        expected = 16.0 / 13.0  # ~1.23
        assert abs(correction - expected) < 0.0001
        
        # Very rich
        correction = calculate_ve_correction(10.0, 13.0, clamp=False)
        expected = 10.0 / 13.0  # ~0.77
        assert abs(correction - expected) < 0.0001
    
    def test_custom_clamp_limit(self):
        """Custom clamping limits should be respected."""
        config = MathConfig(
            version=MathVersion.V2_0_0,
            max_correction_pct=7.0,
        )
        
        # Would be ~7.7% but clamped to 7%
        correction = calculate_ve_correction(14.0, 13.0, config=config)
        assert correction <= 1.07 + 1e-10
        
        # Would be ~-7.7% but clamped to -7%
        correction = calculate_ve_correction(12.0, 13.0, config=config)
        assert correction >= 0.93 - 1e-10
    
    def test_within_clamp_unchanged(self):
        """Corrections within clamp range should not be modified."""
        # Small correction - should not be clamped
        correction_clamped = calculate_ve_correction(13.5, 13.0, clamp=True)
        correction_unclamped = calculate_ve_correction(13.5, 13.0, clamp=False)
        
        assert correction_clamped == correction_unclamped


# =============================================================================
# Test Determinism
# =============================================================================

class TestDeterminism:
    """Tests for determinism guarantees."""
    
    def test_same_inputs_same_outputs(self):
        """Same inputs must always produce identical outputs."""
        test_cases = [
            (14.0, 13.0),
            (12.5, 13.5),
            (13.123, 12.456),
        ]
        
        for measured, target in test_cases:
            results = []
            for _ in range(100):
                result = calculate_ve_correction(measured, target)
                results.append(result)
            
            # All results must be identical
            assert len(set(results)) == 1, \
                f"Non-deterministic results for {measured}/{target}"
    
    def test_no_randomness_in_calculation(self):
        """Verify calculation doesn't use random number generation."""
        initial_state = random.getstate()
        
        # Perform many calculations
        for _ in range(100):
            calculate_ve_correction(14.0, 13.0)
            calculate_ve_correction(12.0, 13.0)
        
        final_state = random.getstate()
        
        # Random state should be unchanged
        assert initial_state == final_state, \
            "Calculation should not affect random state"
    
    def test_bit_reproducibility(self):
        """Results should be bit-reproducible (floating point exact)."""
        for _ in range(10):
            r1 = calculate_ve_correction(14.123456789, 13.987654321)
            r2 = calculate_ve_correction(14.123456789, 13.987654321)
            
            # Use == for bit-exact comparison (not approximate)
            assert r1 == r2, "Results should be bit-exact"


# =============================================================================
# Test Batch Processing
# =============================================================================

class TestBatchProcessing:
    """Tests for batch calculation function."""
    
    def test_batch_basic(self):
        """Basic batch calculation should work."""
        measured = [14.0, 13.0, 12.0]
        targets = [13.0, 13.0, 13.0]
        
        results = calculate_ve_correction_batch(measured, targets)
        
        assert len(results) == 3
        assert results[0] > 1.0  # Lean
        assert results[1] == 1.0  # On target
        assert results[2] < 1.0  # Rich
    
    def test_batch_matches_individual(self):
        """Batch results should match individual calculations."""
        measured = [14.0, 13.5, 13.0, 12.5, 12.0]
        targets = [13.0, 13.0, 13.0, 13.0, 13.0]
        
        batch_results = calculate_ve_correction_batch(measured, targets)
        
        for i, (m, t) in enumerate(zip(measured, targets)):
            individual = calculate_ve_correction(m, t)
            assert batch_results[i] == individual, \
                f"Batch result {batch_results[i]} != individual {individual} at index {i}"
    
    def test_batch_length_mismatch_raises(self):
        """Mismatched input lengths should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_ve_correction_batch([14.0, 13.0], [13.0])
    
    def test_batch_skip_invalid(self):
        """With skip_invalid=True, invalid entries should return None."""
        measured = [14.0, 5.0, 13.0]  # 5.0 is invalid
        targets = [13.0, 13.0, 13.0]
        
        results = calculate_ve_correction_batch(measured, targets, skip_invalid=True)
        
        assert results[0] is not None
        assert results[1] is None  # Invalid entry
        assert results[2] is not None
    
    def test_batch_invalid_raises_by_default(self):
        """Without skip_invalid, invalid entries should raise."""
        measured = [14.0, 5.0, 13.0]  # 5.0 is invalid
        targets = [13.0, 13.0, 13.0]
        
        with pytest.raises(AFRValidationError):
            calculate_ve_correction_batch(measured, targets)


# =============================================================================
# Test Configuration
# =============================================================================

class TestConfiguration:
    """Tests for MathConfig behavior."""
    
    def test_default_config_is_v2(self):
        """Default configuration should use v2.0.0."""
        config = get_default_config()
        assert config.version == MathVersion.V2_0_0
    
    def test_legacy_config_is_v1(self):
        """Legacy configuration should use v1.0.0."""
        config = get_legacy_config()
        assert config.version == MathVersion.V1_0_0
    
    def test_config_immutable(self):
        """MathConfig should be immutable."""
        config = get_default_config()
        
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            config.version = MathVersion.V1_0_0
    
    def test_invalid_config_raises(self):
        """Invalid configuration values should raise ValueError."""
        with pytest.raises(ValueError):
            MathConfig(max_correction_pct=-5.0)
        
        with pytest.raises(ValueError):
            MathConfig(afr_min=20.0, afr_max=10.0)  # min > max
        
        with pytest.raises(ValueError):
            MathConfig(afr_min=-5.0)  # negative min
    
    def test_version_override(self):
        """Version parameter should override config version."""
        config = MathConfig(version=MathVersion.V1_0_0)
        
        # Use v2 despite config being v1
        correction = calculate_ve_correction(
            14.0, 13.0, version=MathVersion.V2_0_0, config=config
        )
        
        expected_v2 = 14.0 / 13.0
        assert abs(correction - expected_v2) < 0.0001


# =============================================================================
# Test Utility Functions
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_correction_to_percentage(self):
        """Test conversion from multiplier to percentage."""
        assert correction_to_percentage(1.0) == 0.0
        assert abs(correction_to_percentage(1.07) - 7.0) < 1e-10
        assert abs(correction_to_percentage(0.93) - (-7.0)) < 1e-10
        assert abs(correction_to_percentage(1.077) - 7.7) < 0.0001
    
    def test_percentage_to_correction(self):
        """Test conversion from percentage to multiplier."""
        assert percentage_to_correction(0.0) == 1.0
        assert abs(percentage_to_correction(7.0) - 1.07) < 1e-10
        assert abs(percentage_to_correction(-7.0) - 0.93) < 1e-10
        assert abs(percentage_to_correction(7.7) - 1.077) < 0.0001
    
    def test_roundtrip_conversion(self):
        """Percentage/correction conversion should be reversible."""
        test_corrections = [0.85, 0.93, 1.0, 1.07, 1.15]
        
        for correction in test_corrections:
            pct = correction_to_percentage(correction)
            back = percentage_to_correction(pct)
            assert abs(back - correction) < 1e-10
    
    def test_get_version_info(self):
        """Test version info function."""
        info = get_version_info()
        
        assert "default_version" in info
        assert "available_versions" in info
        assert "v1_formula" in info
        assert "v2_formula" in info
        assert info["default_version"] == "2.0.0"


# =============================================================================
# Test Real-World Scenarios
# =============================================================================

class TestRealWorldScenarios:
    """Tests based on real-world tuning scenarios."""
    
    def test_typical_wot_lean_condition(self):
        """Typical WOT lean condition needing fuel added."""
        # Target 12.5:1 at WOT, measuring 13.5:1 (lean)
        correction = calculate_ve_correction(13.5, 12.5)
        
        # Should recommend ~8% more fuel
        pct = correction_to_percentage(correction)
        assert 7.0 < pct < 9.0, f"Expected ~8% correction, got {pct:.1f}%"
    
    def test_typical_cruise_rich_condition(self):
        """Typical cruise rich condition needing fuel removed."""
        # Target 14.7:1 at cruise, measuring 13.5:1 (rich)
        correction = calculate_ve_correction(13.5, 14.7)
        
        # Should recommend ~8% less fuel
        pct = correction_to_percentage(correction)
        assert -9.0 < pct < -7.0, f"Expected ~-8% correction, got {pct:.1f}%"
    
    def test_slight_adjustment_scenario(self):
        """Slight adjustment scenario (typical fine-tuning)."""
        # Target 13.0, measuring 13.2 (slightly lean)
        correction = calculate_ve_correction(13.2, 13.0)
        
        # Should recommend ~1.5% more fuel
        pct = correction_to_percentage(correction)
        assert 1.0 < pct < 2.0, f"Expected ~1.5% correction, got {pct:.1f}%"
    
    def test_severe_lean_clamped(self):
        """Severe lean condition should be clamped for safety."""
        # Dangerously lean: 17:1 with 12:1 target
        correction = calculate_ve_correction(17.0, 12.0)
        
        # Should be clamped to 15%
        assert correction <= 1.15, \
            f"Severe lean should be clamped to ≤1.15, got {correction}"
    
    def test_multiple_cylinders_same_correction(self):
        """Same conditions should give same correction for both cylinders."""
        # Front and rear with same readings
        front = calculate_ve_correction(14.0, 13.0)
        rear = calculate_ve_correction(14.0, 13.0)
        
        assert front == rear, "Same inputs should give same outputs"


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_very_small_difference(self):
        """Very small AFR difference should give correction very close to 1.0."""
        correction = calculate_ve_correction(13.001, 13.0)
        
        assert 0.9999 < correction < 1.0001, \
            f"Tiny difference should give correction ≈1.0, got {correction}"
    
    def test_equal_at_all_afr_levels(self):
        """On-target should give 1.0 at any AFR level."""
        for afr in [9.5, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]:
            correction = calculate_ve_correction(afr, afr)
            assert correction == 1.0, f"AFR {afr}/{afr} should give 1.0, got {correction}"
    
    def test_precision_at_extreme_values(self):
        """Precision should be maintained at extreme valid values."""
        # Near minimum
        correction = calculate_ve_correction(9.0, 9.5)
        expected = 9.0 / 9.5
        assert abs(correction - expected) < 1e-10
        
        # Near maximum
        correction = calculate_ve_correction(20.0, 19.0, clamp=False)
        expected = 20.0 / 19.0
        assert abs(correction - expected) < 1e-10


# =============================================================================
# Performance Tests (Optional)
# =============================================================================

class TestPerformance:
    """Basic performance tests."""
    
    def test_single_calculation_fast(self):
        """Single calculation should be very fast."""
        import time
        
        start = time.perf_counter()
        for _ in range(10000):
            calculate_ve_correction(14.0, 13.0)
        elapsed = time.perf_counter() - start
        
        # 10000 calculations should take less than 100ms
        assert elapsed < 0.1, f"10k calculations took {elapsed:.3f}s"
    
    def test_batch_faster_than_individual(self):
        """Batch processing should not be slower than individual calls."""
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
        assert batch_time <= individual_time * 1.5, \
            f"Batch ({batch_time:.4f}s) significantly slower than individual ({individual_time:.4f}s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

