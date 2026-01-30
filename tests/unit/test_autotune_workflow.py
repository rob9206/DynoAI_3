"""Test the auto-tune workflow with real Power Vision data."""

import sys
from pathlib import Path

from api.services.autotune_workflow import AutoTuneWorkflow
from api.services.powercore_integration import find_log_files

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_full_workflow():
    """Test the complete auto-tune workflow."""
    print("=== Testing Auto-Tune Workflow ===")
    print()

    # Find a log file
    logs = find_log_files()
    if not logs:
        print("No log files found - skipping test")
        return

    # Use the largest log file
    log_file = max(logs, key=lambda p: p.stat().st_size)
    print(f"Using log: {log_file.name} ({log_file.stat().st_size / 1024:.1f} KB)")
    print()

    # Create workflow
    workflow = AutoTuneWorkflow()

    # Run full workflow
    output_dir = "outputs/autotune_test"
    session = workflow.run_full_workflow(
        log_path=str(log_file),
        output_dir=output_dir,
    )

    # Print summary
    summary = workflow.get_session_summary(session)
    print("=== Session Summary ===")
    print(f"ID: {summary.get('run_id', 'N/A')}")
    print(f"Status: {summary.get('status', 'unknown')}")
    print()

    if "afr_analysis" in summary:
        afr = summary["afr_analysis"]
        print("AFR Analysis:")
        print(f"  Mean Error: {afr['mean_error_pct']}%")
        print(f"  Zones Lean: {afr['zones_lean']}")
        print(f"  Zones Rich: {afr['zones_rich']}")
        print(f"  Zones OK: {afr['zones_ok']}")
        print()

    if "ve_corrections" in summary:
        corr = summary["ve_corrections"]
        print("VE Corrections:")
        print(f"  Zones Adjusted: {corr['zones_adjusted']}")
        print(f"  Max Correction: {corr['max_correction_pct']}%")
        print(f"  Min Correction: {corr['min_correction_pct']}%")
        print(f"  Clipped Zones: {corr['clipped_zones']}")
        print()

    if summary.get("output_tunelab_script"):
        print(f"TuneLab Script: {summary['output_tunelab_script']}")
    if summary.get("output_pvv_file"):
        print(f"PVV File: {summary['output_pvv_file']}")

    if summary.get("errors"):
        print(f"Errors: {summary['errors']}")

    print()
    print("=== Workflow Test Complete ===")

    # Verify outputs exist
    if summary.get("output_tunelab_script"):
        assert Path(summary["output_tunelab_script"]).exists()
    if summary.get("output_pvv_file"):
        assert Path(summary["output_pvv_file"]).exists()


if __name__ == "__main__":
    test_full_workflow()
