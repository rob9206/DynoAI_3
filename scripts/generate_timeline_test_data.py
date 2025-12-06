#!/usr/bin/env python3
"""
Generate comprehensive timeline test data with realistic VE tuning scenarios.

Creates a complete tuning session with:
- Baseline VE table
- Multiple analysis passes (progressively refining)
- Apply operations (with before/after snapshots)
- Rollback operations (demonstrating undo)

This simulates a real dyno tuning session workflow.
"""

import csv
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.session_logger import SessionLogger


def generate_baseline_ve_table(output_path: Path) -> None:
    """Generate a realistic baseline VE table."""
    rpm_bins = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
    kpa_bins = [30, 40, 50, 60, 70, 80, 90, 100]
    
    # Typical VE values - lower at low RPM/MAP, higher in the middle
    ve_data = []
    for rpm in rpm_bins:
        row = []
        for kpa in kpa_bins:
            # Base VE calculation (simplified)
            base = 85.0
            rpm_factor = (rpm - 1500) / 3500 * 15  # Increase with RPM
            kpa_factor = (kpa - 30) / 70 * 10      # Increase with load
            ve = base + rpm_factor + kpa_factor + random.uniform(-2, 2)
            row.append(round(ve, 2))
        ve_data.append(row)
    
    # Write CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['RPM'] + kpa_bins)
        for rpm, row in zip(rpm_bins, ve_data):
            writer.writerow([rpm] + row)
    
    print(f"[+] Generated baseline VE table: {output_path}")


def generate_correction_table(
    output_path: Path,
    scenario: str = "initial",
    severity: float = 1.0
) -> None:
    """
    Generate VE correction factors based on scenario.
    
    Args:
        output_path: Where to save corrections
        scenario: Type of corrections (initial, refined, problematic)
        severity: Multiplier for correction magnitude
    """
    rpm_bins = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
    kpa_bins = [30, 40, 50, 60, 70, 80, 90, 100]
    
    corrections = []
    
    if scenario == "initial":
        # Large corrections needed across the board
        for i, rpm in enumerate(rpm_bins):
            row = []
            for j, kpa in enumerate(kpa_bins):
                # More corrections needed at high load
                base_correction = (kpa - 30) / 70 * 6 * severity
                # Add some variation
                correction = base_correction + random.uniform(-2, 2)
                correction = max(-7, min(7, correction))  # Clamp to ±7%
                row.append(round(correction, 2))
            corrections.append(row)
    
    elif scenario == "refined":
        # Smaller corrections - tuning is getting close
        for i, rpm in enumerate(rpm_bins):
            row = []
            for j, kpa in enumerate(kpa_bins):
                # Small adjustments
                correction = random.uniform(-2, 2) * severity
                correction = max(-7, min(7, correction))
                row.append(round(correction, 2))
            corrections.append(row)
    
    elif scenario == "problematic":
        # Hot spots indicating issues in specific areas
        for i, rpm in enumerate(rpm_bins):
            row = []
            for j, kpa in enumerate(kpa_bins):
                # Problem area at mid-range RPM and high load
                if 2 <= i <= 4 and j >= 5:
                    correction = random.uniform(-5, -3) * severity  # Running rich
                else:
                    correction = random.uniform(-1, 1) * severity
                correction = max(-7, min(7, correction))
                row.append(round(correction, 2))
            corrections.append(row)
    
    elif scenario == "final":
        # Very small corrections - tune is dialed in
        for i, rpm in enumerate(rpm_bins):
            row = []
            for j, kpa in enumerate(kpa_bins):
                correction = random.uniform(-0.5, 0.5) * severity
                correction = max(-7, min(7, correction))
                row.append(round(correction, 2))
            corrections.append(row)
    
    # Write CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['RPM'] + kpa_bins)
        for rpm, row in zip(rpm_bins, corrections):
            formatted_row = [f"{val:+.2f}" if val != 0 else "0.00" for val in row]
            writer.writerow([rpm] + formatted_row)
    
    print(f"[+] Generated {scenario} corrections: {output_path}")


def apply_corrections(
    base_path: Path,
    corrections_path: Path,
    output_path: Path
) -> None:
    """Apply corrections to base VE table."""
    # Read base
    with open(base_path, newline='') as f:
        reader = csv.reader(f)
        base_rows = list(reader)
    
    # Read corrections
    with open(corrections_path, newline='') as f:
        reader = csv.reader(f)
        corr_rows = list(reader)
    
    # Apply
    result_rows = [base_rows[0]]  # Header
    for i in range(1, len(base_rows)):
        rpm = base_rows[i][0]
        result_row = [rpm]
        
        for j in range(1, len(base_rows[i])):
            base_val = float(base_rows[i][j])
            corr_val = float(corr_rows[i][j].replace('+', ''))
            
            # Apply: new_ve = base_ve * (1 + correction/100)
            new_val = base_val * (1 + corr_val / 100)
            result_row.append(f"{new_val:.2f}")
        
        result_rows.append(result_row)
    
    # Write
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(result_rows)
    
    print(f"[+] Applied corrections: {output_path}")


