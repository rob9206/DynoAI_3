import json

run_id = "1cec2696-1a56-4442-afbd-70f2e5309285"
data = json.load(open(f"runs/{run_id}/output/NextGenAnalysis.json"))

ms = data["mode_summary"]
nt = data["next_tests"]
total = ms["tip_out"] + ms["tip_in"] + ms["cruise"] + ms["wot"]

print("\n" + "=" * 60)
print("  LIVE NEXTGEN ANALYSIS - JUST GENERATED!")
print("=" * 60)

print(f"\nRun ID: {run_id}")
print(f"Samples Analyzed: {total:,}")

print(f"\n[MODE DETECTION - Phase 1]")
print(f"  TIP_OUT: {ms['tip_out']:4d} ({ms['tip_out'] / total * 100:5.1f}%)")
print(f"  TIP_IN:  {ms['tip_in']:4d} ({ms['tip_in'] / total * 100:5.1f}%)")
print(f"  CRUISE:  {ms['cruise']:4d} ({ms['cruise'] / total * 100:5.1f}%)")
print(f"  WOT:     {ms['wot']:4d} ({ms['wot'] / total * 100:5.1f}%)")

print(f"\n[TEST PLANNING - Phase 7]")
steps = nt.get("steps", [])
print(f"  Plans generated: {len(steps)}")
print(f"  Estimated pulls: {nt.get('total_estimated_pulls', 0)}")
print(f"  Coverage gaps: {len(nt.get('coverage_gaps', []))}")

if steps:
    print("\n  Top 3 Recommendations:")
    for i, test in enumerate(steps[:3], 1):
        rpm = test.get("rpm_range", [])
        map_kpa = test.get("map_range", [])
        print(f"\n    [{i}] {test.get('name', 'Unknown')}")
        print(f"        RPM: {rpm[0]}-{rpm[1]}, Load: {map_kpa[0]}-{map_kpa[1]} kPa")
        print(f"        Type: {test.get('test_type', 'N/A')}")

print("\n" + "=" * 60)
print("VIEW IN BROWSER NOW:")
print(f"http://localhost:5173/runs/{run_id}")
print("=" * 60 + "\n")
