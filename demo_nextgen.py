"""
Demo script to generate NextGen Analysis
"""

import os
import shutil
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from api.services.nextgen_workflow import NextGenWorkflow

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("=" * 70)
    print("  DynoAI NextGen Analysis Demo")
    print("=" * 70)
    print()

    # Create a test run
    print("[1/3] Creating test run...")
    test_csv = Path(__file__).parent / "tests" / "data" / "dense_dyno_test.csv"

    if not test_csv.exists():
        print(f"      ✗ Test file not found: {test_csv}")
        return

    print(f"      Using: {test_csv.name}")

    # Copy test file to runs directory
    run_id = f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    runs_dir = Path(__file__).parent / "runs" / run_id / "input"
    runs_dir.mkdir(parents=True, exist_ok=True)

    input_path = runs_dir / "dynoai_input.csv"
    shutil.copy(test_csv, input_path)
    print(f"      ✓ Created run: {run_id}")

    # Generate NextGen analysis
    print("\n[2/3] Generating NextGen Analysis...")
    print("      This includes:")
    print("        - Mode detection (7 driving modes)")
    print("        - Surface building (spark, AFR error, coverage)")
    print("        - Spark valley detection")
    print("        - Cause tree hypotheses")
    print("        - Coverage gap analysis")
    print("        - Predictive test planning with efficiency scores")
    print()

    try:
        workflow = NextGenWorkflow()
        result = workflow.generate_for_run(run_id, force=True)

        if result["success"]:
            print(f"      ✓ Analysis generated successfully!")

            payload_path = (Path(__file__).parent / "runs" / run_id /
                            "NextGenAnalysis.json")
            if payload_path.exists():
                import json

                with open(payload_path) as f:
                    data = json.load(f)

                print(f"\n      Quick Stats:")
                print(
                    f"        - Total samples: {data.get('inputs_present', {}).get('row_count', 'N/A')}"
                )
                print(f"        - Surfaces: {len(data.get('surfaces', {}))}")
                print(
                    f"        - Spark valleys found: {len(data.get('spark_valley', []))}"
                )
                print(
                    f"        - Hypotheses: {len(data.get('cause_tree', {}).get('hypotheses', []))}"
                )
                print(
                    f"        - Test plan steps: {len(data.get('next_tests', []))}"
                )
                print(
                    f"        - Coverage gaps: {len(data.get('coverage_gaps', []))}"
                )
        else:
            print(f"      ✗ Generation failed: {result.get('error')}")
            return
    except Exception as e:
        print(f"      ✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return

    # Open browser
    print("\n[3/3] Opening browser...")
    frontend_url = "http://localhost:5173"
    url = f"{frontend_url}/runs/{run_id}"
    print(f"      URL: {url}")

    time.sleep(1)
    try:
        webbrowser.open(url)
        print("      ✓ Browser opened!")
    except:
        print("      ℹ Could not auto-open browser")

    print("\n" + "=" * 70)
    print("  ✓ Demo Complete!")
    print("=" * 70)
    print()
    print("Open your browser to:")
    print(f"  {url}")
    print()
    print("What you'll see:")
    print("  • Mode Summary - Distribution of IDLE/CRUISE/WOT/TIP_IN/etc.")
    print("  • Coverage Gaps - Missing regions by priority")
    print("  • Spark Valley - Timing anomalies with confidence scores")
    print("  • Cause Tree - Ranked diagnostic hypotheses with evidence")
    print("  • Test Planner - Configure RPM/MAP/environment constraints")
    print("  • Target Heatmap - Visual guide showing which cells to hit next")
    print("  • Next Test Plan - Efficiency-scored suggestions (dyno + street)")
    print()
    print("Files created:")
    print(f"  runs/{run_id}/NextGenAnalysis.json       (full payload)")
    print(f"  runs/{run_id}/NextGenAnalysis_Meta.json  (metadata)")
    print()


if __name__ == "__main__":
    main()
