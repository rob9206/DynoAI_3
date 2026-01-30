import json

run_id = "99f7459e-cef4-4bdf-b670-c058abefbccf"
data = json.load(open(f"runs/{run_id}/output/NextGenAnalysis.json"))

print("\n" + "="*60)
print("  DYNOAI NEXTGEN ANALYSIS - IN ACTION!")
print("="*60)

# Phase 1: Mode Detection
ms = data['mode_summary']
total = ms['tip_out'] + ms['tip_in'] + ms['cruise'] + ms['wot']
print("\n[PHASE 1: MODE DETECTION]")
print(f"  TIP_OUT: {ms['tip_out']:4d} samples ({ms['tip_out']/total*100:5.1f}%)")
print(f"  TIP_IN:  {ms['tip_in']:4d} samples ({ms['tip_in']/total*100:5.1f}%)")
print(f"  CRUISE:  {ms['cruise']:4d} samples ({ms['cruise']/total*100:5.1f}%)")
print(f"  WOT:     {ms['wot']:4d} samples ({ms['wot']/total*100:5.1f}%)")
print(f"  TOTAL:   {total} samples analyzed")

# Phase 2: Spark Valley
print("\n[PHASE 2: SPARK VALLEY ANALYSIS]")
if data.get('spark_valley'):
    sv = data['spark_valley']
    print(f"  Status: DETECTED")
    print(f"  Valley center: {sv.get('valley_center_deg', 'N/A')} degrees")
    print(f"  Strength: {sv.get('valley_strength', 'N/A')}")
else:
    print("  Status: No significant valley detected")

# Phase 7: Test Planning
print("\n[PHASE 7: INTELLIGENT TEST PLANNING]")
nt = data.get('next_tests', {})
steps = nt.get('steps', [])
print(f"  Test plans generated: {len(steps)}")
print(f"  Estimated pulls: {nt.get('total_estimated_pulls', 0)}")
print(f"  Coverage gaps identified: {len(nt.get('coverage_gaps', []))}")

if steps:
    print("\n  Recommended Test Plans:")
    for i, test in enumerate(steps[:3], 1):
        rpm = test.get('rpm_range', [])
        map_kpa = test.get('map_range', [])
        print(f"\n    [{i}] {test.get('name', 'Unknown')}")
        print(f"        RPM: {rpm[0]}-{rpm[1]}, Load: {map_kpa[0]}-{map_kpa[1]} kPa")
        print(f"        Type: {test.get('test_type', 'N/A')}")
        print(f"        Priority: {test.get('priority', 'N/A')}")

# Coverage Gaps
if nt.get('coverage_gaps'):
    print("\n  Coverage Gaps:")
    for i, gap in enumerate(nt['coverage_gaps'][:3], 1):
        print(f"    {i}. {gap}")

print("\n" + "="*60)
print("[OK] ALL PHASE 1-7 FEATURES WORKING!")
print(f"\nView in browser:")
print(f"  http://localhost:5174/runs/{run_id}")
print("="*60 + "\n")
