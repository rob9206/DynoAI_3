"""
DynoAI Heat Soak Compensation - Automated correction for temperature-induced density drift.

This module addresses the "2-8 HP variation" and VE instability caused by IAT sensor heat soak.
When air-cooled V-twins sit idling or run at low airflow, the IAT sensor becomes heat-soaked,
reading higher than the actual air entering the cylinder.

The ECM calculates air density based on this falsely high reading and reduces fuel.
The actual (denser) air causes a lean condition.
Auto-tuning software sees "Lean" and incorrectly raises the VE table values to compensate.
Result: The bike runs rich when cooled down.

This module:
1. Detects heat soak conditions (High IAT + Low Airflow).
2. Calculates the density error between Sensor Temp and Estimated True Air Temp.
3. Generates a "Correction Overlay" (negative factors) to remove this artificial inflation
   from VE tables tuned in hot conditions.
"""

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dynoai.constants import KPA_BINS, RPM_BINS

# ============================================================================
# Configuration Constants
# ============================================================================

# Default threshold for "Hot" IAT where soak becomes significant (°F)
DEFAULT_SOAK_THRESHOLD_F = 130.0

# Minimum airflow (RPM) where soak is active (above this, airflow cools sensor)
SOAK_RPM_CEILING = 3500

# Maximum TPS where soak is active (WOT usually clears soak quickly)
SOAK_TPS_CEILING = 15.0

# IAT recovery rate (degrees F per second at high airflow) - estimated
IAT_RECOVERY_RATE = 2.0

# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class HeatProfile:
    """Summary of thermal conditions during a log session."""

    start_iat: float
    end_iat: float
    peak_iat: float
    avg_iat: float
    start_et: Optional[float]
    peak_et: Optional[float]
    soak_duration_s: float = 0.0  # Time spent in "soak" conditions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_iat": round(self.start_iat, 1),
            "end_iat": round(self.end_iat, 1),
            "peak_iat": round(self.peak_iat, 1),
            "avg_iat": round(self.avg_iat, 1),
            "peak_et": round(self.peak_et, 1) if self.peak_et else None,
            "soak_duration_s": round(self.soak_duration_s, 1),
        }


@dataclass
class SoakEvent:
    """A period of detected heat soak."""

    start_idx: int
    end_idx: int
    duration_s: float
    avg_iat: float
    max_iat: float
    rpm_range: Tuple[float, float]
    estimated_density_error_pct: float  # Estimated % error in VE due to soak


# ============================================================================
# Core Functions
# ============================================================================


def calculate_air_density_ratio(temp_f: float, reference_temp_f: float = 77.0) -> float:
    """
    Calculate air density ratio using Ideal Gas Law approximation.
    Rankine = Fahrenheit + 459.67
    Density ~ 1 / Temperature (Rankine)
    """
    temp_r = temp_f + 459.67
    ref_r = reference_temp_f + 459.67
    return ref_r / temp_r


def analyze_heat_profile(records: Sequence[Dict[str, float]]) -> HeatProfile:
    """Analyze basic temperature statistics from a log."""
    if not records:
        return HeatProfile(0, 0, 0, 0, None, None)

    iats = [r.get("iat", 0) for r in records if r.get("iat") is not None]
    ets = [r.get("et", 0) for r in records if r.get("et") is not None]

    if not iats:
        return HeatProfile(0, 0, 0, 0, None, None)

    # Calculate soak time (time above threshold with low airflow)
    soak_time = 0.0
    dt = 0.01  # Assume 10ms or calculate from timestamps if available
    # Simple estimation based on record count if no time

    return HeatProfile(
        start_iat=iats[0],
        end_iat=iats[-1],
        peak_iat=max(iats),
        avg_iat=sum(iats) / len(iats),
        start_et=ets[0] if ets else None,
        peak_et=max(ets) if ets else None,
    )


