"""
DynoAI AI Training Data Schemas

Defines data structures for capturing V-twin tuning patterns to train AI models
for automated per-cylinder balancing, decel management, timing optimization,
and heat soak compensation.

These schemas are designed to capture:
1. Build configuration patterns (cam specs, stage progression)
2. Tuning session outcomes (VE changes, AFR targets, timing adjustments)
3. Cylinder-to-cylinder variation patterns
4. Decel popping characteristics and solutions
5. Heat soak thermal drift patterns
6. Knock detection and timing optimization patterns
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ============================================================================
# Build Configuration - Captures learnable patterns from engine setups
# ============================================================================


class EngineFamily(str, Enum):
    """Harley-Davidson engine families."""

    TWIN_CAM = "twin_cam"  # 88/96/103/110 Twin Cam (1999-2016)
    MILWAUKEE_EIGHT = "milwaukee_eight"  # M8 107/114/117 (2017+)
    EVOLUTION = "evolution"  # Evo 80/88 (1984-1999)
    REVOLUTION = "revolution"  # V-Rod (2001-2017)
    SPORTSTER = "sportster"  # 883/1200 (1986+)


class CamProfile(str, Enum):
    """Common aftermarket cam profiles with known characteristics."""

    STOCK = "stock"
    S_AND_S_475 = "s_and_s_475"  # Bolt-in, moderate overlap
    S_AND_S_585 = "s_and_s_585"  # High overlap, significant idle change
    S_AND_S_590 = "s_and_s_590"  # High performance
    WOOD_TW222 = "wood_tw222"  # Short duration, easy tune
    FEULING_574 = "feuling_574"  # Moderate, linear power
    ANDREWS_21 = "andrews_21"  # Mild street cam
    ANDREWS_26 = "andrews_26"  # Hot street cam
    REDSHIFT_509 = "redshift_509"  # High-lift performance
    CUSTOM = "custom"


class StageLevel(str, Enum):
    """Modification stage levels with predictable VE scaling patterns."""

    STOCK = "stock"  # Factory configuration
    STAGE_1 = "stage_1"  # Air cleaner + exhaust (+8-15% VE typical)
    STAGE_2 = "stage_2"  # Stage 1 + cam (+15-25% VE typical)
    STAGE_3 = "stage_3"  # Stage 2 + big bore (+20-35% VE typical)
    STAGE_4 = "stage_4"  # Full build (+30-50% VE typical)


@dataclass
class CamSpecification:
    """Detailed cam specs that affect VE patterns."""

    profile: CamProfile
    intake_duration_deg: float  # @ 0.053" lift
    exhaust_duration_deg: float
    intake_lift_in: float
    exhaust_lift_in: float
    lobe_separation_angle_deg: float  # LSA
    overlap_deg_front: float  # Overlap at front cylinder
    overlap_deg_rear: float  # Overlap at rear cylinder
    idle_rpm_target: int = 1000  # Recommended idle RPM

    def get_overlap_category(self) -> str:
        """Categorize overlap for pattern matching."""
        avg_overlap = (self.overlap_deg_front + self.overlap_deg_rear) / 2
        if avg_overlap < 20:
            return "low"
        elif avg_overlap < 35:
            return "moderate"
        else:
            return "high"


@dataclass
class BuildConfiguration:
    """Complete engine build configuration for pattern matching."""

    # Engine basics
    engine_family: EngineFamily
    displacement_ci: int  # Cubic inches (e.g., 103, 114)
    compression_ratio: float  # Static CR
    bore_in: float
    stroke_in: float

    # Stage level
    stage: StageLevel

    # Induction
    cam_spec: CamSpecification
    air_cleaner: str  # Brand/model
    throttle_body_mm: int = 50  # Throttle body diameter

    # Exhaust
    header_type: str = "2-into-1"  # "2-into-1", "true dual", "slip-on"
    muffler_type: str = ""
    header_diameter_in: float = 1.75

    # Fuel
    injector_flow_lb_hr: float = 4.5  # Stock ~4.5 lb/hr
    fuel_pump_type: str = "stock"

    # Octane requirement
    octane_requirement: int = 91  # Minimum octane rating

    # ECM
    ecm_type: str = "delphi"  # "delphi", "thundermax", "daytona_twin_tec"
    tuning_software: str = "power_vision"  # Platform used

    # Build metadata
    builder: Optional[str] = None
    build_date: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# Data Provenance - Track data authenticity and source
# ============================================================================


@dataclass
class DataProvenance:
    """
    Track data source and authenticity for quality assurance.

    Enables verification of data origin and establishes chain of custody
    for training data used in AI models.
    """

    # Who collected it
    tuner_id: str
    tuner_certification: Optional[str] = None  # "Dynojet Certified", "Fuel Moto", etc.
    shop_name: str = ""
    shop_location: str = ""  # "City, State"

    # What equipment
    dyno_serial_number: Optional[str] = None
    dyno_calibration_date: Optional[str] = None
    wideband_model: str = ""  # "Innovate LC-2", "AEM X-Series", etc.
    wideband_calibration_date: Optional[str] = None
    tuning_software: str = ""  # "Power Vision 3.1.0", "TTS Mastertune"

    # Original data files
    log_file_name: str = ""
    log_file_hash: Optional[str] = None  # SHA256 hash for verification
    log_file_size_bytes: int = 0

    # Verification flags
    peer_reviewed: bool = False
    reviewed_by: Optional[str] = None
    review_date: Optional[str] = None
    verified_on_dyno: bool = False  # Results physically reproduced

    # Quality indicators
    data_completeness_score: float = 0.0  # 0-100% based on required fields
    confidence_level: str = "medium"  # low/medium/high

    # Metadata
    collection_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""

    @staticmethod
    def calculate_file_hash(file_path: str | Path) -> str:
        """Calculate SHA256 hash of file for verification."""
        sha256_hash = hashlib.sha256()
        file_path = Path(file_path)

        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()


# ============================================================================
# Tuning Session Data - Captures complete tuning context and outcomes
# ============================================================================


class TuningObjective(str, Enum):
    """Primary goal of tuning session."""

    BASELINE = "baseline"  # Initial tune after build
    VE_OPTIMIZATION = "ve_optimization"  # VE table refinement
    TIMING_OPTIMIZATION = "timing_optimization"  # Spark advance tuning
    CYLINDER_BALANCE = "cylinder_balance"  # Per-cylinder AFR equalization
    DECEL_POP_FIX = "decel_pop_fix"  # Eliminate decel popping
    HEAT_SOAK_FIX = "heat_soak_fix"  # Compensate for IAT drift
    ALTITUDE_COMP = "altitude_compensation"  # High-altitude tuning
    DIAGNOSTIC = "diagnostic"  # Troubleshooting


@dataclass
class EnvironmentalConditions:
    """Atmospheric conditions during tuning session."""

    ambient_temp_f: float
    barometric_pressure_inhg: float
    humidity_percent: float
    altitude_ft: int
    correction_factor: float = 1.0  # SAE J1349 or similar

    def is_standard_day(self) -> bool:
        """Check if conditions are near standard (77°F, 29.92" Hg, sea level)."""
        return (
            70 <= self.ambient_temp_f <= 85
            and 29.5 <= self.barometric_pressure_inhg <= 30.3
            and self.altitude_ft < 1000
        )


@dataclass
class DynoSessionMetadata:
    """Dyno test session information."""

    dyno_type: str  # "Dynojet 250i", "Mainline", etc.
    load_type: str = "inertia"  # "inertia", "eddy_current", "water_brake"
    fan_airflow_cfm: Optional[int] = None  # Cooling fan capacity
    warmup_time_min: int = 10  # Warmup duration before testing
    cooldown_time_min: int = 5  # Cooldown between pulls
    runs_performed: int = 0
    smoothing_factor: int = 4  # Dyno smoothing setting


@dataclass
class TuningSession:
    """
    Complete tuning session data for AI training.

    This captures the full context needed to learn VE scaling patterns,
    AFR targets, timing limits, and cylinder-specific adjustments.
    """

    # Session identification (required)
    session_id: str
    timestamp_utc: str

    # Build configuration (required)
    build_config: BuildConfiguration

    # Tuning objectives (required)
    objective: TuningObjective

    # Environmental conditions (required)
    conditions: EnvironmentalConditions

    # Dyno metadata (required)
    dyno_metadata: DynoSessionMetadata

    # Optional tracking
    tuner_id: Optional[str] = None  # For tracking tuner expertise
    provenance: Optional[DataProvenance] = None
    previous_tune_hours: float = 0.0  # Hours since last tune

    # Pre-tune state
    initial_ve_table_front: List[List[float]] = field(default_factory=list)
    initial_ve_table_rear: List[List[float]] = field(default_factory=list)
    initial_spark_table_front: List[List[float]] = field(default_factory=list)
    initial_spark_table_rear: List[List[float]] = field(default_factory=list)

    # Post-tune state (outcomes)
    final_ve_table_front: List[List[float]] = field(default_factory=list)
    final_ve_table_rear: List[List[float]] = field(default_factory=list)
    final_spark_table_front: List[List[float]] = field(default_factory=list)
    final_spark_table_rear: List[List[float]] = field(default_factory=list)

    # Target AFR strategy used
    afr_targets: Dict[str, float] = field(
        default_factory=dict
    )  # e.g., {"cruise": 13.8, "wot": 12.8}

    # Results
    peak_hp: float = 0.0
    peak_torque: float = 0.0
    afr_accuracy_rms_error: float = 0.0  # How close AFR stayed to targets

    # Cylinder balance achieved
    max_cylinder_afr_delta: float = 0.0  # Max AFR difference between cylinders

    # Timing optimization
    knock_events_detected: int = 0
    timing_retard_cells: int = 0  # Cells where timing was retarded
    timing_advance_cells: int = 0  # Cells where timing was advanced

    # Decel management
    decel_pop_severity_before: int = 0  # 0-10 scale
    decel_pop_severity_after: int = 0

    # Heat soak impact
    iat_start_f: float = 0.0
    iat_end_f: float = 0.0
    iat_peak_f: float = 0.0
    hp_variation_due_to_heat: float = 0.0  # Max HP variation between hot/cold runs

    # Time investment
    tuning_duration_hours: float = 0.0
    iterations_required: int = 0  # Number of tune-test-adjust cycles

    # Quality metrics
    tuner_satisfaction: Optional[int] = None  # 1-10 scale
    customer_satisfaction: Optional[int] = None

    # Notes and lessons learned
    challenges_encountered: List[str] = field(default_factory=list)
    solutions_applied: List[str] = field(default_factory=list)
    notes: str = ""


# ============================================================================
# VE Pattern Training Data
# ============================================================================


@dataclass
class VEScalingPattern:
    """
    Captures VE change patterns for different build configurations.

    Used to train AI to predict base VE tables from build specs.
    """

    # Build context
    engine_family: EngineFamily
    stage: StageLevel
    cam_overlap_category: str  # "low", "moderate", "high"
    displacement_ci: int

    # VE changes from stock (percentage)
    ve_delta_idle: float  # VE change at idle (1000 RPM, low load)
    ve_delta_cruise: float  # VE change at cruise (2500 RPM, 30 kPa)
    ve_delta_midrange: float  # VE change at midrange (3500 RPM, 60 kPa)
    ve_delta_wot: float  # VE change at WOT (4500 RPM, 95 kPa)

    # Cylinder-specific deltas (if asymmetric)
    front_rear_ve_difference_pct: float = 0.0

    # Sample count (confidence metric)
    sessions_observed: int = 1


@dataclass
class AFRTargetPattern:
    """
    Captures AFR target strategies for different operating conditions.

    Used to train AI on context-dependent AFR targets (altitude, temperature, etc.).
    """

    # Operating condition
    operating_region: str  # "idle", "cruise", "wot", "decel"
    rpm_range: Tuple[int, int]  # RPM bounds
    load_range: Tuple[int, int]  # kPa bounds

    # Target AFR
    target_afr: float
    acceptable_range: Tuple[float, float]  # (min, max) acceptable

    # Context factors
    altitude_ft: int = 0
    ambient_temp_f: float = 77.0
    engine_temp_hot: bool = True  # Cold vs hot engine

    # Fuel type
    fuel_octane: int = 91
    fuel_type: str = "gasoline"  # "gasoline", "e85", "race_gas"

    # Reasoning
    rationale: str = ""  # Why this AFR target


# ============================================================================
# Cylinder Balancing Training Data
# ============================================================================


@dataclass
class CylinderImbalancePattern:
    """
    Captures cylinder-to-cylinder AFR imbalance patterns and corrections.

    Used to train AI to predict imbalance and generate correction factors.
    """

    # Configuration that caused imbalance
    engine_family: EngineFamily
    cam_profile: CamProfile
    exhaust_type: str  # "2-into-1", "true dual"
    header_length_delta_in: float = 0.0  # Front vs rear header length difference

    # Observed imbalance
    imbalance_cells: List[Tuple[int, int, float]] = field(default_factory=list)
    # Format: [(rpm_idx, kpa_idx, afr_delta), ...]
    # afr_delta = rear_afr - front_afr (positive = rear richer)

    # Root cause (if identified)
    primary_cause: str = (
        "unknown"  # "firing_interval", "heat_differential", "exhaust_scavenging"
    )

    # Correction applied (VE adjustment percentages)
    front_ve_corrections: List[List[float]] = field(default_factory=list)
    rear_ve_corrections: List[List[float]] = field(default_factory=list)

    # Outcome
    imbalance_before_max: float = 0.0  # Max AFR delta before correction
    imbalance_after_max: float = 0.0  # Max AFR delta after correction
    correction_success: bool = False


# ============================================================================
# Decel Management Training Data
# ============================================================================


@dataclass
class DecelPoppingPattern:
    """
    Captures deceleration popping characteristics and solutions.

    Used to train AI to automatically generate decel fuel management overlays.
    """

    # Engine configuration
    engine_family: EngineFamily
    cam_overlap_deg: float
    exhaust_type: str
    pair_valve_present: bool = True  # Air injection valve

    # Pop characteristics
    pop_severity: int = 0  # 0-10 scale (10 = gunshot backfires)
    pop_rpm_range: Tuple[int, int] = (1500, 3500)  # Where popping occurs
    pop_throttle_position: float = 0.0  # TPS at onset (usually 0-7%)

    # AFR behavior during decel
    decel_afr_spike_max: float = 0.0  # Peak lean spike during decel
    decel_afr_baseline: float = 14.7  # Normal decel AFR

    # Enrichment solution applied
    enrichment_zones: List[Tuple[int, int, int, int, float]] = field(
        default_factory=list
    )
    # Format: [(rpm_min, rpm_max, tps_min, tps_max, enrichment_pct), ...]

    # Outcome
    pop_eliminated: bool = False
    fuel_economy_impact_pct: float = 0.0  # Negative = loss
    customer_satisfaction: int = 0  # 1-10 scale


# ============================================================================
# Heat Soak Training Data
# ============================================================================


@dataclass
class HeatSoakPattern:
    """
    Captures IAT heat soak patterns and correction strategies.

    Used to train AI to predict and compensate for thermal drift.
    """

    # Environmental conditions
    ambient_temp_f: float
    airflow_cfm: Optional[int] = None  # Fan airflow during dyno testing

    # Thermal progression
    iat_initial_f: float
    iat_peak_f: float
    iat_soak_time_min: float  # Time above soak threshold
    engine_temp_f: Optional[float] = None

    # VE drift observed
    ve_inflation_pct: float = 0.0  # How much VE was artificially inflated
    affected_rpm_range: Tuple[int, int] = (1000, 3500)  # Usually low RPM
    affected_load_range: Tuple[int, int] = (20, 60)  # Usually cruise/idle

    # Correction applied
    heat_correction_overlay: List[List[float]] = field(default_factory=list)
    # Negative values = remove artificial VE inflation

    # Outcome
    hp_variation_before: float = 0.0  # HP swing hot vs cold before correction
    hp_variation_after: float = 0.0  # HP swing after correction


# ============================================================================
# Knock & Timing Training Data
# ============================================================================


@dataclass
class KnockTimingPattern:
    """
    Captures knock characteristics and timing optimization outcomes.

    Used to train AI to find MBT timing while avoiding knock.
    """

    # Engine configuration
    compression_ratio: float
    fuel_octane: int
    cam_profile: CamProfile
    altitude_ft: int = 0

    # Knock characteristics
    knock_cells: List[Tuple[int, int, int]] = field(default_factory=list)
    # Format: [(rpm_idx, kpa_idx, knock_event_count), ...]

    knock_severity_max: float = 0.0  # Max retard observed (degrees)
    knock_false_positive_rate: float = 0.0  # Ion sensing false knock %

    # Timing strategy
    initial_timing_table: List[List[float]] = field(default_factory=list)
    final_timing_table: List[List[float]] = field(default_factory=list)

    # Per-cell timing changes
    timing_retards: List[Tuple[int, int, float]] = field(default_factory=list)
    # Format: [(rpm_idx, kpa_idx, retard_deg), ...]

    timing_advances: List[Tuple[int, int, float]] = field(default_factory=list)
    # Format: [(rpm_idx, kpa_idx, advance_deg), ...]

    # Outcome
    mbt_achieved: bool = False  # Did we find MBT?
    torque_gain_pct: float = 0.0  # Torque improvement from timing optimization
    knock_free: bool = False  # Zero knock after tuning


# ============================================================================
# Composite Training Dataset
# ============================================================================


@dataclass
class TrainingDataset:
    """
    Complete training dataset for DynoAI machine learning models.

    Aggregates all pattern types for comprehensive AI training.
    """

    # Dataset metadata
    dataset_id: str
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    contributor: Optional[str] = None

    # Tuning sessions (raw data)
    tuning_sessions: List[TuningSession] = field(default_factory=list)

    # Extracted patterns
    ve_scaling_patterns: List[VEScalingPattern] = field(default_factory=list)
    afr_target_patterns: List[AFRTargetPattern] = field(default_factory=list)
    cylinder_imbalance_patterns: List[CylinderImbalancePattern] = field(
        default_factory=list
    )
    decel_popping_patterns: List[DecelPoppingPattern] = field(default_factory=list)
    heat_soak_patterns: List[HeatSoakPattern] = field(default_factory=list)
    knock_timing_patterns: List[KnockTimingPattern] = field(default_factory=list)

    # Statistics
    total_sessions: int = 0
    total_dyno_hours: float = 0.0
    engines_covered: int = 0
    tuners_contributed: int = 0

    def add_session(self, session: TuningSession) -> None:
        """Add a tuning session to the dataset."""
        self.tuning_sessions.append(session)
        self.total_sessions += 1
        self.total_dyno_hours += session.tuning_duration_hours

    def summary(self) -> Dict[str, Any]:
        """Generate dataset summary statistics."""
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "total_sessions": self.total_sessions,
            "total_dyno_hours": round(self.total_dyno_hours, 1),
            "engines_covered": self.engines_covered,
            "tuners_contributed": self.tuners_contributed,
            "pattern_counts": {
                "ve_scaling": len(self.ve_scaling_patterns),
                "afr_targets": len(self.afr_target_patterns),
                "cylinder_imbalance": len(self.cylinder_imbalance_patterns),
                "decel_popping": len(self.decel_popping_patterns),
                "heat_soak": len(self.heat_soak_patterns),
                "knock_timing": len(self.knock_timing_patterns),
            },
        }