def create_comprehensive_timeline(run_id: str = None) -> Path:
    """
    Create a comprehensive timeline with a realistic tuning session.
    
    Simulates:
    1. Baseline VE table
    2. First dyno pull - large corrections needed
    3. Apply corrections
    4. Second pull - refinement needed
    5. Apply refinement
    6. Third pull - problem detected
    7. Rollback to previous good state
    8. Fourth pull with fix - final tune
    9. Apply final corrections
    """
    # Create run directory
    if run_id is None:
        run_id = f"run_timeline_demo_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    run_dir = Path("runs") / run_id
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 60)
    print(f"Creating comprehensive timeline: {run_id}")
    print("=" * 60)
    
    # Initialize session logger
    logger = SessionLogger(run_dir)
    
    # Step 1: Baseline VE table
    print("\n[Step 1] Creating baseline VE table...")
    baseline_path = output_dir / "VE_Baseline.csv"
    generate_baseline_ve_table(baseline_path)
    logger.record_baseline(
        ve_path=baseline_path,
        description="Initial baseline VE table loaded from ECM"
    )
    
    # Step 2: First analysis - large corrections needed
    print("\n[Step 2] First dyno pull - initial corrections...")
    corrections_1 = output_dir / "VE_Corrections_Pass1.csv"
    generate_correction_table(corrections_1, scenario="initial", severity=1.0)
    logger.record_analysis(
        correction_path=corrections_1,
        manifest={
            "stats": {"rows_read": 1500, "front_accepted": 45, "rear_accepted": 43},
            "config": {"args": {"clamp": 7, "smooth_passes": 2}}
        },
        description="First dyno pull: Initial tune analysis (baseline)"
    )
    
    # Step 3: Apply first corrections
    print("\n[Step 3] Applying first round of corrections...")
    ve_applied_1 = output_dir / "VE_Applied_Pass1.csv"
    apply_corrections(baseline_path, corrections_1, ve_applied_1)
    logger.record_apply(
        ve_before_path=baseline_path,
        ve_after_path=ve_applied_1,
        apply_metadata={
            "max_adjust_pct": 7.0,
            "cells_modified": 52,
            "applied_at_utc": datetime.now(timezone.utc).isoformat()
        },
        description="Applied initial corrections (±7% clamp)"
    )
    
    # Step 4: Second analysis - refinement
    print("\n[Step 4] Second dyno pull - refinement...")
    corrections_2 = output_dir / "VE_Corrections_Pass2.csv"
    generate_correction_table(corrections_2, scenario="refined", severity=0.6)
    logger.record_analysis(
        correction_path=corrections_2,
        manifest={
            "stats": {"rows_read": 1450, "front_accepted": 38, "rear_accepted": 36},
            "config": {"args": {"clamp": 5, "smooth_passes": 3}}
        },
        description="Second pull: Refinement pass (tighter clamp)"
    )
    
    # Step 5: Apply refinement
    print("\n[Step 5] Applying refinement corrections...")
    ve_applied_2 = output_dir / "VE_Applied_Pass2.csv"
    apply_corrections(ve_applied_1, corrections_2, ve_applied_2)
    logger.record_apply(
        ve_before_path=ve_applied_1,
        ve_after_path=ve_applied_2,
        apply_metadata={
            "max_adjust_pct": 5.0,
            "cells_modified": 34,
            "applied_at_utc": datetime.now(timezone.utc).isoformat()
        },
        description="Applied refinement corrections (±5% clamp)"
    )
    
    # Step 6: Third analysis - problem detected
    print("\n[Step 6] Third dyno pull - problem area detected...")
    corrections_3 = output_dir / "VE_Corrections_Pass3.csv"
    generate_correction_table(corrections_3, scenario="problematic", severity=1.2)
    logger.record_analysis(
        correction_path=corrections_3,
        manifest={
            "stats": {"rows_read": 1520, "front_accepted": 42, "rear_accepted": 40},
            "config": {"args": {"clamp": 7, "smooth_passes": 2}}
        },
        description="Third pull: Problem detected in mid-range/high load area"
    )
    
    # Step 7: Rollback - revert to previous good state
    print("\n[Step 7] Rolling back to previous good tune...")
    ve_rolled_back = output_dir / "VE_Rolled_Back.csv"
    shutil.copy2(ve_applied_1, ve_rolled_back)  # Go back to first apply
    logger.record_rollback(
        ve_before_path=ve_applied_2,
        ve_after_path=ve_rolled_back,
        rollback_info={
            "rolled_back_at_utc": datetime.now(timezone.utc).isoformat(),
            "original_apply_metadata": {"applied_at_utc": "2025-12-05T20:00:00Z"}
        },
        description="Rolled back to Pass 1: investigating mid-range issue"
    )
    
    # Step 8: Fourth analysis - corrected approach
    print("\n[Step 8] Fourth dyno pull - problem resolved...")
    corrections_4 = output_dir / "VE_Corrections_Pass4.csv"
    generate_correction_table(corrections_4, scenario="refined", severity=0.8)
    logger.record_analysis(
        correction_path=corrections_4,
        manifest={
            "stats": {"rows_read": 1480, "front_accepted": 40, "rear_accepted": 38},
            "config": {"args": {"clamp": 6, "smooth_passes": 2}}
        },
        description="Fourth pull: Problem resolved, smoother corrections"
    )
    
    # Step 9: Apply final corrections
    print("\n[Step 9] Applying final corrections...")
    ve_final = output_dir / "VE_Final.csv"
    apply_corrections(ve_rolled_back, corrections_4, ve_final)
    logger.record_apply(
        ve_before_path=ve_rolled_back,
        ve_after_path=ve_final,
        apply_metadata={
            "max_adjust_pct": 6.0,
            "cells_modified": 36,
            "applied_at_utc": datetime.now(timezone.utc).isoformat()
        },
        description="Applied final corrections after problem resolution"
    )
    
    # Step 10: Final verification pull
    print("\n[Step 10] Final verification pull...")
    corrections_5 = output_dir / "VE_Corrections_Final.csv"
    generate_correction_table(corrections_5, scenario="final", severity=0.3)
    logger.record_analysis(
        correction_path=corrections_5,
        manifest={
            "stats": {"rows_read": 1460, "front_accepted": 25, "rear_accepted": 23},
            "config": {"args": {"clamp": 3, "smooth_passes": 4}}
        },
        description="Final verification: Tune dialed in, minimal corrections needed"
    )
    
    # Create run_state.json for UI compatibility
    run_state = {
        "run_id": run_id,
        "status": "complete",
        "source": "timeline_demo",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(run_dir / "run_state.json", 'w') as f:
        json.dump(run_state, f, indent=2)
    
    # Print summary
    summary = logger.get_session_summary()
    timeline = logger.get_timeline()
    
    print("\n" + "=" * 60)
    print("✅ COMPREHENSIVE TIMELINE CREATED!")
    print("=" * 60)
    print(f"\nRun ID: {run_id}")
    print(f"Total Events: {summary['total_events']}")
    print(f"  - Baseline: {summary['event_counts']['baseline']}")
    print(f"  - Analysis: {summary['event_counts']['analysis']}")
    print(f"  - Apply: {summary['event_counts']['apply']}")
    print(f"  - Rollback: {summary['event_counts']['rollback']}")
    
    print("\n📜 Timeline Events:")
    for i, event in enumerate(timeline, 1):
        print(f"  {i}. [{event['type'].upper()}] {event['description']}")
    
    print(f"\n📁 Files created:")
    print(f"  - Session log: {run_dir / 'session_log.json'}")
    print(f"  - Snapshots: {run_dir / 'snapshots'} ({len(list((run_dir / 'snapshots').glob('*.csv')))} files)")
    print(f"  - Output files: {output_dir} ({len(list(output_dir.glob('*.csv')))} files)")
    
    print("\n🚀 Access the Time Machine:")
    print(f"  http://localhost:5000/time-machine/{run_id}")
    print("\n" + "=" * 60)
    
    return run_dir


def main():
    # Allow custom run_id from command line
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("\n🎬 Generating Comprehensive Timeline Test Data")
    print("This will simulate a complete dyno tuning session with:")
    print("  - Initial baseline")
    print("  - Multiple analysis passes")
    print("  - Apply operations")
    print("  - A rollback (problem detected)")
    print("  - Final refinement")
    print("\nThis takes about 5 seconds...\n")
    
    run_dir = create_comprehensive_timeline(run_id)
    
    print("\n✨ You can now explore this rich timeline in the Time Machine!")
    print("   It demonstrates all the key features:")
    print("   - Progressive refinement")
    print("   - Problem detection and rollback")
    print("   - Apply operations with before/after snapshots")
    print("   - Multiple comparison points")


if __name__ == "__main__":
    main()

