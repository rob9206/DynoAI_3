#!/usr/bin/env python3
"""
Seed demo timeline data for the VE Table Time Machine.

This script creates sample timeline events for an existing run,
allowing you to test the Time Machine feature immediately.

Usage:
    python scripts/seed_timeline_demo.py [run_id]

If no run_id is provided, it will use the first complete Jetstream run found.
"""

import json
import sys
from pathlib import Path

from api.services.session_logger import SessionLogger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def find_complete_run() -> Path | None:
    """Find the first complete run with VE correction data."""
    runs_dir = Path("runs")
    if not runs_dir.exists():
        return None

    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue

        state_file = run_dir / "run_state.json"
        ve_file = run_dir / "output" / "VE_Correction_Delta_DYNO.csv"

        if state_file.exists() and ve_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            if state.get("status") == "complete":
                return run_dir

    return None


def seed_timeline(run_dir: Path) -> None:
    """Create demo timeline events for a run."""
    print(f"[*] Seeding timeline for: {run_dir.name}")

    output_dir = run_dir / "output"
    ve_correction = output_dir / "VE_Correction_Delta_DYNO.csv"
    manifest_file = output_dir / "manifest.json"

    if not ve_correction.exists():
        print(f"[!] VE correction file not found: {ve_correction}")
        return

    # Load manifest if available
    manifest = {}
    if manifest_file.exists():
        with open(manifest_file) as f:
            manifest = json.load(f)

    # Create session logger
    logger = SessionLogger(run_dir)

    # Check if timeline already has events
    existing = logger.get_timeline()
    if existing:
        print(f"[!] Timeline already has {len(existing)} events. Skipping.")
        print("    To reset, delete: " + str(run_dir / "session_log.json"))
        return

    # Record the analysis event
    print("[+] Recording analysis event...")
    logger.record_analysis(
        correction_path=ve_correction,
        manifest=manifest,
        description="Generated VE corrections from dyno log analysis",
    )

    # Create a simulated "apply" by copying the correction as if it was applied
    # (In real use, this would happen when the user clicks Apply in the UI)

    # For demo purposes, let's simulate a second analysis with different results
    # by creating a modified copy of the VE corrections
    import csv
    import shutil
    from datetime import datetime, timezone

    # Create a "refined" version of corrections (simulate a second pass)
    ve_refined = output_dir / "VE_Correction_Refined.csv"
    if not ve_refined.exists():
        # Read original corrections
        with open(ve_correction, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Modify values slightly (simulate refinement)
        for i in range(1, len(rows)):
            for j in range(1, len(rows[i])):
                try:
                    val = float(rows[i][j].replace("+", "").replace("'", ""))
                    # Reduce corrections by 20% (refinement)
                    val = val * 0.8
                    rows[i][j] = f"{val:+.2f}" if val != 0 else "0.00"
                except (ValueError, IndexError):
                    pass

        # Write refined file
        with open(ve_refined, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    # Record the refinement as a second analysis
    print("[+] Recording refinement analysis event...")
    logger.record_analysis(
        correction_path=ve_refined,
        manifest={
            **manifest,
            "config": {
                "args": {"clamp": 5, "smooth_passes": 3},
            },
            "description": "Refined VE corrections with tighter clamping",
        },
        description="Refined VE corrections (tighter clamping, more smoothing)",
    )

    # Print summary
    timeline = logger.get_timeline()
    summary = logger.get_session_summary()

    print("\n" + "=" * 50)
    print("[OK] Timeline seeded successfully!")
    print("=" * 50)
    print(f"Run ID: {run_dir.name}")
    print(f"Events created: {summary['total_events']}")
    print(f"  - Analysis: {summary['event_counts']['analysis']}")
    print(f"  - Apply: {summary['event_counts']['apply']}")
    print(f"  - Rollback: {summary['event_counts']['rollback']}")
    print(f"\nSession log: {run_dir / 'session_log.json'}")
    print(f"Snapshots: {run_dir / 'snapshots'}")
    print("\nYou can now:")
    print(f"  1. Start the web app: .\\start-web.ps1")
    print(f"  2. Navigate to: http://localhost:5000/time-machine/{run_dir.name}")


def main():
    # Get run_id from command line or find one automatically
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
        run_dir = Path("runs") / run_id
        if not run_dir.exists():
            print(f"[!] Run not found: {run_dir}")
            sys.exit(1)
    else:
        print("[*] No run_id provided, searching for a complete run...")
        run_dir = find_complete_run()
        if not run_dir:
            print("[!] No complete runs found in runs/ directory")
            print("    Run some analysis first or provide a run_id")
            sys.exit(1)

    seed_timeline(run_dir)


if __name__ == "__main__":
    main()