# ============================================================================
# Helper Functions for Pattern Extraction
# ============================================================================


def extract_ve_scaling_pattern(session: TuningSession) -> VEScalingPattern:
    """
    Extract VE scaling pattern from a completed tuning session.

    Calculates VE deltas in key operating regions.
    """
    # Calculate average VE changes in different regions
    # This would analyze initial vs final VE tables

    # Idle region (RPM 0, KPA 0-1)
    idle_delta = 0.0
    if session.initial_ve_table_front and session.final_ve_table_front:
        # Calculate percentage change
        pass  # Implementation would compute actual deltas

    return VEScalingPattern(
        engine_family=session.build_config.engine_family,
        stage=session.build_config.stage,
        cam_overlap_category=session.build_config.cam_spec.get_overlap_category(),
        displacement_ci=session.build_config.displacement_ci,
        ve_delta_idle=idle_delta,
        ve_delta_cruise=0.0,
        ve_delta_midrange=0.0,
        ve_delta_wot=0.0,
        sessions_observed=1,
    )


def extract_cylinder_imbalance_pattern(
    session: TuningSession, imbalance_data: List[Tuple[int, int, float]]
) -> CylinderImbalancePattern:
    """
    Extract cylinder imbalance pattern from balancing session.

    Args:
        session: Tuning session with cylinder balance objective
        imbalance_data: Detected AFR deltas [(rpm_idx, kpa_idx, delta), ...]
    """
    return CylinderImbalancePattern(
        engine_family=session.build_config.engine_family,
        cam_profile=session.build_config.cam_spec.profile,
        exhaust_type=session.build_config.header_type,
        imbalance_cells=imbalance_data,
        front_ve_corrections=session.final_ve_table_front,
        rear_ve_corrections=session.final_ve_table_rear,
        imbalance_before_max=session.max_cylinder_afr_delta,
        imbalance_after_max=0.0,  # Would be measured post-correction
        correction_success=session.max_cylinder_afr_delta < 0.3,
    )


__all__ = [
    # Enums
    "EngineFamily",
    "CamProfile",
    "StageLevel",
    "TuningObjective",
    # Build configuration
    "CamSpecification",
    "BuildConfiguration",
    # Data provenance
    "DataProvenance",
    # Session data
    "EnvironmentalConditions",
    "DynoSessionMetadata",
    "TuningSession",
    # Pattern types
    "VEScalingPattern",
    "AFRTargetPattern",
    "CylinderImbalancePattern",
    "DecelPoppingPattern",
    "HeatSoakPattern",
    "KnockTimingPattern",
    # Dataset
    "TrainingDataset",
    # Helper functions
    "extract_ve_scaling_pattern",
    "extract_cylinder_imbalance_pattern",
]
