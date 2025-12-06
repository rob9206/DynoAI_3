"""
DynoAI Decel Fuel Management - Automated deceleration popping elimination.

This module detects deceleration events from dyno log data and generates
VE enrichment overlays to eliminate decel popping (afterfire) in V-twin engines.

The algorithm:
1. Detects throttle closure events (decel) from TPS rate of change
2. Analyzes AFR behavior during decel to identify lean spikes
3. Calculates enrichment needed to prevent exhaust combustion
4. Generates VE overlay for closed-throttle cells

Usage:
    from decel_management import (
        detect_decel_events,
        analyze_decel_afr,
        calculate_decel_enrichment,
        generate_decel_overlay,
    )

    # Detect decel events
    events = detect_decel_events(records, sample_rate_ms=10.0)

    # Analyze AFR during events
    events = analyze_decel_afr(records, events, afr_col='afr_meas_f')

    # Calculate enrichment
    enrichment_map = calculate_decel_enrichment(events, severity='medium')

    # Generate overlay
    overlay = generate_decel_overlay(enrichment_map, rpm_bins, kpa_bins)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dynoai.constants import KPA_BINS, KPA_INDEX, RPM_BINS, RPM_INDEX

# ============================================================================
# Configuration Constants
# ============================================================================


class DecelSeverity(Enum):
    """Decel enrichment severity presets."""

    LOW = "low"  # Minimal enrichment, may still have some popping
    MEDIUM = "medium"  # Balanced - eliminates most popping (default)
    HIGH = "high"  # Aggressive - eliminates all popping, impacts economy


# Severity multipliers for enrichment scaling
SEVERITY_MULTIPLIERS: Dict[DecelSeverity, float] = {
    DecelSeverity.LOW: 0.7,
    DecelSeverity.MEDIUM: 1.0,
    DecelSeverity.HIGH: 1.3,
}

# Default decel event detection criteria
DEFAULT_DECEL_CONFIG: Dict[str, float] = {
    "tps_rate_threshold": -15.0,  # TPS change rate (%/second), negative = closing
    "tps_max_at_end": 7.0,  # Maximum TPS at end of event (%)
    "rpm_min": 1500,  # Minimum RPM for decel event
    "rpm_max": 5500,  # Maximum RPM for decel event
    "duration_min_ms": 200,  # Minimum event duration (ms)
    "duration_max_ms": 3000,  # Maximum event duration (ms)
}

# Base enrichment table by RPM and TPS zone
# Format: (rpm_min, rpm_max, tps_min, tps_max) -> enrichment_pct
BASE_ENRICHMENT: Dict[Tuple[int, int, int, int], float] = {
    # Low RPM zones (1500-2500) - highest pop risk
    (1500, 2500, 0, 2): 0.22,  # +22%
    (1500, 2500, 2, 5): 0.17,  # +17%
    (1500, 2500, 5, 7): 0.10,  # +10%
    # Mid-low RPM zones (2500-3500)
    (2500, 3500, 0, 2): 0.18,  # +18%
    (2500, 3500, 2, 5): 0.12,  # +12%
    (2500, 3500, 5, 7): 0.08,  # +8%
    # Mid RPM zones (3500-4500)
    (3500, 4500, 0, 2): 0.12,  # +12%
    (3500, 4500, 2, 5): 0.08,  # +8%
    (3500, 4500, 5, 7): 0.05,  # +5%
    # High RPM zones (4500-5500) - highest airflow, less enrichment needed
    (4500, 5500, 0, 2): 0.10,  # +10%
    (4500, 5500, 2, 5): 0.06,  # +6%
    (4500, 5500, 5, 7): 0.04,  # +4%
}

# Maximum kPa for decel cells (only apply to vacuum/low-load cells)
DECEL_KPA_MAX: int = 45

# Maximum enrichment cap (safety limit)
MAX_ENRICHMENT_PCT: float = 0.30  # 30%

# Minimum enrichment floor in decel zone
MIN_ENRICHMENT_PCT: float = 0.05  # 5%

# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DecelEvent:
    """Represents a detected deceleration event."""

    start_idx: int
    end_idx: int
    start_rpm: float
    end_rpm: float
    start_tps: float
    end_tps: float
    tps_rate: float  # %/second (negative for closing)
    duration_ms: float
    afr_min: Optional[float] = None  # Leanest AFR during event
    afr_max: Optional[float] = None  # Richest AFR during event
    pop_likelihood: float = 0.0  # 0.0-1.0 score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "rpm_range": [self.start_rpm, self.end_rpm],
            "tps_range": [self.start_tps, self.end_tps],
            "tps_rate": round(self.tps_rate, 2),
            "duration_ms": round(self.duration_ms, 1),
            "afr_excursion": {
                "min": round(self.afr_min, 2) if self.afr_min else None,
                "max": round(self.afr_max, 2) if self.afr_max else None,
            },
            "pop_likelihood": round(self.pop_likelihood, 3),
        }


@dataclass
class DecelAnalysisReport:
    """Complete analysis report for decel fuel management."""

    version: str = "1.0"
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    input_file: str = ""
    events_detected: int = 0
    avg_pop_likelihood: float = 0.0
    highest_risk_rpm: Optional[float] = None
    highest_risk_tps: Optional[float] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    enrichment_zones: List[Dict[str, Any]] = field(default_factory=list)
    severity_used: str = "medium"
    total_enrichment_avg: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    tradeoffs: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "input_file": self.input_file,
            "summary": {
                "events_detected": self.events_detected,
                "avg_pop_likelihood": round(self.avg_pop_likelihood, 3),
                "highest_risk_rpm": self.highest_risk_rpm,
                "highest_risk_tps": self.highest_risk_tps,
                "total_enrichment_applied": f"+{self.total_enrichment_avg * 100:.1f}% average in decel zone",
            },
            "severity_used": self.severity_used,
            "events": self.events[:20],  # Limit to 20 events in report
            "enrichment_zones": self.enrichment_zones,
            "recommendations": self.recommendations,
            "tradeoffs": self.tradeoffs,
        }


# ============================================================================
# Core Algorithm Functions
# ============================================================================


def detect_decel_events(
    records: Sequence[Dict[str, Optional[float]]],
    sample_rate_ms: float = 10.0,
    config: Optional[Dict[str, float]] = None,
) -> List[DecelEvent]:
    """
    Detect deceleration events from logged data.

    A decel event is defined as:
    - Throttle closing rapidly (TPS rate below threshold)
    - Ending at low throttle position
    - Within valid RPM range
    - Duration within expected range

    Args:
        records: List of data records with 'rpm', 'tps' keys
        sample_rate_ms: Time between samples in milliseconds
        config: Optional config overrides (defaults to DEFAULT_DECEL_CONFIG)

    Returns:
        List of detected DecelEvent objects
    """
    cfg = {**DEFAULT_DECEL_CONFIG, **(config or {})}

    # Extract TPS values
    tps_values: List[float] = []
    for r in records:
        tps = r.get("tps")
        if tps is not None:
            tps_values.append(float(tps))
        else:
            tps_values.append(0.0)  # Default to 0 if missing

    if len(tps_values) < 3:
        return []

    # Calculate TPS rate of change using simple gradient
    tps_rate: List[float] = []
    # Ensure dt_sec is never 0
    dt_sec = max(sample_rate_ms / 1000.0, 0.001)

    # Forward difference for first element
    tps_rate.append((tps_values[1] - tps_values[0]) / dt_sec)

    # Central difference for middle elements
    for i in range(1, len(tps_values) - 1):
        rate = (tps_values[i + 1] - tps_values[i - 1]) / (2 * dt_sec)
        tps_rate.append(rate)

    # Backward difference for last element
    tps_rate.append((tps_values[-1] - tps_values[-2]) / dt_sec)

    events: List[DecelEvent] = []
    in_event = False
    event_start = 0

    for i in range(len(records)):
        rpm = records[i].get("rpm")
        tps_val = tps_values[i]
        rate = tps_rate[i]

        if rpm is None:
            continue

        rpm_float = float(rpm)

        # Check if entering decel event
        if not in_event:
            # Check both rate threshold AND just low TPS with dropping RPM
            is_rapid_close = rate <= cfg["tps_rate_threshold"]

            # Also catch "already closed" throttle during RPM drop (common in synthetic logs)
            # If TPS is 0 and RPM is dropping, we are in decel
            # Ensure we have valid RPM drop
            rpm_drop = 0.0
            if i > 0:
                prev_rpm = float(records[i - 1].get("rpm", rpm_float))
                rpm_drop = prev_rpm - rpm_float

            is_steady_closed = (tps_val <= cfg["tps_max_at_end"]) and (
                rpm_drop > 5.0
            )  # Significant drop per sample

            if (is_rapid_close or is_steady_closed) and (
                cfg["rpm_min"] <= rpm_float <= cfg["rpm_max"]
            ):
                in_event = True
                event_start = i

        # Check if exiting decel event
        else:
            # Event ends when TPS rises OR RPM drops too low
            tps_rose = tps_val > cfg["tps_max_at_end"]
            rpm_too_low = rpm_float < cfg["rpm_min"]

            if tps_rose or rpm_too_low or i == len(records) - 1:
                duration_ms = (i - event_start) * sample_rate_ms

                if cfg["duration_min_ms"] <= duration_ms <= cfg["duration_max_ms"]:
                    # Get start values
                    start_rpm = records[event_start].get("rpm")
                    start_tps = tps_values[event_start]

                    if start_rpm is not None:
                        # Calculate average TPS rate during event
                        avg_rate = sum(tps_rate[event_start:i]) / max(
                            1, i - event_start
                        )

                        event = DecelEvent(
                            start_idx=event_start,
                            end_idx=i,
                            start_rpm=float(start_rpm),
                            end_rpm=rpm_float,
                            start_tps=start_tps,
                            end_tps=tps_val,
                            tps_rate=avg_rate,
                            duration_ms=duration_ms,
                        )
                        events.append(event)

                in_event = False

    return events


def analyze_decel_afr(
    records: Sequence[Dict[str, Optional[float]]],
    events: List[DecelEvent],
    afr_col: str = "afr_meas_f",
) -> List[DecelEvent]:
    """
    Analyze AFR behavior during decel events.

    Adds afr_min, afr_max, and pop_likelihood to each event.
    Pop likelihood is based on how lean the AFR gets during decel.

    Args:
        records: List of data records with AFR columns
        events: List of DecelEvent objects to analyze
        afr_col: Column name for AFR data ('afr_meas_f' or 'afr_meas_r')

    Returns:
        Updated list of DecelEvent objects with AFR analysis
    """
    for event in events:
        afr_values: List[float] = []

        for i in range(event.start_idx, min(event.end_idx + 1, len(records))):
            afr = records[i].get(afr_col)
            if afr is not None and 9.0 <= afr <= 20.0:  # Valid AFR range
                afr_values.append(float(afr))

        if afr_values:
            event.afr_min = min(afr_values)
            event.afr_max = max(afr_values)

            # Calculate pop likelihood based on lean excursion
            # Lean spike > 15.5 AFR is high pop risk
            # AFR > 16.5 is very high risk
            lean_spike = event.afr_max - 14.7  # Deviation from stoich
            if lean_spike > 0:
                event.pop_likelihood = min(1.0, lean_spike / 2.0)
            else:
                event.pop_likelihood = 0.0

    return events


def calculate_decel_enrichment(
    events: List[DecelEvent],
    severity: DecelSeverity = DecelSeverity.MEDIUM,
    config: Optional[Dict[str, float]] = None,
) -> Dict[Tuple[int, int, int, int], float]:
    """
    Calculate required enrichment to prevent decel popping.

    Starts with base enrichment table and adjusts based on detected events.
    Events with high pop likelihood increase enrichment in their zones.

    Args:
        events: List of analyzed DecelEvent objects
        severity: Enrichment severity level (low/medium/high)
        config: Optional config overrides

    Returns:
        Dict mapping (rpm_min, rpm_max, tps_min, tps_max) -> enrichment_pct
    """
    multiplier = SEVERITY_MULTIPLIERS.get(severity, 1.0)

    # Start with base enrichment scaled by severity
    enrichment_map: Dict[Tuple[int, int, int, int], float] = {}
    for zone, base_pct in BASE_ENRICHMENT.items():
        enrichment_map[zone] = base_pct * multiplier

    # Adjust based on detected events
    for event in events:
        if event.pop_likelihood < 0.3:
            continue  # Skip low-likelihood events

        # Find which zone this event falls into
        for zone in BASE_ENRICHMENT.keys():
            rpm_min, rpm_max, tps_min, tps_max = zone

            # Check if event's end point is in this zone
            if (
                rpm_min <= event.end_rpm < rpm_max
                and tps_min <= event.end_tps < tps_max
            ):
                # Increase enrichment based on pop severity
                current = enrichment_map[zone]
                # Add up to 5% more based on pop severity
                additional = event.pop_likelihood * 0.05
                enrichment_map[zone] = min(MAX_ENRICHMENT_PCT, current + additional)
                break

    # Ensure minimum enrichment floor
    for zone in enrichment_map:
        if enrichment_map[zone] < MIN_ENRICHMENT_PCT:
            enrichment_map[zone] = MIN_ENRICHMENT_PCT

    return enrichment_map


def generate_decel_overlay(
    enrichment_map: Dict[Tuple[int, int, int, int], float],
    rpm_bins: Sequence[int] = RPM_BINS,
    kpa_bins: Sequence[int] = KPA_BINS,
) -> List[List[float]]:
    """
    Generate VE correction overlay for decel fuel management.

    Decel occurs at low MAP values (high vacuum). This overlay targets
    cells below DECEL_KPA_MAX and maps TPS zones to effective kPa levels.

    Args:
        enrichment_map: Dict of zone -> enrichment percentage
        rpm_bins: List of RPM bin centers
        kpa_bins: List of kPa bin centers

    Returns:
        2D list of VE correction factors (enrichment percentages)
    """
    overlay: List[List[float]] = [[0.0 for _ in kpa_bins] for _ in rpm_bins]

    for i, rpm in enumerate(rpm_bins):
        for j, kpa in enumerate(kpa_bins):
            # Only apply enrichment to low-MAP (decel) cells
            if kpa > DECEL_KPA_MAX:
                continue

            # Map kPa to effective TPS
            # Lower kPa = more vacuum = lower effective TPS
            effective_tps = (kpa / DECEL_KPA_MAX) * 7.0  # Scale to 0-7% TPS

            # Find applicable enrichment zone
            for zone, enrichment in enrichment_map.items():
                rpm_min, rpm_max, tps_min, tps_max = zone

                if rpm_min <= rpm < rpm_max and tps_min <= effective_tps < tps_max:
                    overlay[i][j] = enrichment
                    break

    return overlay


# ============================================================================
# Output Functions
# ============================================================================


def write_decel_overlay_csv(
    overlay: List[List[float]],
    output_path: str | Path,
    rpm_bins: Sequence[int] = RPM_BINS,
    kpa_bins: Sequence[int] = KPA_BINS,
) -> str:
    """
    Write decel VE overlay to CSV in standard format.

    Args:
        overlay: 2D list of enrichment values
        output_path: Path to output CSV file
        rpm_bins: List of RPM bin centers
        kpa_bins: List of kPa bin centers

    Returns:
        Path to written file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header row: RPM, kPa values
        header = ["RPM"] + [str(kpa) for kpa in kpa_bins]
        writer.writerow(header)

        # Data rows
        for i, rpm in enumerate(rpm_bins):
            row = [str(rpm)] + [
                f"{overlay[i][j] * 100:+.2f}" for j in range(len(kpa_bins))
            ]
            writer.writerow(row)

    return str(output_path)


