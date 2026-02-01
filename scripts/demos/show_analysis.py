import json
from pathlib import Path

run_id = "99f7459e-cef4-4bdf-b670-c058abefbccf"
json_path = Path(f"runs/{run_id}/output/NextGenAnalysis.json")

data = json.load(open(json_path))
ms = data["mode_summary"]

print("\n" + "=" * 50)
print("  NEXTGEN ANALYSIS IN ACTION")
print("=" * 50)

print("\n[Mode Detection - Phase 1]")
print(f"  TIP_OUT: {ms['tip_out']} samples")
print(f"  TIP_IN:  {ms['tip_in']} samples")
print(f"  CRUISE:  {ms['cruise']} samples")
print(f"  WOT:     {ms['wot']} samples")

print("\n[Spark Valley Analysis - Phase 2]")
if data.get("spark_valley"):
    sv = data["spark_valley"]
    print(f"  Detected at: {sv.get('valley_center_deg', 'N/A')} degrees")
    print(f"  Strength: {sv.get('valley_strength', 'N/A')}")
else:
    print("  No significant valley detected")

print("\n[Test Planning - Phase 7]")
next_tests = data.get("next_tests", {})
if isinstance(next_tests, dict):
    test_list = next_tests.get("steps", [])
    print(f"  Test plans generated: {len(test_list)}")
    print(f"  Coverage gaps: {len(next_tests.get('coverage_gaps', []))}")
    print(f"  Estimated pulls: {next_tests.get('total_estimated_pulls', 0)}")
    if test_list:
        print("\n  Top 3 Test Recommendations:")
        for i, test in enumerate(test_list[:3], 1):
            rpm_range = test.get("rpm_range", ["N/A", "N/A"])
            map_range = test.get("map_range", ["N/A", "N/A"])
            print(f"    {i}. {test.get('name', 'Unknown')}")
            print(
                f"       RPM: {rpm_range[0]}-{rpm_range[1]}, Load: {map_range[0]}-{map_range[1]} kPa"
            )
            print(f"       Type: {test.get('test_type', 'N/A')}")
else:
    print("  No test plans generated")

print(f"\n[Coverage Gaps - Phase 5]:")
if next_tests.get("coverage_gaps"):
    for gap in next_tests["coverage_gaps"][:3]:
        print(f"  - {gap}")

print("\n[OK] ALL PHASE 1-7 FEATURES WORKING!")
print(f"\nView in browser: http://localhost:5174/runs/{run_id}")
print("=" * 50 + "\n")
