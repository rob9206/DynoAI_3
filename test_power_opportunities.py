"""
Test script for the Find Me Power analysis feature.

This script tests the find_power_opportunities() function with synthetic data
to ensure it correctly identifies power opportunities.
"""

import sys
from pathlib import Path

# Add parent directory to path to import the main module
sys.path.insert(0, str(Path(__file__).parent))

from ai_tuner_toolkit_dyno_v1_2 import (
    find_power_opportunities,
    RPM_BINS,
    KPA_BINS,
)


def create_test_grids():
    """Create synthetic test data for power opportunity analysis."""
    rows = len(RPM_BINS)
    cols = len(KPA_BINS)
    
    # Initialize grids
    afr_err_f = [[None for _ in range(cols)] for _ in range(rows)]
    afr_err_r = [[None for _ in range(cols)] for _ in range(rows)]
    spark_f = [[0.0 for _ in range(cols)] for _ in range(rows)]
    spark_r = [[0.0 for _ in range(cols)] for _ in range(rows)]
    coverage_f = [[0 for _ in range(cols)] for _ in range(rows)]
    coverage_r = [[0 for _ in range(cols)] for _ in range(rows)]
    knock_f = [[0.0 for _ in range(cols)] for _ in range(rows)]
    knock_r = [[0.0 for _ in range(cols)] for _ in range(rows)]
    hp_grid = [[None for _ in range(cols)] for _ in range(rows)]
    
    # Scenario 1: Rich cell with good coverage (should suggest leaning)
    # RPM 3000 (index 2), KPA 65 (index 1)
    afr_err_f[2][1] = 4.5  # 4.5% rich
    afr_err_r[2][1] = 4.0  # 4.0% rich
    coverage_f[2][1] = 30
    coverage_r[2][1] = 25
    knock_f[2][1] = 0.0
    knock_r[2][1] = 0.0
    hp_grid[2][1] = 75.0
    
    # Scenario 2: No knock, room for timing advance
    # RPM 3500 (index 3), KPA 80 (index 3)
    afr_err_f[3][3] = 0.5  # Slightly rich
    afr_err_r[3][3] = 0.3
    coverage_f[3][3] = 40
    coverage_r[3][3] = 35
    knock_f[3][3] = 0.0
    knock_r[3][3] = 0.0
    spark_f[3][3] = 0.0  # No current timing suggestion
    spark_r[3][3] = 0.0
    hp_grid[3][3] = 85.0
    
    # Scenario 3: Combined opportunity (rich + no knock)
    # RPM 4000 (index 4), KPA 95 (index 4)
    afr_err_f[4][4] = 3.5  # Rich
    afr_err_r[4][4] = 3.2
    coverage_f[4][4] = 50
    coverage_r[4][4] = 45
    knock_f[4][4] = 0.0
    knock_r[4][4] = 0.0
    spark_f[4][4] = 0.0
    spark_r[4][4] = 0.0
    hp_grid[4][4] = 95.0
    
    # Scenario 4: Knock detected - should NOT suggest changes
    # RPM 4500 (index 5), KPA 95 (index 4)
    afr_err_f[5][4] = 4.0  # Rich but has knock
    afr_err_r[5][4] = 3.8
    coverage_f[5][4] = 30
    coverage_r[5][4] = 28
    knock_f[5][4] = 1.5  # Knock detected!
    knock_r[5][4] = 1.2
    hp_grid[5][4] = 100.0
    
    # Scenario 5: Low coverage - should NOT suggest changes
    # RPM 5000 (index 6), KPA 80 (index 3)
    afr_err_f[6][3] = 5.0  # Very rich but low coverage
    afr_err_r[6][3] = 4.8
    coverage_f[6][3] = 5  # Too few hits
    coverage_r[6][3] = 8
    knock_f[6][3] = 0.0
    knock_r[6][3] = 0.0
    hp_grid[6][3] = 105.0
    
    return {
        'afr_err_f': afr_err_f,
        'afr_err_r': afr_err_r,
        'spark_f': spark_f,
        'spark_r': spark_r,
        'coverage_f': coverage_f,
        'coverage_r': coverage_r,
        'knock_f': knock_f,
        'knock_r': knock_r,
        'hp_grid': hp_grid,
    }


