#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for JetDrive Realtime Analysis NoneType fix

This script tests that the realtime analysis engine handles None and NaN values
correctly without raising comparison errors.
"""

import io
import math
import sys
from pathlib import Path

from api.services.jetdrive_realtime_analysis import RealtimeAnalysisEngine

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_none_tps():
    """Test that None TPS values don't cause comparison errors."""
    print("Testing None TPS value handling...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    # First sample with valid TPS
    sample1 = {
        "rpm": 3000.0,
        "map_kpa": 50.0,
        "afr": 14.5,
        "tps": 50.0,
    }
    engine.on_aggregated_sample(sample1)
    print("  ✓ Valid TPS sample processed")

    # Second sample with None TPS (should not crash)
    sample2 = {
        "rpm": 3000.0,
        "map_kpa": 50.0,
        "afr": 14.5,
        "tps": None,  # This was causing the error
    }
    try:
        engine.on_aggregated_sample(sample2)
        print("  ✓ None TPS sample processed without error")
    except TypeError as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def test_nan_afr():
    """Test that NaN AFR values don't cause comparison errors."""
    print("\nTesting NaN AFR value handling...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    # Sample with NaN AFR
    sample = {
        "rpm": 3000.0,
        "map_kpa": 50.0,
        "afr": float("nan"),  # NaN should be handled
        "tps": 50.0,
    }
    try:
        engine.on_aggregated_sample(sample)
        print("  ✓ NaN AFR sample processed without error")
    except (TypeError, ValueError) as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def test_all_none_values():
    """Test that samples with all None values don't crash."""
    print("\nTesting all None values...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    sample = {
        "rpm": None,
        "map_kpa": None,
        "afr": None,
        "tps": None,
    }
    try:
        engine.on_aggregated_sample(sample)
        print("  ✓ All None sample processed without error")
    except TypeError as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def test_mixed_valid_invalid():
    """Test mixed valid and invalid values."""
    print("\nTesting mixed valid/invalid values...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    samples = [
        # Valid sample
        {"rpm": 3000.0, "map_kpa": 50.0, "afr": 14.5, "tps": 50.0},
        # None TPS
        {"rpm": 3100.0, "map_kpa": 52.0, "afr": 14.6, "tps": None},
        # NaN AFR
        {"rpm": 3200.0, "map_kpa": 54.0, "afr": float("nan"), "tps": 55.0},
        # None RPM (should skip coverage)
        {"rpm": None, "map_kpa": 56.0, "afr": 14.7, "tps": 60.0},
        # All None
        {"rpm": None, "map_kpa": None, "afr": None, "tps": None},
    ]

    try:
        for i, sample in enumerate(samples):
            engine.on_aggregated_sample(sample)
        print(f"  ✓ All {len(samples)} mixed samples processed without error")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def test_edge_cases():
    """Test edge cases that could cause issues."""
    print("\nTesting edge cases...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    edge_cases = [
        # Zero values (valid but edge case)
        {"rpm": 0.0, "map_kpa": 0.0, "afr": 0.0, "tps": 0.0},
        # Negative values (invalid but shouldn't crash)
        {"rpm": -100.0, "map_kpa": -10.0, "afr": -5.0, "tps": -20.0},
        # Very large values
        {"rpm": 99999.0, "map_kpa": 500.0, "afr": 50.0, "tps": 200.0},
        # Mixed None and NaN
        {"rpm": None, "map_kpa": float("nan"), "afr": None, "tps": float("nan")},
    ]

    try:
        for sample in edge_cases:
            engine.on_aggregated_sample(sample)
        print(f"  ✓ All {len(edge_cases)} edge cases handled correctly")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def test_state_retrieval():
    """Test that state retrieval works after processing samples."""
    print("\nTesting state retrieval...")
    engine = RealtimeAnalysisEngine(target_afr=14.7)

    # Process some samples
    samples = [
        {"rpm": 3000.0, "map_kpa": 50.0, "afr": 14.5, "tps": 50.0},
        {"rpm": 3500.0, "map_kpa": 60.0, "afr": 14.6, "tps": 60.0},
        {"rpm": None, "map_kpa": None, "afr": None, "tps": None},
    ]

    for sample in samples:
        engine.on_aggregated_sample(sample)

    try:
        state = engine.get_state()
        print(f"  ✓ State retrieved successfully")
        print(f"    - Coverage: {state['coverage']['coverage_pct']:.1f}%")
        print(f"    - Cells hit: {state['coverage']['cells_hit']}")
        print(f"    - Quality score: {state['quality']['score']:.1f}")
        print(f"    - Alerts: {len(state['alerts'])}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("JetDrive Realtime Analysis - NoneType Fix Test Suite")
    print("=" * 60)

    tests = [
        test_none_tps,
        test_nan_afr,
        test_all_none_values,
        test_mixed_valid_invalid,
        test_edge_cases,
        test_state_retrieval,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{len(tests)} passed")
    if failed == 0:
        print("✅ ALL TESTS PASSED - Fix is working correctly!")
    else:
        print(f"❌ {failed} test(s) failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
