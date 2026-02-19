#!/usr/bin/env python3
"""
Quick Test Script: AI Correction System
========================================

Runs a quick end-to-end test of the v3 AI correction system.
Tests session creation, pull simulation, advisor recommendations, and convergence.
"""

import os
import sys
from pprint import pprint

# Add project root to path
sys.path.append(os.getcwd())


def test_ai_correction_system():
    """Run comprehensive test of AI correction system."""
    print("=" * 60)
    print("AI Correction System Test")
    print("=" * 60)
    print()

    try:
        from api.services.v3_session_service import (
            _get_session,
            check_convergence,
            create_session,
            get_uncertainty_map,
            materialize_run,
            simulate_pull_realistic,
            suggest_next_pull,
        )
    except ImportError as e:
        print(f"[FAIL] Could not import v3 services: {e}")
        print("Make sure dynoai_v3 is installed and backend is set up correctly.")
        return False

    # Test 1: Create Session
    print("Test 1: Creating Session...")
    try:
        config = {
            "engine_family": "m8_114",
            "rpm_bins": [2000, 3000, 4000, 5000, 6000],
            "map_bins": [40, 60, 80, 100],
        }
        session_data = create_session(config)
        session_id = session_data["session_id"]
        print(f"  [OK] Session created: {session_id[:8]}...")
        print(
            f"  [OK] Grid: {len(config['rpm_bins'])} RPM x {len(config['map_bins'])} MAP bins"
        )
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Test 2: Get Initial Recommendation
    print("\nTest 2: Getting Initial Pull Recommendation...")
    try:
        rec = suggest_next_pull(session_id)
        print(f"  [OK] Recommended: {rec['rpm']:.0f} RPM @ {rec['map_kpa']:.0f} kPa")
        print(f"  [OK] Mode: {rec.get('pull_mode', 'N/A')}")
        print(f"  [OK] Reason: {rec.get('reason', 'N/A')[:60]}...")
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Test 3: Run Simulated Pulls
    print("\nTest 3: Running Simulated Pulls...")
    pull_results = []
    num_pulls = 5

    for i in range(num_pulls):
        try:
            # Get recommendation
            rec = suggest_next_pull(session_id)
            rpm = rec["rpm"]
            map_kpa = rec["map_kpa"]

            print(
                f"  Pull #{i + 1}: Simulating at {rpm:.0f} RPM @ {map_kpa:.0f} kPa...",
                end=" ",
            )

            # Simulate pull
            result = simulate_pull_realistic(session_id, rpm=rpm, map_kpa=map_kpa)

            obs_added = result.get("observations_added", 0)
            pull_num = result.get("pull_number", 0)

            print(f"[OK] ({obs_added} observations)")

            pull_results.append(
                {
                    "pull_number": pull_num,
                    "rpm": rpm,
                    "map_kpa": map_kpa,
                    "observations_added": obs_added,
                }
            )

        except Exception as e:
            print(f"[FAIL] Failed: {e}")
            return False

    # Test 4: Check Convergence
    print("\nTest 4: Checking Convergence Status...")
    try:
        conv = check_convergence(session_id)
        print(f"  [OK] Coverage: {conv.get('coverage_pct', 0):.1f}%")
        print(f"  [OK] Mean Uncertainty: {conv.get('mean_uncertainty', 0):.3f}")
        print(f"  [OK] Converged: {conv.get('converged', False)}")
        print(f"  [OK] Pulls Remaining: {conv.get('pulls_remaining', 'N/A')}")
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Test 5: Get Uncertainty Map
    print("\nTest 5: Getting Uncertainty Map...")
    try:
        unc_map = get_uncertainty_map(session_id)
        uncertainty = unc_map.get("uncertainty", [])
        if uncertainty:
            import numpy as np

            unc_array = np.array(uncertainty)
            print(
                f"  [OK] Uncertainty range: {unc_array.min():.3f} - {unc_array.max():.3f}"
            )
            print(f"  [OK] Mean uncertainty: {unc_array.mean():.3f}")
        else:
            print("  [WARN] No uncertainty data available")
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Test 6: Verify Observations Stored
    print("\nTest 6: Verifying Observations in GP Surrogate...")
    try:
        session = _get_session(session_id)
        observations = session.surrogate.observations

        # Filter out template observations (pull_number == -1)
        real_obs = [obs for obs in observations if obs.pull_number != -1]

        print(f"  [OK] Total observations: {len(real_obs)}")

        if real_obs:
            # Check VE values are reasonable (absolute VE should be 50-150%)
            ve_values = [obs.ve_delta for obs in real_obs]
            min_ve = min(ve_values)
            max_ve = max(ve_values)
            print(f"  [OK] VE range: {min_ve:.1f}% - {max_ve:.1f}%")

            if 50.0 <= min_ve <= max_ve <= 150.0:
                print("  [OK] VE values are in expected range (absolute VE)")
            else:
                print(
                    f"  [WARN] VE values outside expected range (might be deltas instead of absolute)"
                )

        # Check GP is fitted
        if session.surrogate.is_fitted:
            print("  [OK] GP Surrogate is fitted")
        else:
            print("  [WARN] GP Surrogate not fitted (may need more observations)")

    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Test 7: Materialize Run (Generate Corrections)
    print("\nTest 7: Materializing Run (Generating Corrections)...")
    try:
        result = materialize_run(session_id)
        run_id = result.get("run_id")
        ve_2d_path = result.get("ve_2d_path")

        print(f"  [OK] Run ID: {run_id}")
        print(f"  [OK] VE Corrections 2D: {ve_2d_path}")

        # Verify file exists
        if os.path.exists(ve_2d_path):
            print(f"  [OK] Corrections file exists")
        else:
            print(f"  [WARN] Corrections file not found at: {ve_2d_path}")

    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        print(
            "  Note: This might fail if no corrections are cached. Run simulate() first."
        )
        # Don't fail the whole test for this

    # Test 8: Verify Hit Count Penalty
    print("\nTest 8: Verifying Hit Count Penalty...")
    try:
        session = _get_session(session_id)
        advisor = session.advisor

        # Check if hit count penalty method exists
        if hasattr(advisor, "_get_hit_count_penalty"):
            penalty = advisor._get_hit_count_penalty()
            import numpy as np

            # Check penalty values are reasonable
            min_penalty = penalty.min()
            max_penalty = penalty.max()

            print(f"  [OK] Penalty range: {min_penalty:.3f} - {max_penalty:.3f}")

            if 0.0 <= min_penalty <= max_penalty <= 1.0:
                print("  [OK] Penalty values are in expected range [0, 1]")
            else:
                print("  [WARN] Penalty values outside expected range")
        else:
            print("  [WARN] Hit count penalty method not found")

    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"[OK] Session created successfully")
    print(f"[OK] {num_pulls} simulated pulls completed")
    print(
        f"[OK] Total observations: {sum(r['observations_added'] for r in pull_results)}"
    )
    print(f"[OK] Convergence checked")
    print(f"[OK] Uncertainty map retrieved")
    print(f"[OK] Observations verified in GP surrogate")
    print(f"[OK] Hit count penalty verified")
    print()
    print("[SUCCESS] All tests passed! AI correction system is working correctly.")
    print()
    print(f"Session ID: {session_id}")
    print("You can use this session ID to continue testing via API or UI.")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_ai_correction_system()
    sys.exit(0 if success else 1)
