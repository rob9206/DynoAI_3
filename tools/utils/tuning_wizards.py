"""
DynoAI Tuning Wizards - One-click solutions for common V-twin tuning problems.

This module provides validated, practical tuning tools based on real-world research:

1. Decel Pop Wizard - Fix exhaust popping with one click (universal problem)
2. Stage Configuration - VE multiplier templates by build level
3. Heat Soak Warning - Track HP degradation across pulls
4. Cam Family Presets - Idle VE and AFR targets by cam type

These tools solve real problems that tuners face daily, with automation that
Power Vision and similar tools can't provide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from dynoai.constants import KPA_BINS, RPM_BINS

# ============================================================================
# Stage Configuration Presets
# ============================================================================


class StageLevel(Enum):
    """Harley-Davidson modification stage levels."""

    STOCK = "stock"
    STAGE_1 = "stage_1"  # Air cleaner + exhaust
    STAGE_2 = "stage_2"  # Stage 1 + cam (bolt-in)
    STAGE_3 = "stage_3"  # Stage 2 + headwork/big bore
    STAGE_4 = "stage_4"  # Full race build


@dataclass
class StagePreset:
    """Configuration preset for a modification stage."""

    level: StageLevel
    display_name: str
    description: str

    # VE scaling expectations
    ve_multiplier_min: float  # Minimum expected VE increase
    ve_multiplier_max: float  # Maximum expected VE increase

    # AFR targets (NOT 14.7 for performance!)
    afr_cruise: float  # Part-throttle cruise
    afr_wot: float  # Wide-open throttle
    afr_idle: float  # Idle

    # Clamp adjustments
    suggested_clamp: float  # Max single-correction %

    # Expected characteristics
    idle_rpm_target: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "level": self.level.value,
            "display_name": self.display_name,
            "description": self.description,
            "ve_scaling": {
                "multiplier_min": self.ve_multiplier_min,
                "multiplier_max": self.ve_multiplier_max,
                "percentage_range": f"+{self.ve_multiplier_min * 100:.0f}% to +{self.ve_multiplier_max * 100:.0f}%",
            },
            "afr_targets": {
                "cruise": self.afr_cruise,
                "wot": self.afr_wot,
                "idle": self.afr_idle,
            },
            "tuning_params": {
                "suggested_clamp": self.suggested_clamp,
                "idle_rpm_target": self.idle_rpm_target,
            },
            "notes": self.notes,
        }


# Stage presets with validated values from research
STAGE_PRESETS: dict[StageLevel, StagePreset] = {
    StageLevel.STOCK: StagePreset(
        level=StageLevel.STOCK,
        display_name="Stock",
        description="Factory configuration, emissions-compliant tune",
        ve_multiplier_min=0.0,
        ve_multiplier_max=0.05,
        afr_cruise=14.6,
        afr_wot=13.2,
        afr_idle=14.7,
        suggested_clamp=5.0,
        idle_rpm_target=1000,
        notes=[
            "Factory ECM is often too lean for optimal performance",
            "Stock exhaust restricts airflow",
            "PAIR valve may cause decel pop",
        ],
    ),
    StageLevel.STAGE_1: StagePreset(
        level=StageLevel.STAGE_1,
        display_name="Stage 1",
        description="Air cleaner + exhaust upgrade",
        ve_multiplier_min=0.08,
        ve_multiplier_max=0.15,
        afr_cruise=13.8,
        afr_wot=12.8,
        afr_idle=14.0,
        suggested_clamp=10.0,
        idle_rpm_target=1000,
        notes=[
            "Expect +8-15% VE improvement",
            "Stock cam may limit gains",
            "Decel pop common without tune",
            "Heat management important",
        ],
    ),
    StageLevel.STAGE_2: StagePreset(
        level=StageLevel.STAGE_2,
        display_name="Stage 2",
        description="Stage 1 + bolt-in cam (475-510 lift)",
        ve_multiplier_min=0.15,
        ve_multiplier_max=0.25,
        afr_cruise=13.4,
        afr_wot=12.5,
        afr_idle=13.5,
        suggested_clamp=15.0,
        idle_rpm_target=1050,
        notes=[
            "Expect +15-25% VE improvement",
            "Idle may be rougher than stock",
            "Vacuum signal may be lower",
            "May need idle VE adjustment",
        ],
    ),
    StageLevel.STAGE_3: StagePreset(
        level=StageLevel.STAGE_3,
        display_name="Stage 3",
        description="Headwork, big bore, high-performance cam (550+ lift)",
        ve_multiplier_min=0.25,
        ve_multiplier_max=0.40,
        afr_cruise=13.0,
        afr_wot=12.2,
        afr_idle=13.2,
        suggested_clamp=20.0,
        idle_rpm_target=1100,
        notes=[
            "Expect +25-40% VE improvement",
            "Idle quality may require attention",
            "Consider higher idle RPM",
            "Increased fuel demand at all RPMs",
        ],
    ),
    StageLevel.STAGE_4: StagePreset(
        level=StageLevel.STAGE_4,
        display_name="Stage 4 / Race",
        description="Full race build - stroker, ported heads, race cam",
        ve_multiplier_min=0.40,
        ve_multiplier_max=0.60,
        afr_cruise=12.8,
        afr_wot=11.8,
        afr_idle=13.0,
        suggested_clamp=25.0,
        idle_rpm_target=1150,
        notes=[
            "Expect +40-60% VE improvement",
            "May require larger injectors",
            "Idle stability may be challenging",
            "Professional dyno tuning recommended",
            "Consider standalone fuel management",
        ],
    ),
}


def get_stage_preset(level: str) -> StagePreset:
    """Get stage preset by level name."""
    try:
        stage_level = StageLevel(level.lower().replace(" ", "_"))
        return STAGE_PRESETS[stage_level]
    except (ValueError, KeyError):
        return STAGE_PRESETS[StageLevel.STOCK]


def list_stage_presets() -> list[dict[str, Any]]:
    """List all stage presets for dropdown selection."""
    return [preset.to_dict() for preset in STAGE_PRESETS.values()]


# ============================================================================
# Cam Family Presets
# ============================================================================


class CamFamily(Enum):
    """Cam profile families for V-twin engines."""

    STOCK = "stock"
    BOLT_IN = "bolt_in"  # 475-510 lift, mild overlap
    PERFORMANCE = "performance"  # 550+ lift, increased overlap
    RACE = "race"  # Aggressive duration and overlap


@dataclass
class CamPreset:
    """Configuration preset for a cam family."""

    family: CamFamily
    display_name: str
    description: str
    lift_range: str  # e.g., "475-510"

    # Idle characteristics
    idle_vacuum_expected: int  # inches Hg
    idle_rpm_min: int
    idle_rpm_target: int

    # VE table adjustments for idle cells (RPM < 1500, kPa < 40)
    idle_ve_offset: float  # % adjustment to idle VE cells

    # AFR targets
    afr_idle: float
    afr_cruise: float
    afr_wot: float

    # Decel considerations
    decel_enrichment_multiplier: float  # Multiplier for decel enrichment

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "family": self.family.value,
            "display_name": self.display_name,
            "description": self.description,
            "lift_range": self.lift_range,
            "idle_characteristics": {
                "vacuum_expected_hg": self.idle_vacuum_expected,
                "rpm_min": self.idle_rpm_min,
                "rpm_target": self.idle_rpm_target,
                "ve_offset_pct": self.idle_ve_offset,
            },
            "afr_targets": {
                "idle": self.afr_idle,
                "cruise": self.afr_cruise,
                "wot": self.afr_wot,
            },
            "decel_enrichment_multiplier": self.decel_enrichment_multiplier,
            "notes": self.notes,
        }


# Cam family presets
CAM_PRESETS: dict[CamFamily, CamPreset] = {
    CamFamily.STOCK: CamPreset(
        family=CamFamily.STOCK,
        display_name="Stock",
        description="Factory cam profile - smooth idle, emissions compliant",
        lift_range="420-450",
        idle_vacuum_expected=18,
        idle_rpm_min=950,
        idle_rpm_target=1000,
        idle_ve_offset=0.0,
        afr_idle=14.7,
        afr_cruise=14.6,
        afr_wot=13.2,
        decel_enrichment_multiplier=1.0,
        notes=[
            "Good vacuum signal for accessories",
            "Smooth idle quality",
            "Best fuel economy",
        ],
    ),
    CamFamily.BOLT_IN: CamPreset(
        family=CamFamily.BOLT_IN,
        display_name="Bolt-In (475-510)",
        description="Mild performance cam - good street manners",
        lift_range="475-510",
        idle_vacuum_expected=14,
        idle_rpm_min=975,
        idle_rpm_target=1050,
        idle_ve_offset=3.0,  # +3% VE in idle cells
        afr_idle=13.8,
        afr_cruise=13.6,
        afr_wot=12.8,
        decel_enrichment_multiplier=1.15,  # 15% more decel fuel
        notes=[
            "Slight idle lope, acceptable for street",
            "May need idle VE enrichment",
            "Good all-around performance",
            "Popular for Stage 2 builds",
        ],
    ),
    CamFamily.PERFORMANCE: CamPreset(
        family=CamFamily.PERFORMANCE,
        display_name="Performance (550+)",
        description="Aggressive cam - noticeable lope, increased power",
        lift_range="550-585",
        idle_vacuum_expected=10,
        idle_rpm_min=1000,
        idle_rpm_target=1100,
        idle_ve_offset=6.0,  # +6% VE in idle cells
        afr_idle=13.4,
        afr_cruise=13.2,
        afr_wot=12.4,
        decel_enrichment_multiplier=1.25,  # 25% more decel fuel
        notes=[
            "Noticeable idle lope",
            "Low vacuum may affect accessories",
            "Requires idle VE adjustments",
            "May need higher idle RPM",
        ],
    ),
    CamFamily.RACE: CamPreset(
        family=CamFamily.RACE,
        display_name="Race (600+)",
        description="Race cam - rough idle, maximum power",
        lift_range="600+",
        idle_vacuum_expected=6,
        idle_rpm_min=1050,
        idle_rpm_target=1150,
        idle_ve_offset=10.0,  # +10% VE in idle cells
        afr_idle=13.0,
        afr_cruise=12.8,
        afr_wot=11.8,
        decel_enrichment_multiplier=1.35,  # 35% more decel fuel
        notes=[
            "Rough idle expected",
            "May not idle well when hot",
            "Very low vacuum",
            "Consider standalone fuel management",
            "Professional tuning recommended",
        ],
    ),
}


def get_cam_preset(family: str) -> CamPreset:
    """Get cam preset by family name."""
    try:
        cam_family = CamFamily(family.lower().replace("-", "_").replace(" ", "_"))
        return CAM_PRESETS[cam_family]
    except (ValueError, KeyError):
        return CAM_PRESETS[CamFamily.STOCK]


def list_cam_presets() -> list[dict[str, Any]]:
    """List all cam presets for dropdown selection."""
    return [preset.to_dict() for preset in CAM_PRESETS.values()]


def generate_idle_ve_overlay(
    cam_preset: CamPreset,
    rpm_bins: list[int] | None = None,
    kpa_bins: list[int] | None = None,
) -> list[list[float]]:
    """
    Generate VE overlay for idle cells based on cam preset.

    Args:
        cam_preset: Cam family preset
        rpm_bins: RPM bin values (default: standard bins)
        kpa_bins: kPa bin values (default: standard bins)

    Returns:
        2D list of VE adjustments (percentages)
    """
    if rpm_bins is None:
        rpm_bins = list(RPM_BINS)
    if kpa_bins is None:
        kpa_bins = list(KPA_BINS)

    overlay = [[0.0 for _ in kpa_bins] for _ in rpm_bins]

    # Apply idle VE offset to low RPM, low kPa cells
    for i, rpm in enumerate(rpm_bins):
        for j, kpa in enumerate(kpa_bins):
            # Idle zone: RPM < 1500, kPa < 45
            if rpm <= 1500 and kpa <= 45:
                # Full offset at very low RPM/load, tapering off
                rpm_factor = max(0, 1 - (rpm - 800) / 700)  # Tapers from 800-1500
                kpa_factor = max(0, 1 - (kpa - 20) / 25)  # Tapers from 20-45

                overlay[i][j] = cam_preset.idle_ve_offset * rpm_factor * kpa_factor

    return overlay


# ============================================================================
# Heat Soak Warning System
# ============================================================================


@dataclass
class PullMetrics:
    """Metrics from a single dyno pull."""

    pull_number: int
    peak_hp: float
    peak_torque: float
    peak_rpm: int
    iat_start: float
    iat_end: float
    iat_peak: float
    ambient_temp: Optional[float] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pull_number": self.pull_number,
            "peak_hp": round(self.peak_hp, 1),
            "peak_torque": round(self.peak_torque, 1),
            "peak_rpm": self.peak_rpm,
            "iat": {
                "start": round(self.iat_start, 1),
                "end": round(self.iat_end, 1),
                "peak": round(self.iat_peak, 1),
            },
            "ambient_temp": round(self.ambient_temp, 1) if self.ambient_temp else None,
            "timestamp": self.timestamp,
        }


@dataclass
class HeatSoakAnalysis:
    """Analysis of heat soak across multiple pulls."""

    pulls: list[PullMetrics]
    hp_degradation_pct: float  # % HP loss from first to last
    is_heat_soaked: bool  # True if degradation > 3%
    confidence: float  # 0-1 confidence in the assessment
    baseline_pull: int  # Which pull represents "cold" baseline
    recommendation: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_pulls": len(self.pulls),
                "hp_degradation_pct": round(self.hp_degradation_pct, 1),
                "is_heat_soaked": self.is_heat_soaked,
                "confidence": round(self.confidence, 2),
                "baseline_pull": self.baseline_pull,
            },
            "recommendation": self.recommendation,
            "warnings": self.warnings,
            "pulls": [p.to_dict() for p in self.pulls],
        }


def analyze_heat_soak(pulls: list[PullMetrics]) -> HeatSoakAnalysis:
    """
    Analyze HP degradation across sequential dyno pulls.

    Args:
        pulls: List of pull metrics in order

    Returns:
        HeatSoakAnalysis with recommendations
    """
    if len(pulls) < 2:
        return HeatSoakAnalysis(
            pulls=pulls,
            hp_degradation_pct=0.0,
            is_heat_soaked=False,
            confidence=0.0,
            baseline_pull=1,
            recommendation="Need at least 2 pulls to analyze heat soak",
            warnings=["Insufficient data for analysis"],
        )

    # Find the pull with highest HP (likely the "coldest" baseline)
    baseline_idx = max(range(len(pulls)), key=lambda i: pulls[i].peak_hp)
    baseline_hp = pulls[baseline_idx].peak_hp

    # Calculate degradation from baseline to most recent
    latest_hp = pulls[-1].peak_hp
    hp_degradation = ((baseline_hp - latest_hp) / baseline_hp) * 100

    # Check IAT trends
    iat_increase = pulls[-1].iat_end - pulls[0].iat_start

    # Determine confidence based on data consistency
    hp_trend_consistent = all(
        pulls[i].peak_hp >= pulls[i + 1].peak_hp - 1.0  # Allow 1 HP variance
        for i in range(len(pulls) - 1)
    )

    confidence = 0.5  # Base confidence
    if hp_trend_consistent:
        confidence += 0.3
    if iat_increase > 20:  # IAT rose significantly
        confidence += 0.2

    # Determine if heat soaked (>3% degradation threshold from research)
    is_heat_soaked = hp_degradation > 3.0

    # Generate recommendations
    warnings = []
    if is_heat_soaked:
        if hp_degradation > 5.0:
            recommendation = (
                f"SEVERE HEAT SOAK: {hp_degradation:.1f}% HP loss detected. "
                "Allow 10+ minutes of cool-down before next pull. "
                "Consider baseline data unreliable for tuning."
            )
            warnings.append("Data from later pulls may not be suitable for tuning")
        else:
            recommendation = (
                f"MODERATE HEAT SOAK: {hp_degradation:.1f}% HP loss detected. "
                "Allow 5 minutes of cool-down. "
                f"Use pull #{baseline_idx + 1} as baseline reference."
            )
    else:
        if hp_degradation > 1.5:
            recommendation = (
                f"MINOR HEAT INFLUENCE: {hp_degradation:.1f}% variation detected. "
                "Data is usable but consider cool-down for consistency."
            )
        else:
            recommendation = (
                "GOOD: Minimal heat soak detected. Data is reliable for tuning."
            )

    # Additional warnings
    if iat_increase > 30:
        warnings.append(f"IAT increased {iat_increase:.0f}°F during session")

    if pulls[-1].iat_peak > 150:
        warnings.append(f"Peak IAT of {pulls[-1].iat_peak:.0f}°F may affect accuracy")

    return HeatSoakAnalysis(
        pulls=pulls,
        hp_degradation_pct=hp_degradation,
        is_heat_soaked=is_heat_soaked,
        confidence=confidence,
        baseline_pull=baseline_idx + 1,  # 1-indexed for display
        recommendation=recommendation,
        warnings=warnings,
    )


# ============================================================================
# Decel Pop Wizard (One-Click Fix)
# ============================================================================


@dataclass
class DecelWizardResult:
    """Result from the one-click Decel Pop Wizard."""

    success: bool
    severity_applied: str
    cells_modified: int
    rpm_range: tuple[int, int]
    enrichment_preview: dict[str, Any]  # Summary of what was changed
    overlay_data: list[list[float]]  # The actual VE overlay
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "severity_applied": self.severity_applied,
            "cells_modified": self.cells_modified,
            "rpm_range": list(self.rpm_range),
            "enrichment_preview": self.enrichment_preview,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


def generate_decel_fix_overlay(
    severity: str = "medium",
    rpm_min: int = 1750,
    rpm_max: int = 5500,
    cam_family: str = "stock",
    rpm_bins: list[int] | None = None,
    kpa_bins: list[int] | None = None,
) -> DecelWizardResult:
    """
    Generate a one-click decel pop fix overlay.

    This is the "magic" - a proven enrichment pattern that eliminates
    decel popping in V-twin engines with aftermarket exhausts.

    Args:
        severity: 'low', 'medium', or 'high' enrichment
        rpm_min: Minimum RPM for decel zone
        rpm_max: Maximum RPM for decel zone
        cam_family: Cam type for enrichment adjustment
        rpm_bins: RPM bin values
        kpa_bins: kPa bin values

    Returns:
        DecelWizardResult with overlay and metadata
    """
    if rpm_bins is None:
        rpm_bins = list(RPM_BINS)
    if kpa_bins is None:
        kpa_bins = list(KPA_BINS)

    # Get cam multiplier
    cam_preset = get_cam_preset(cam_family)
    cam_multiplier = cam_preset.decel_enrichment_multiplier

    # Base enrichment percentages by severity
    # These are validated values that work for most setups
    severity_base = {
        "low": 0.12,  # +12% base
        "medium": 0.18,  # +18% base (recommended)
        "high": 0.25,  # +25% base (aggressive)
    }

    base_enrichment = severity_base.get(severity.lower(), 0.18)

    # RPM-based taper: More enrichment at low RPM where pop is worst
    # Less at high RPM where airflow naturally helps
    def rpm_factor(rpm: int) -> float:
        if rpm < 2000:
            return 1.2  # Maximum enrichment
        elif rpm < 3000:
            return 1.0  # Full enrichment
        elif rpm < 4000:
            return 0.8  # Reduced
        else:
            return 0.6  # Minimum needed

    # kPa-based mask: Only apply to vacuum/low-load cells (0% throttle territory)
    # Decel pop happens at low MAP (high vacuum)
    MAX_DECEL_KPA = 45

    overlay = [[0.0 for _ in kpa_bins] for _ in rpm_bins]
    cells_modified = 0
    enrichment_summary: dict[str, Any] = {
        "by_rpm_zone": {},
        "max_enrichment": 0.0,
        "avg_enrichment": 0.0,
    }
    enrichment_values: list[float] = []

    for i, rpm in enumerate(rpm_bins):
        # Only apply within the specified RPM range
        if not (rpm_min <= rpm <= rpm_max):
            continue

        for j, kpa in enumerate(kpa_bins):
            # Only apply to low-load (decel) cells
            if kpa > MAX_DECEL_KPA:
                continue

            # Calculate enrichment with all factors
            # Lower kPa = more vacuum = more enrichment needed
            kpa_factor = 1 - (kpa / MAX_DECEL_KPA) * 0.4  # 1.0 at 0 kPa, 0.6 at max

            enrichment = base_enrichment * rpm_factor(rpm) * kpa_factor * cam_multiplier

            # Cap at reasonable maximum (30%)
            enrichment = min(enrichment, 0.30)

            overlay[i][j] = enrichment
            cells_modified += 1
            enrichment_values.append(enrichment)

            # Track by RPM zone
            zone = f"{(rpm // 1000) * 1000}-{((rpm // 1000) + 1) * 1000}"
            if zone not in enrichment_summary["by_rpm_zone"]:
                enrichment_summary["by_rpm_zone"][zone] = []
            enrichment_summary["by_rpm_zone"][zone].append(enrichment)

    # Calculate summary stats
    if enrichment_values:
        enrichment_summary["max_enrichment"] = round(max(enrichment_values) * 100, 1)
        enrichment_summary["avg_enrichment"] = round(
            sum(enrichment_values) / len(enrichment_values) * 100, 1
        )

    # Simplify zone summary to averages
    for zone, values in enrichment_summary["by_rpm_zone"].items():
        enrichment_summary["by_rpm_zone"][zone] = round(
            sum(values) / len(values) * 100, 1
        )

    # Generate warnings and recommendations
    warnings = []
    recommendations = []

    if severity == "high":
        warnings.append("HIGH severity may impact fuel economy during engine braking")

    if cam_preset.family in (CamFamily.PERFORMANCE, CamFamily.RACE):
        recommendations.append(
            "With aggressive cams, consider PAIR valve block-off for best results"
        )

    recommendations.extend(
        [
            "Apply overlay to 0% throttle column in VE table",
            "Re-test after applying to verify popping elimination",
            "Minor fuel economy reduction during decel is expected",
        ]
    )

    return DecelWizardResult(
        success=True,
        severity_applied=severity,
        cells_modified=cells_modified,
        rpm_range=(rpm_min, rpm_max),
        enrichment_preview=enrichment_summary,
        overlay_data=overlay,
        warnings=warnings,
        recommendations=recommendations,
    )


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    # Stage presets
    "StageLevel",
    "StagePreset",
    "STAGE_PRESETS",
    "get_stage_preset",
    "list_stage_presets",
    # Cam presets
    "CamFamily",
    "CamPreset",
    "CAM_PRESETS",
    "get_cam_preset",
    "list_cam_presets",
    "generate_idle_ve_overlay",
    # Heat soak
    "PullMetrics",
    "HeatSoakAnalysis",
    "analyze_heat_soak",
    # Decel wizard
    "DecelWizardResult",
    "generate_decel_fix_overlay",
]