def detect_soak_events(
    records: Sequence[Dict[str, float]],
    sample_rate_ms: float = 10.0,
    threshold_f: float = DEFAULT_SOAK_THRESHOLD_F,
) -> List[SoakEvent]:
    """
    Identify periods where heat soak likely compromised VE tuning data.
    Condition: IAT > Threshold AND RPM < Ceiling AND TPS < Ceiling
    """
    events: List[SoakEvent] = []
    in_event = False
    start_idx = 0

    for i, r in enumerate(records):
        iat = r.get("iat", 0)
        rpm = r.get("rpm", 0)
        tps = r.get("tps", 0)

        is_soak_condition = (
            iat >= threshold_f and rpm < SOAK_RPM_CEILING and tps < SOAK_TPS_CEILING
        )

        if is_soak_condition and not in_event:
            in_event = True
            start_idx = i
        elif not is_soak_condition and in_event:
            in_event = False
            duration = (i - start_idx) * (sample_rate_ms / 1000.0)
            if duration > 2.0:  # Minimum 2 seconds to matter
                segment = records[start_idx:i]
                seg_iats = [x.get("iat", 0) for x in segment]
                avg_iat = sum(seg_iats) / len(seg_iats)

                # Estimate error:
                # If sensor says 150F but real air is 100F (due to momentary airflow cooling that sensor missed)
                # Or simply: The fact that it's 150F means ECM is pulling fuel (Density ~0.88 vs 77F)
                # If we tune here, we bake in a factor of (1/0.88 = 1.13) +13% VE.
                # If we want to correct to "Standard Day" (77F), we need to remove that.
                # But usually, we just want to correct to "Running Temp" (approx 100-110F IAT).

                # Let's assume "True Running IAT" should be around 110F.
                # Error = Ratio(Measured) / Ratio(Target)
                target_temp = 110.0
                measured_ratio = calculate_air_density_ratio(avg_iat, 77.0)
                target_ratio = calculate_air_density_ratio(target_temp, 77.0)

                # If measured is 150F (ratio 0.88) and target is 110F (ratio 0.94)
                # The ECM applied 0.88 fuel. It needed 0.94 fuel.
                # It was LEAN by (0.94/0.88) = 1.068 (+6.8%).
                # AutoTune ADDED 6.8% to VE.
                # To fix, we must SUBTRACT 6.8%.

                pct_error = (target_ratio / measured_ratio) - 1.0

                events.append(
                    SoakEvent(
                        start_idx=start_idx,
                        end_idx=i,
                        duration_s=duration,
                        avg_iat=avg_iat,
                        max_iat=max(seg_iats),
                        rpm_range=(
                            min(x.get("rpm", 0) for x in segment),
                            max(x.get("rpm", 0) for x in segment),
                        ),
                        estimated_density_error_pct=pct_error,
                    )
                )

    # Check for event active at end of log
    if in_event:
        i = len(records)
        duration = (i - start_idx) * (sample_rate_ms / 1000.0)
        if duration > 2.0:
            segment = records[start_idx:]
            seg_iats = [x.get("iat", 0) for x in segment]
            avg_iat = sum(seg_iats) / len(seg_iats)

            target_temp = 110.0
            measured_ratio = calculate_air_density_ratio(avg_iat, 77.0)
            target_ratio = calculate_air_density_ratio(target_temp, 77.0)
            pct_error = (target_ratio / measured_ratio) - 1.0

            events.append(
                SoakEvent(
                    start_idx=start_idx,
                    end_idx=i,
                    duration_s=duration,
                    avg_iat=avg_iat,
                    max_iat=max(seg_iats),
                    rpm_range=(
                        min(x.get("rpm", 0) for x in segment),
                        max(x.get("rpm", 0) for x in segment),
                    ),
                    estimated_density_error_pct=pct_error,
                )
            )

    return events


def generate_heat_correction_overlay(
    events: List[SoakEvent],
    rpm_bins: Sequence[int] = None,
    kpa_bins: Sequence[int] = None,
) -> List[List[float]]:
    """
    Generate a VE correction overlay (negative factors) to compensate for heat soak.
    """
    if rpm_bins is None:
        rpm_bins = RPM_BINS
    if kpa_bins is None:
        kpa_bins = KPA_BINS
    # Initialize empty grid
    overlay = [[0.0 for _ in kpa_bins] for _ in rpm_bins]

    # Map events to grid cells
    # We accumulate errors and average them for affected cells
    cell_errors: Dict[Tuple[int, int], List[float]] = {}

    for event in events:
        # Determine which RPM bins this event touched
        # Since we don't have exact cell hits here without re-scanning records,
        # we'll approximate based on the event's RPM range and assumed Low Load (since TPS < 15)

        # Find RPM indices
        min_r_idx = -1
        max_r_idx = -1

        for i, rpm in enumerate(rpm_bins):
            if rpm >= event.rpm_range[0] and min_r_idx == -1:
                min_r_idx = i
            if rpm <= event.rpm_range[1]:
                max_r_idx = i

        if min_r_idx == -1:
            min_r_idx = 0
        if max_r_idx == -1:
            max_r_idx = len(rpm_bins) - 1

        # Apply to Low KPA/TPS columns (approx 20-60 kPa for idle/cruise)
        # This is a simplification; ideally we'd map every record.
        kpa_indices = [i for i, k in enumerate(kpa_bins) if k <= 60]

        for r_idx in range(min_r_idx, max_r_idx + 1):
            for k_idx in kpa_indices:
                if (r_idx, k_idx) not in cell_errors:
                    cell_errors[(r_idx, k_idx)] = []
                # We want to NEGATE the error. If AutoTune added 6%, we want -6%.
                cell_errors[(r_idx, k_idx)].append(-event.estimated_density_error_pct)

    # Average the corrections
    for (r, k), errors in cell_errors.items():
        avg_correction = sum(errors) / len(errors)
        # Clamp to safety limits (e.g., don't remove more than 10% fuel blindly)
        if avg_correction < -0.10:
            avg_correction = -0.10
        if avg_correction > 0.0:
            avg_correction = 0.0  # Should only be removing fuel

        overlay[r][k] = avg_correction

    return overlay


def write_heat_overlay_csv(
    overlay: List[List[float]],
    output_path: Path,
    rpm_bins: Sequence[int] = None,
    kpa_bins: Sequence[int] = None,
) -> str:
    """Write the correction overlay to CSV."""
    if rpm_bins is None:
        rpm_bins = RPM_BINS
    if kpa_bins is None:
        kpa_bins = KPA_BINS
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["RPM"] + [str(k) for k in kpa_bins])
        for i, row in enumerate(overlay):
            out_row = [str(rpm_bins[i])] + [f"{x * 100:.2f}" for x in row]
            writer.writerow(out_row)
    return str(output_path)


if __name__ == "__main__":
    # Simple self-test
    print("Heat Management Module Loaded.")
