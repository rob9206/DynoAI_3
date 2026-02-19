"""
Showcase Antigravity: DynoAI v3 AI Tuning Demo
==============================================

This script demonstrates the "Agency" of the DynoAI system. It acts as an
autonomous tuner that:
1.  Analyzes the current engine state (via GP Surrogate).
2.  Plans the next optimal test (via Pull Advisor).
3.  Executes the test (via DynoSimulator).
4.  Learns from the result (Uncertainty Reduction).
5.  Repeats until converged.

Usage:
    python scripts/showcase_antigravity.py
"""

import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from api.services.v3_session_service import (
    create_session,
    simulate_pull,
    suggest_next_pull,
    check_convergence,
    get_uncertainty_map,
)

import numpy as np

# Configure logging to suppress library noise
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("Showcase")


def bar(value, max_val, width=30):
    """Render a simple ASCII progress bar."""
    filled = int(width * min(value, max_val) / max_val)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def main():
    print("\n" + "=" * 65)
    print("  ANTIGRAVITY SHOWCASE: DynoAI v3 Autonomous Tuning Demo")
    print("=" * 65)
    print()
    print("  Engine:  Milwaukee-Eight 114ci (M8 114)")
    print("  Grid:    11 RPM bins x 8 MAP bins = 88 cells")
    print("  AI:      Gaussian Process Surrogate + Bayesian Active Learning")
    print("  Goal:    Map the VE surface using minimal, optimally-placed pulls")
    print()
    print("-" * 65)

    config = {
        "engine_family": "m8_114",
        "rpm_bins": [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
        "map_bins": [30, 40, 50, 60, 70, 80, 90, 100],
    }

    # Step 1: Create the session
    print("\n[1/3] INITIALIZING AI SESSION...")
    session_data = create_session(config)
    session_id = session_data["session_id"]
    print(f"      Session ID:       {session_id}")
    print(f"      Engine Family:    {session_data['engine_family']}")
    print(f"      Est. Pulls Needed: {session_data['estimated_pulls']}")

    if session_data.get("initial_plan"):
        plan = session_data["initial_plan"]
        print(f"      Initial Plan:     {len(plan)} pull(s) pre-planned")
        for p in plan[:3]:
            mode = p.get("pull_mode", "acceleration")
            print(f"        -> #{p['pull_number']}: {p['rpm']:.0f} RPM / {p['map_kpa']:.0f} kPa ({mode})")
        if len(plan) > 3:
            print(f"        ... and {len(plan) - 3} more")

    # Step 2: Run the active learning loop
    max_pulls = 8
    print(f"\n[2/3] AUTONOMOUS ACTIVE LEARNING LOOP ({max_pulls} pulls)")
    print("-" * 65)

    for i in range(1, max_pulls + 1):
        # A. Ask the AI what to do
        rec = suggest_next_pull(session_id)
        target_rpm = rec["rpm"]
        target_map = rec["map_kpa"]
        pull_type = rec.get("pull_type", "unknown")
        pull_mode = rec.get("pull_mode", "acceleration")
        info_gain = rec.get("expected_info_gain", 0)
        reason = rec.get("reason", "")

        print(f"\n  Pull #{i}")
        print(f"  AI Reasoning:  \"{reason}\"")
        print(f"  Target:        {target_rpm:.0f} RPM / {target_map:.0f} kPa")
        print(f"  Type:          {pull_type} ({pull_mode})")
        print(f"  Info Gain:     {info_gain:.3f}")

        # B. Execute the pull (synthetic simulation)
        result = simulate_pull(session_id, rpm=target_rpm, map_kpa=target_map)
        obs_added = result.get("observations_added", 0)

        # C. Check convergence
        conv = result.get("convergence", {})
        if conv:
            total = conv.get("total_cells", 88)
            above = conv.get("cells_above_threshold", 0)
            converged_pct = ((total - above) / total) * 100 if total > 0 else 0
            mean_unc = conv.get("mean_uncertainty", 10.0)
            pulls_remaining = conv.get("estimated_pulls_remaining", "?")

            print(f"  Observations:  {obs_added} accepted")
            print(f"  Convergence:   {converged_pct:.0f}%  {bar(converged_pct, 100)}")
            print(f"  Mean Sigma:    {mean_unc:.4f}")
            print(f"  Est. Remaining: ~{pulls_remaining} pull(s)")

            if conv.get("converged", False):
                print(f"\n  *** MODEL CONVERGED after {i} pulls! ***")
                break

        # Show alternatives
        alts = rec.get("alternatives", [])
        if alts:
            alt_strs = [f"{a['rpm']:.0f}/{a['map_kpa']:.0f}" for a in alts[:2]]
            print(f"  Alternatives:  {', '.join(alt_strs)}")

        time.sleep(0.3)

    # Step 3: Final Summary
    print("\n" + "=" * 65)
    print("  FINAL RESULTS")
    print("=" * 65)

    final_conv = check_convergence(session_id)
    total = final_conv.get("total_cells", 88)
    above = final_conv.get("cells_above_threshold", 0)
    converged_pct = ((total - above) / total) * 100 if total > 0 else 0
    mean_unc = final_conv.get("mean_uncertainty", 0)

    print(f"\n  Pulls Executed:    {min(i, max_pulls)}")
    print(f"  Cells Converged:   {total - above} / {total} ({converged_pct:.0f}%)")
    print(f"  Mean Uncertainty:  {mean_unc:.4f} sigma")
    print(f"  Converged:         {'YES' if final_conv.get('converged') else 'NO'}")

    # Show a snippet of the predicted VE map
    try:
        unc_data = get_uncertainty_map(session_id)
        ve_map = np.array(unc_data["ve_map"])
        unc_map = np.array(unc_data["uncertainty_map"])
        rpm_bins = unc_data["rpm_bins"]
        map_bins = unc_data["map_bins"]

        print(f"\n  Predicted VE Surface (sample):")
        print(f"  {'RPM':>6s}", end="")
        for m in map_bins[:5]:
            print(f"  {m:>5.0f}kPa", end="")
        print()
        for r_idx in range(0, len(rpm_bins), 2):
            print(f"  {rpm_bins[r_idx]:>6.0f}", end="")
            for m_idx in range(min(5, len(map_bins))):
                print(f"  {ve_map[r_idx][m_idx]:>7.1f}%", end="")
            print()

        print(f"\n  Uncertainty Map (sample, lower=better):")
        print(f"  {'RPM':>6s}", end="")
        for m in map_bins[:5]:
            print(f"  {m:>5.0f}kPa", end="")
        print()
        for r_idx in range(0, len(rpm_bins), 2):
            print(f"  {rpm_bins[r_idx]:>6.0f}", end="")
            for m_idx in range(min(5, len(map_bins))):
                print(f"  {unc_map[r_idx][m_idx]:>8.3f}", end="")
            print()
    except Exception as e:
        print(f"  (Could not display VE map: {e})")

    print(f"\n  Session ID: {session_id}")
    print(f"  Predict Time: {unc_data.get('predict_time_ms', 0):.1f} ms")
    print()
    print("  Antigravity: Autonomous agency demonstrated successfully.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
