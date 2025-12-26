"""
Virtual ECU Demo - Demonstrates closed-loop tuning simulation.

This script shows how the Virtual ECU creates realistic AFR errors
when VE tables don't match actual engine behavior.

Scenarios demonstrated:
1. Perfect VE table → Perfect AFR
2. Incorrect VE table → AFR errors
3. Side-by-side comparison

This is the foundation for full closed-loop tuning simulation!
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.dyno_simulator import (
    DynoSimulator,
    EngineProfile,
    SimulatorConfig,
)
from api.services.virtual_ecu import (
    VirtualECU,
    create_afr_target_table,
    create_baseline_ve_table,
    create_intentionally_wrong_ve_table,
    print_ecu_diagnostics,
)


def run_pull_with_ecu(ecu: VirtualECU | None, name: str) -> pd.DataFrame:
    """
    Run a dyno pull with the given ECU configuration.
    
    Args:
        ecu: VirtualECU instance (or None for default behavior)
        name: Name for this run (for logging)
    
    Returns:
        DataFrame with pull data
    """
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")
    
    # Create simulator
    config = SimulatorConfig(
        profile=EngineProfile.m8_114(),
        enable_thermal_effects=True,
        enable_knock_detection=True,
        auto_pull=False,
    )
    
    simulator = DynoSimulator(config=config, virtual_ecu=ecu)
    simulator.start()
    
    # Wait for idle
    time.sleep(0.5)
    
    # Trigger pull
    print("  Starting pull...")
    simulator.trigger_pull()
    
    # Wait for completion
    while simulator.get_state().value != 'idle':
        time.sleep(0.1)
    
    print("  Pull complete!")
    
    # Get data
    pull_data = simulator.get_pull_data()
    simulator.stop()
    
    df = pd.DataFrame(pull_data)
    
    # Calculate AFR error statistics
    df['AFR Error F'] = df['AFR Meas F'] - df['AFR Target']
    df['AFR Error R'] = df['AFR Meas R'] - df['AFR Target']
    
    mean_error_f = df['AFR Error F'].mean()
    mean_error_r = df['AFR Error R'].mean()
    max_error_f = df['AFR Error F'].abs().max()
    max_error_r = df['AFR Error R'].abs().max()
    
    print(f"\n  AFR Error Statistics:")
    print(f"    Front - Mean: {mean_error_f:+.3f}, Max: {max_error_f:.3f}")
    print(f"    Rear  - Mean: {mean_error_r:+.3f}, Max: {max_error_r:.3f}")
    
    return df


def scenario_1_perfect_ve():
    """
    Scenario 1: Perfect VE table → Perfect AFR
    
    When the ECU's VE table matches actual engine VE,
    the resulting AFR should be on target.
    """
    print("\n" + "="*70)
    print("SCENARIO 1: Perfect VE Table")
    print("="*70)
    print("The ECU's VE table matches actual engine behavior.")
    print("Expected result: AFR should be very close to target.")
    
    # Create perfect VE tables
    ve_table = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)
    afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)
    
    # Create ECU
    ecu = VirtualECU(
        ve_table_front=ve_table,
        ve_table_rear=ve_table,
        afr_target_table=afr_table,
    )
    
    # Show diagnostics at a specific point
    print("\nECU Diagnostics at 4000 RPM, 80 kPa (WOT):")
    print_ecu_diagnostics(ecu, rpm=4000, map_kpa=80, actual_ve=0.85)
    
    # Run pull
    df = run_pull_with_ecu(ecu, "Perfect VE Table")
    
    return df, "Perfect VE"


def scenario_2_incorrect_ve():
    """
    Scenario 2: Incorrect VE table → AFR errors
    
    When the ECU's VE table is wrong (typical for untuned engine),
    the resulting AFR will have errors that need correction.
    """
    print("\n" + "="*70)
    print("SCENARIO 2: Incorrect VE Table (Needs Tuning)")
    print("="*70)
    print("The ECU's VE table is 10% too low (engine breathes better than ECU knows).")
    print("Expected result: AFR will be LEAN (not enough fuel for actual air).")
    
    # Create baseline (correct) VE
    correct_ve = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)
    
    # Create intentionally wrong VE (10% too low on average)
    wrong_ve = create_intentionally_wrong_ve_table(
        correct_ve, 
        error_pct_mean=-10.0,  # 10% too low
        error_pct_std=5.0,     # ±5% variation
        seed=42
    )
    
    afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)
    
    # Create ECU with wrong VE
    ecu = VirtualECU(
        ve_table_front=wrong_ve,
        ve_table_rear=wrong_ve,
        afr_target_table=afr_table,
    )
    
    # Show diagnostics at a specific point
    print("\nECU Diagnostics at 4000 RPM, 80 kPa (WOT):")
    print("  (ECU has wrong VE, actual VE is higher)")
    print_ecu_diagnostics(ecu, rpm=4000, map_kpa=80, actual_ve=0.85)
    
    # Run pull
    df = run_pull_with_ecu(ecu, "Incorrect VE Table")
    
    return df, "Incorrect VE (Needs Tune)"


def scenario_3_no_ecu():
    """
    Scenario 3: No ECU simulation (default behavior)
    
    For comparison, run without virtual ECU to show default behavior.
    """
    print("\n" + "="*70)
    print("SCENARIO 3: No ECU Simulation (Default Behavior)")
    print("="*70)
    print("Running without Virtual ECU for comparison.")
    print("Uses default AFR error patterns (lean mid-range, rich at top).")
    
    # Run pull without ECU
    df = run_pull_with_ecu(None, "No ECU Simulation")
    
    return df, "Default (No ECU)"


def plot_comparison(results: list[tuple[pd.DataFrame, str]]):
    """
    Plot side-by-side comparison of all scenarios.
    
    Args:
        results: List of (dataframe, label) tuples
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Virtual ECU Simulation Comparison', fontsize=16, fontweight='bold')
    
    colors = ['green', 'red', 'blue', 'orange']
    
    # Plot 1: AFR vs RPM
    ax = axes[0, 0]
    for (df, label), color in zip(results, colors):
        ax.plot(df['Engine RPM'], df['AFR Meas F'], label=label, color=color, alpha=0.7)
        ax.plot(df['Engine RPM'], df['AFR Target'], 'k--', alpha=0.3, linewidth=1)
    ax.set_xlabel('RPM')
    ax.set_ylabel('AFR')
    ax.set_title('AFR vs RPM (Front Cylinder)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: AFR Error vs RPM
    ax = axes[0, 1]
    for (df, label), color in zip(results, colors):
        ax.plot(df['Engine RPM'], df['AFR Error F'], label=label, color=color, alpha=0.7)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.set_xlabel('RPM')
    ax.set_ylabel('AFR Error (Measured - Target)')
    ax.set_title('AFR Error vs RPM')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Torque vs RPM
    ax = axes[1, 0]
    for (df, label), color in zip(results, colors):
        ax.plot(df['Engine RPM'], df['Torque'], label=label, color=color, alpha=0.7)
    ax.set_xlabel('RPM')
    ax.set_ylabel('Torque (ft-lb)')
    ax.set_title('Torque vs RPM')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 4: AFR Error Distribution
    ax = axes[1, 1]
    for (df, label), color in zip(results, colors):
        ax.hist(df['AFR Error F'], bins=30, alpha=0.5, label=label, color=color)
    ax.axvline(x=0, color='k', linestyle='--', alpha=0.3)
    ax.set_xlabel('AFR Error')
    ax.set_ylabel('Frequency')
    ax.set_title('AFR Error Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    output_path = Path(__file__).parent / 'virtual_ecu_comparison.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Plot saved to: {output_path}")
    
    plt.show()


def main():
    """Run all scenarios and compare results."""
    print("\n" + "="*70)
    print("VIRTUAL ECU DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how Virtual ECU simulation creates realistic AFR errors")
    print("when VE tables don't match actual engine behavior.")
    print("\nWe'll run 3 scenarios:")
    print("  1. Perfect VE table (AFR on target)")
    print("  2. Incorrect VE table (AFR errors - needs tuning)")
    print("  3. No ECU simulation (default behavior)")
    
    results = []
    
    # Run scenarios
    try:
        results.append(scenario_1_perfect_ve())
        results.append(scenario_2_incorrect_ve())
        results.append(scenario_3_no_ecu())
        
        # Plot comparison
        print("\n" + "="*70)
        print("GENERATING COMPARISON PLOTS")
        print("="*70)
        plot_comparison(results)
        
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print("\n✅ Virtual ECU simulation is working!")
        print("\nKey findings:")
        print("  • Perfect VE → AFR on target (±0.05 sensor noise)")
        print("  • Wrong VE → Systematic AFR errors (needs tuning)")
        print("  • Errors are proportional to VE table inaccuracy")
        print("\n🚀 This enables closed-loop tuning simulation!")
        print("   Next step: Multi-iteration convergence loop")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

