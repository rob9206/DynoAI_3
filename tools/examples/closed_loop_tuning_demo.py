"""
Closed-Loop Tuning Demo - Complete multi-iteration tuning simulation.

This script demonstrates the full closed-loop tuning workflow:
1. Start with intentionally wrong VE tables
2. Run dyno pulls
3. Analyze AFR errors
4. Calculate and apply VE corrections
5. Repeat until converged

This is the complete virtual tuning system!
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.dyno_simulator import EngineProfile
from api.services.virtual_tuning_session import (
    TuningSessionConfig,
    VirtualTuningOrchestrator,
)


def run_closed_loop_demo():
    """Run a complete closed-loop tuning demonstration."""
    print("\n" + "=" * 70)
    print("CLOSED-LOOP VIRTUAL TUNING DEMONSTRATION")
    print("=" * 70)
    print("\nThis demo shows complete multi-iteration tuning until convergence.")
    print("Starting with a VE table that's 10% too low (typical untuned engine).")
    print()

    # Create configuration
    config = TuningSessionConfig(
        engine_profile=EngineProfile.m8_114(),
        base_ve_scenario="lean",  # Start with -10% VE error
        max_iterations=10,
        convergence_threshold_afr=0.3,  # Converge when AFR error < 0.3
        convergence_cell_pct=90.0,  # 90% of cells must be converged
        max_correction_per_iteration_pct=15.0,
        oscillation_detection_enabled=True,
    )

    print(f"Configuration:")
    print(f"  Engine: {config.engine_profile.name}")
    print(f"  Starting scenario: {config.base_ve_scenario} (VE -10%)")
    print(f"  Max iterations: {config.max_iterations}")
    print(f"  Convergence threshold: {config.convergence_threshold_afr} AFR points")
    print(f"  Oscillation detection: {config.oscillation_detection_enabled}")
    print()

    # Create orchestrator
    orchestrator = VirtualTuningOrchestrator()

    # Create session
    print("Creating tuning session...")
    session = orchestrator.create_session(config)
    print(f"[OK] Session created: {session.session_id}")
    print()

    # Run tuning
    print("=" * 70)
    print("STARTING CLOSED-LOOP TUNING")
    print("=" * 70)
    print()

    start_time = time.time()
    session = orchestrator.run_session(session)
    duration = time.time() - start_time

    # Print results
    print()
    print("=" * 70)
    print("TUNING COMPLETE")
    print("=" * 70)
    print()

    print(f"Status: {session.status.value.upper()}")
    print(f"Total iterations: {session.current_iteration}")
    print(f"Duration: {duration:.1f} seconds")
    print()

    if session.iterations:
        print("Iteration History:")
        print(
            f"{'Iter':<6} {'Max AFR Error':<15} {'Mean AFR Error':<16} {'Max VE Corr':<15} {'Status'}"
        )
        print("-" * 70)

        for it in session.iterations:
            status = "[CONVERGED]" if it.converged else "[Tuning]"
            print(
                f"{it.iteration:<6} "
                f"{it.max_afr_error:>6.3f} AFR{'':<6} "
                f"{it.mean_afr_error:>6.3f} AFR{'':<7} "
                f"{it.max_ve_correction_pct:>6.2f}%{'':<7} "
                f"{status}"
            )

        print()

        # Final metrics
        last_iteration = session.iterations[-1]
        print("Final Metrics:")
        print(f"  Max AFR Error: {last_iteration.max_afr_error:.3f} AFR points")
        print(f"  Mean AFR Error: {last_iteration.mean_afr_error:.3f} AFR points")
        print(f"  RMS AFR Error: {last_iteration.rms_afr_error:.3f} AFR points")
        print(
            f"  Cells Converged: {last_iteration.cells_converged} / {11*9} ({last_iteration.cells_converged/(11*9)*100:.1f}%)"
        )
        print(f"  Peak HP: {last_iteration.peak_hp:.1f} HP")
        print(f"  Peak Torque: {last_iteration.peak_tq:.1f} ft-lb")
        print()

        # Convergence analysis
        if session.status.value == "converged":
            print(f"[OK] CONVERGED in {session.current_iteration} iterations!")
            convergence_rate = (
                "fast"
                if session.current_iteration <= 3
                else "normal" if session.current_iteration <= 6 else "slow"
            )
            print(f"   Convergence rate: {convergence_rate.upper()}")
        elif session.status.value == "max_iterations":
            print(f"[WARN] Reached max iterations without full convergence")
            print(
                f"   Final error ({last_iteration.max_afr_error:.3f}) is close to threshold ({config.convergence_threshold_afr})"
            )
        elif session.status.value == "failed":
            print(f"[ERROR] FAILED: {session.error_message}")

        print()

        # Plot results
        plot_convergence(session)

    return session


def plot_convergence(session):
    """Plot convergence metrics over iterations."""
    if not session.iterations:
        return

    iterations = [it.iteration for it in session.iterations]
    max_errors = [it.max_afr_error for it in session.iterations]
    mean_errors = [it.mean_afr_error for it in session.iterations]
    ve_corrections = [it.max_ve_correction_pct for it in session.iterations]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Closed-Loop Tuning Convergence", fontsize=16, fontweight="bold")

    # Plot 1: AFR Error vs Iteration
    ax = axes[0, 0]
    ax.plot(
        iterations,
        max_errors,
        "o-",
        label="Max AFR Error",
        color="red",
        linewidth=2,
        markersize=8,
    )
    ax.plot(
        iterations,
        mean_errors,
        "s-",
        label="Mean AFR Error",
        color="orange",
        linewidth=2,
        markersize=6,
    )
    ax.axhline(
        y=session.config.convergence_threshold_afr,
        color="green",
        linestyle="--",
        alpha=0.5,
        label="Convergence Threshold",
    )
    ax.set_xlabel("Iteration")
    ax.set_ylabel("AFR Error (points)")
    ax.set_title("AFR Error Convergence")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 2: VE Correction vs Iteration
    ax = axes[0, 1]
    ax.bar(iterations, ve_corrections, color="blue", alpha=0.7)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Max VE Correction (%)")
    ax.set_title("VE Corrections Applied")
    ax.grid(True, alpha=0.3, axis="y")

    # Plot 3: Convergence Progress
    ax = axes[1, 0]
    cells_converged = [it.cells_converged for it in session.iterations]
    total_cells = 11 * 9
    convergence_pct = [c / total_cells * 100 for c in cells_converged]
    ax.plot(iterations, convergence_pct, "o-", color="green", linewidth=2, markersize=8)
    ax.axhline(
        y=session.config.convergence_cell_pct,
        color="green",
        linestyle="--",
        alpha=0.5,
        label="Target",
    )
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Cells Converged (%)")
    ax.set_title("Convergence Progress")
    ax.set_ylim([0, 105])
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 4: Error Reduction Rate
    ax = axes[1, 1]
    if len(max_errors) > 1:
        error_reduction = [max_errors[0]]  # First iteration has no reduction
        for i in range(1, len(max_errors)):
            reduction_pct = (
                (max_errors[i - 1] - max_errors[i]) / max_errors[i - 1]
            ) * 100
            error_reduction.append(reduction_pct)

        ax.bar(iterations, error_reduction, color="purple", alpha=0.7)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Error Reduction (%)")
        ax.set_title("Iteration-to-Iteration Improvement")
        ax.grid(True, alpha=0.3, axis="y")
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)

    plt.tight_layout()

    # Save plot
    output_path = Path(__file__).parent / "closed_loop_convergence.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"[PLOT] Convergence plot saved to: {output_path}")

    plt.show()


def main():
    """Run the demo."""
    try:
        session = run_closed_loop_demo()

        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print()
        print("[OK] Closed-loop tuning demonstration complete!")
        print()
        print("Key Findings:")
        print("  - Starting VE error: -10% (typical untuned engine)")

        if session.iterations:
            first_error = session.iterations[0].max_afr_error
            last_error = session.iterations[-1].max_afr_error
            improvement = ((first_error - last_error) / first_error) * 100

            print(f"  - Initial AFR error: {first_error:.3f} points")
            print(f"  - Final AFR error: {last_error:.3f} points")
            print(f"  - Improvement: {improvement:.1f}%")
            print(f"  - Iterations needed: {session.current_iteration}")

        print()
        print("[SUCCESS] This demonstrates fully automated tuning simulation!")
        print("          Next step: Add UI for real-time progress visualization")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