def write_decel_analysis_report(
    report: DecelAnalysisReport,
    output_path: str | Path,
) -> str:
    """
    Write decel analysis report to JSON file.

    Args:
        report: DecelAnalysisReport object
        output_path: Path to output JSON file

    Returns:
        Path to written file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    return str(output_path)


def generate_decel_report(
    events: List[DecelEvent],
    enrichment_map: Dict[Tuple[int, int, int, int], float],
    overlay: List[List[float]],
    input_file: str = "",
    severity: DecelSeverity = DecelSeverity.MEDIUM,
) -> DecelAnalysisReport:
    """
    Generate a complete decel analysis report.

    Args:
        events: List of analyzed DecelEvent objects
        enrichment_map: Calculated enrichment map
        overlay: Generated VE overlay
        input_file: Name of input file
        severity: Severity level used

    Returns:
        DecelAnalysisReport object
    """
    report = DecelAnalysisReport(
        input_file=input_file,
        events_detected=len(events),
        severity_used=severity.value,
    )

    if events:
        # Calculate averages
        pop_likelihoods = [e.pop_likelihood for e in events if e.pop_likelihood > 0]
        if pop_likelihoods:
            report.avg_pop_likelihood = sum(pop_likelihoods) / len(pop_likelihoods)

        # Find highest risk event
        highest_risk_event = max(events, key=lambda e: e.pop_likelihood)
        report.highest_risk_rpm = highest_risk_event.end_rpm
        report.highest_risk_tps = highest_risk_event.end_tps

        # Add event details
        report.events = [e.to_dict() for e in events]

    # Add enrichment zone details
    for zone, enrichment in enrichment_map.items():
        rpm_min, rpm_max, tps_min, tps_max = zone
        report.enrichment_zones.append(
            {
                "rpm_range": [rpm_min, rpm_max],
                "tps_range": [tps_min, tps_max],
                "enrichment_pct": round(enrichment * 100, 1),
            }
        )

    # Calculate average enrichment in decel zone
    decel_cells = [
        (i, j)
        for i in range(len(overlay))
        for j in range(len(overlay[0]))
        if overlay[i][j] > 0
    ]
    if decel_cells:
        total = sum(overlay[i][j] for i, j in decel_cells)
        report.total_enrichment_avg = total / len(decel_cells)

    # Add recommendations
    if report.avg_pop_likelihood > 0.5:
        report.recommendations.append(
            "High pop likelihood detected - consider PAIR valve removal/block-off"
        )
    if report.events_detected > 10:
        report.recommendations.append(
            "Multiple decel events detected - overlay should significantly reduce popping"
        )
    if severity == DecelSeverity.LOW:
        report.recommendations.append(
            "Using LOW severity - some popping may remain, increase to MEDIUM if needed"
        )

    report.recommendations.extend(
        [
            "Apply decel overlay to closed-throttle cells only",
            "Slight fuel economy reduction during engine braking is expected",
            "Re-test after applying to verify popping elimination",
        ]
    )

    # Add tradeoffs
    fuel_impact = (
        "-0.5 to -1.0 MPG"
        if severity == DecelSeverity.MEDIUM
        else "-0.3 to -0.5 MPG"
        if severity == DecelSeverity.LOW
        else "-1.0 to -2.0 MPG"
    )
    report.tradeoffs = {
        "fuel_economy_impact": f"{fuel_impact} estimated during mixed driving",
        "emission_impact": "Slight increase in HC during decel (closed loop mitigates)",
        "driveability_impact": "Smoother decel, reduced exhaust bark",
    }

    return report


# ============================================================================
# High-Level Integration Function
# ============================================================================


def process_decel_management(
    records: Sequence[Dict[str, Optional[float]]],
    output_dir: str | Path,
    severity: str = "medium",
    sample_rate_ms: float = 10.0,
    input_file: str = "",
    config: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Complete decel management processing pipeline.

    This function runs the full decel analysis pipeline:
    1. Detect decel events
    2. Analyze AFR behavior
    3. Calculate enrichment
    4. Generate overlay
    5. Write output files

    Args:
        records: List of data records from dyno log
        output_dir: Directory for output files
        severity: Enrichment severity ('low', 'medium', 'high')
        sample_rate_ms: Sample rate of log data
        input_file: Name of input file for report
        config: Optional config overrides

    Returns:
        Dict with processing results and output file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse severity
    try:
        severity_enum = DecelSeverity(severity.lower())
    except ValueError:
        severity_enum = DecelSeverity.MEDIUM

    # Step 1: Detect decel events
    events = detect_decel_events(records, sample_rate_ms, config)

    # Step 2: Analyze AFR (try both cylinders)
    events = analyze_decel_afr(records, events, "afr_meas_f")
    events = analyze_decel_afr(records, events, "afr_meas_r")

    # Step 3: Calculate enrichment
    enrichment_map = calculate_decel_enrichment(events, severity_enum, config)

    # Step 4: Generate overlay
    overlay = generate_decel_overlay(enrichment_map)

    # Step 5: Generate report
    report = generate_decel_report(
        events, enrichment_map, overlay, input_file, severity_enum
    )

    # Step 6: Write outputs
    overlay_path = write_decel_overlay_csv(
        overlay, output_dir / "Decel_Fuel_Overlay.csv"
    )
    report_path = write_decel_analysis_report(
        report, output_dir / "Decel_Analysis_Report.json"
    )

    return {
        "events_detected": len(events),
        "severity_used": severity_enum.value,
        "avg_pop_likelihood": report.avg_pop_likelihood,
        "output_files": {
            "overlay": overlay_path,
            "report": report_path,
        },
        "overlay": overlay,
        "report": report,
    }


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    # Enums
    "DecelSeverity",
    # Data classes
    "DecelEvent",
    "DecelAnalysisReport",
    # Core functions
    "detect_decel_events",
    "analyze_decel_afr",
    "calculate_decel_enrichment",
    "generate_decel_overlay",
    # Output functions
    "write_decel_overlay_csv",
    "write_decel_analysis_report",
    "generate_decel_report",
    # High-level function
    "process_decel_management",
    # Constants
    "DEFAULT_DECEL_CONFIG",
    "BASE_ENRICHMENT",
    "DECEL_KPA_MAX",
    "MAX_ENRICHMENT_PCT",
    "MIN_ENRICHMENT_PCT",
]