def test_power_opportunities():
    """Test the find_power_opportunities function."""
    print("Testing Find Me Power analysis feature...")
    print("=" * 60)
    
    # Create test data
    test_data = create_test_grids()
    
    # Run analysis
    opportunities = find_power_opportunities(**test_data)
    
    # Display results
    print(f"\nFound {len(opportunities)} power opportunities:\n")
    
    for i, opp in enumerate(opportunities, 1):
        print(f"{i}. {opp['type']}")
        print(f"   Location: {opp['rpm']} RPM @ {opp['kpa']} kPa")
        print(f"   Suggestion: {opp['suggestion']}")
        print(f"   Estimated Gain: {opp['estimated_gain_hp']:.2f} HP")
        print(f"   Confidence: {opp['confidence']}%")
        print(f"   Coverage: {opp['coverage']} hits")
        if opp['current_hp']:
            print(f"   Current HP: {opp['current_hp']} HP")
        print(f"   Details: {opp['details']}")
        print()
    
    # Validation checks
    print("=" * 60)
    print("Validation Checks:")
    print("=" * 60)
    
    # Check 1: Should find opportunities for scenarios 1, 2, and 3
    if len(opportunities) >= 3:
        print("[PASS] Found expected number of opportunities (>= 3)")
    else:
        print(f"[FAIL] Expected >= 3 opportunities, found {len(opportunities)}")
    
    # Check 2: Should NOT suggest changes for knock scenario (RPM 4500)
    knock_suggestions = [o for o in opportunities if o['rpm'] == 4500]
    if len(knock_suggestions) == 0:
        print("[PASS] Correctly avoided suggesting changes where knock detected")
    else:
        print(f"[FAIL] Should not suggest changes for cells with knock")
    
    # Check 3: Should NOT suggest changes for low coverage scenario (RPM 5000)
    low_coverage_suggestions = [o for o in opportunities if o['rpm'] == 5000]
    if len(low_coverage_suggestions) == 0:
        print("[PASS] Correctly avoided suggesting changes for low coverage cells")
    else:
        print(f"[FAIL] Should not suggest changes for cells with low coverage")
    
    # Check 4: All suggestions should have positive estimated gains
    all_positive = all(o['estimated_gain_hp'] > 0 for o in opportunities)
    if all_positive:
        print("[PASS] All opportunities have positive estimated HP gains")
    else:
        print("[FAIL] Some opportunities have non-positive HP gains")
    
    # Check 5: Check for combined opportunities
    combined_opps = [o for o in opportunities if o['type'] == 'Combined (AFR + Timing)']
    if len(combined_opps) > 0:
        print(f"[PASS] Found {len(combined_opps)} combined opportunities")
    else:
        print("[FAIL] No combined opportunities found (expected at least 1)")
    
    # Check 6: Verify safety limits
    unsafe_suggestions = []
    for opp in opportunities:
        details = opp['details']
        if 'suggested_afr_change_pct' in details:
            if abs(details['suggested_afr_change_pct']) > 3.0:
                unsafe_suggestions.append(f"AFR change > 3% at {opp['rpm']} RPM")
        if 'advance_deg' in details:
            if details['advance_deg'] > 2.0:
                unsafe_suggestions.append(f"Timing advance > 2° at {opp['rpm']} RPM")
    
    if len(unsafe_suggestions) == 0:
        print("[PASS] All suggestions respect safety limits (+-3% AFR, +2deg timing)")
    else:
        print(f"[FAIL] Found unsafe suggestions: {unsafe_suggestions}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    
    return len(opportunities) > 0


if __name__ == "__main__":
    success = test_power_opportunities()
    sys.exit(0 if success else 1)

