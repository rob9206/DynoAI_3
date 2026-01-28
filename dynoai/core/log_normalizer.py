"""
DynoAI NextGen Log Normalizer

Normalizes different upstream data sources into canonical column names for NextGen analysis.
Implements graceful degradation when optional channels are missing.

Canonical Channels:
    Required: rpm, map_kpa, tps, iat
    Per-cylinder (preferred): afr_meas_f, afr_meas_r, afr_cmd_f, afr_cmd_r, spark_f, spark_r
    Global fallbacks: afr_meas, afr_cmd, spark
    Optional: knock, knock_f, knock_r, ect, vbatt, torque, time_ms

Usage:
    from dynoai.core.log_normalizer import normalize_dataframe

    result = normalize_dataframe(df)
    normalized_df = result.df
    print(f"Found columns: {result.columns_found}")
    print(f"Missing columns: {result.columns_missing}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pandas as pd

__all__ = [
    "NormalizationResult",
    "ChannelPresence",
    "ChannelWarning",
    "ChannelReadiness",
    "normalize_dataframe",
    "detect_columns",
    "get_channel_readiness",
    "CANONICAL_COLUMNS",
    "COLUMN_ALIASES",
    "WARNING_CODES",
]

# =============================================================================
# Stable Warning Codes (for tests and programmatic use)
# =============================================================================

WARNING_CODES = {
    # Missing channel warnings
    "missing_channel:rpm":
    "Required channel 'rpm' not found",
    "missing_channel:map_kpa":
    "Required channel 'map_kpa' not found",
    "missing_channel:tps":
    "Throttle position (tps) not found - mode detection may be less accurate",
    "missing_channel:iat":
    "Intake air temp (iat) not found - heat soak detection disabled",
    "missing_channel:ect":
    "Coolant temp (ect) not found - thermal analysis limited",
    "missing_channel:afr_meas":
    "No AFR measurement found - AFR analysis disabled",
    "missing_channel:afr_meas_f":
    "Front cylinder AFR not found - using global AFR",
    "missing_channel:afr_meas_r":
    "Rear cylinder AFR not found - using global AFR",
    "missing_channel:afr_cmd":
    "No commanded AFR found - using stoich (14.7) default",
    "missing_channel:afr_cmd_f":
    "Front cylinder AFR target not found",
    "missing_channel:afr_cmd_r":
    "Rear cylinder AFR target not found",
    "missing_channel:spark":
    "No spark timing found - spark valley analysis disabled",
    "missing_channel:spark_f":
    "Front cylinder spark not found - using global spark",
    "missing_channel:spark_r":
    "Rear cylinder spark not found - using global spark",
    "missing_channel:knock":
    "No knock data found - knock-based reasoning disabled",
    "missing_channel:knock_f":
    "Front cylinder knock not found",
    "missing_channel:knock_r":
    "Rear cylinder knock not found",
    # Degraded mode warnings
    "degraded:per_cylinder_afr":
    "Using global AFR for both cylinders (no per-cylinder data)",
    "degraded:per_cylinder_spark":
    "Using global spark for both cylinders (no per-cylinder data)",
    "degraded:afr_cmd_default":
    "No commanded AFR found, using stoich (14.7) as default",
}

# =============================================================================
# Canonical Column Definitions
# =============================================================================

# Required channels for basic analysis
REQUIRED_COLUMNS = ["rpm", "map_kpa"]

# Preferred per-cylinder channels
PER_CYLINDER_COLUMNS = [
    "afr_meas_f",
    "afr_meas_r",
    "afr_cmd_f",
    "afr_cmd_r",
    "spark_f",
    "spark_r",
]

# Global fallback channels (used when per-cylinder not available)
GLOBAL_FALLBACK_COLUMNS = [
    "afr_meas",
    "afr_cmd",
    "spark",
]

# Optional channels that enhance analysis
OPTIONAL_COLUMNS = [
    "tps",
    "iat",
    "ect",
    "vbatt",
    "torque",
    "knock",
    "knock_f",
    "knock_r",
    "time_ms",
    "timestamp",
]

# All canonical columns
CANONICAL_COLUMNS = (REQUIRED_COLUMNS + PER_CYLINDER_COLUMNS +
                     GLOBAL_FALLBACK_COLUMNS + OPTIONAL_COLUMNS)

# =============================================================================
# Column Alias Mappings
# =============================================================================

# Maps various source names to canonical names (case-insensitive matching)
COLUMN_ALIASES: Dict[str, List[str]] = {
    # Engine speed
    "rpm":
    ["rpm", "engine_rpm", "engine rpm", "enginespeed", "engine speed", "n"],
    # Manifold pressure
    "map_kpa": [
        "map_kpa",
        "map kpa",
        "map",
        "manifold_pressure",
        "manifold pressure",
        "boost_kpa",
        "intake_pressure",
    ],
    # Throttle position
    "tps": [
        "tps",
        "throttle",
        "throttle_position",
        "throttle position",
        "tp",
        "throttle_%",
        "throttle%",
    ],
    # Intake air temperature
    "iat": [
        "iat",
        "intake_air_temp",
        "intake air temp",
        "iat_f",
        "iat_c",
        "air_temp",
        "inlet_temp",
    ],
    # Engine coolant temperature
    "ect": [
        "ect",
        "coolant_temp",
        "coolant temp",
        "engine_temp",
        "engine temp",
        "et",
        "water_temp",
    ],
    # AFR measured - front cylinder
    "afr_meas_f": [
        "afr_meas_f",
        "afr meas f",
        "wbo2_f",
        "wbo2 f",
        "afr_f",
        "afr_front",
        "afr front",
        "lambda_f",
        "o2_f",
    ],
    # AFR measured - rear cylinder
    "afr_meas_r": [
        "afr_meas_r",
        "afr meas r",
        "wbo2_r",
        "wbo2 r",
        "afr_r",
        "afr_rear",
        "afr rear",
        "lambda_r",
        "o2_r",
    ],
    # AFR measured - global/single sensor
    "afr_meas": [
        "afr_meas",
        "afr meas",
        "afr",
        "wbo2",
        "lambda",
        "o2",
        "air_fuel_ratio",
        "air/fuel ratio",
    ],
    # AFR commanded - front cylinder
    "afr_cmd_f": [
        "afr_cmd_f",
        "afr cmd f",
        "afr_target_f",
        "afr target f",
        "lambda_target_f",
        "cmd_afr_f",
    ],
    # AFR commanded - rear cylinder
    "afr_cmd_r": [
        "afr_cmd_r",
        "afr cmd r",
        "afr_target_r",
        "afr target r",
        "lambda_target_r",
        "cmd_afr_r",
    ],
    # AFR commanded - global
    "afr_cmd": [
        "afr_cmd",
        "afr cmd",
        "afr_target",
        "afr target",
        "lambda_target",
        "commanded_afr",
        "target_afr",
    ],
    # Spark timing - front cylinder
    "spark_f": [
        "spark_f",
        "spark f",
        "advance_f",
        "advance f",
        "timing_f",
        "spark_adv_f",
        "ignition_f",
        "ign_f",
    ],
    # Spark timing - rear cylinder
    "spark_r": [
        "spark_r",
        "spark r",
        "advance_r",
        "advance r",
        "timing_r",
        "spark_adv_r",
        "ignition_r",
        "ign_r",
    ],
    # Spark timing - global
    "spark": [
        "spark",
        "advance",
        "timing",
        "spark_adv",
        "ignition",
        "ign",
        "spark_advance",
        "ignition_timing",
    ],
    # Knock sensor
    "knock": [
        "knock",
        "knock_sensor",
        "knock sensor",
        "knock_count",
        "knock_retard",
        "kr",
    ],
    # Knock - front cylinder
    "knock_f": ["knock_f", "knock f", "knock_front", "kr_f"],
    # Knock - rear cylinder
    "knock_r": ["knock_r", "knock r", "knock_rear", "kr_r"],
    # Battery voltage
    "vbatt": ["vbatt", "battery", "battery_voltage", "batt_v", "voltage"],
    # Torque
    "torque": ["torque", "tq", "engine_torque", "wheel_torque", "ft_lb", "nm"],
    # Time
    "time_ms": ["time_ms", "timestamp_ms", "time", "t_ms", "elapsed_ms"],
    "timestamp": ["timestamp", "time_s", "time_sec", "elapsed_s"],
}

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ChannelWarning:
    """A structured warning with stable code for programmatic use."""

    code: str  # e.g., "missing_channel:knock"
    message: str
    severity: str = "warning"  # "error", "warning", "info"
    feature_impact: str = ""  # What feature is affected

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "feature_impact": self.feature_impact,
        }


@dataclass
class ChannelPresence:
    """Describes what channels are available and in what form."""

    has_required: bool = False
    has_per_cylinder_afr: bool = False
    has_per_cylinder_spark: bool = False
    has_per_cylinder_knock: bool = False
    has_global_afr: bool = False
    has_global_spark: bool = False
    has_knock: bool = False
    has_tps: bool = False
    has_iat: bool = False
    has_ect: bool = False
    has_time: bool = False

    @property
    def can_analyze_afr(self) -> bool:
        """True if AFR analysis is possible."""
        return self.has_per_cylinder_afr or self.has_global_afr

    @property
    def can_analyze_spark(self) -> bool:
        """True if spark analysis is possible."""
        return self.has_per_cylinder_spark or self.has_global_spark

    @property
    def cylinder_mode(self) -> str:
        """Returns 'per_cylinder' or 'global' based on available channels."""
        if self.has_per_cylinder_afr or self.has_per_cylinder_spark:
            return "per_cylinder"
        return "global"

    def to_dict(self) -> Dict:
        return {
            "has_required": self.has_required,
            "has_per_cylinder_afr": self.has_per_cylinder_afr,
            "has_per_cylinder_spark": self.has_per_cylinder_spark,
            "has_per_cylinder_knock": self.has_per_cylinder_knock,
            "has_global_afr": self.has_global_afr,
            "has_global_spark": self.has_global_spark,
            "has_knock": self.has_knock,
            "has_tps": self.has_tps,
            "has_iat": self.has_iat,
            "has_ect": self.has_ect,
            "has_time": self.has_time,
            "can_analyze_afr": self.can_analyze_afr,
            "can_analyze_spark": self.can_analyze_spark,
            "cylinder_mode": self.cylinder_mode,
        }


@dataclass
class ChannelReadiness:
    """
    Summary of channel readiness for UI display.

    Provides a checklist of required/recommended channels and what features
    are available based on the data.
    """

    # Channel counts
    required_present: int = 0
    required_total: int = 2  # rpm, map_kpa
    recommended_present: int = 0
    recommended_total: int = 6  # tps, iat, afr_meas, afr_cmd, spark, knock

    # Channel status lists
    required_channels: List[Dict] = field(default_factory=list)
    recommended_channels: List[Dict] = field(default_factory=list)

    # Warnings with stable codes
    warnings: List[ChannelWarning] = field(default_factory=list)

    # Feature availability
    features_available: List[str] = field(default_factory=list)
    features_degraded: List[str] = field(default_factory=list)
    features_disabled: List[str] = field(default_factory=list)

    # Trust summary
    trust_summary: str = ""
    confidence_score: float = 0.0

    @property
    def is_ready(self) -> bool:
        """True if minimum required channels are present."""
        return self.required_present >= self.required_total

    @property
    def warning_codes(self) -> List[str]:
        """List of warning codes for programmatic use."""
        return [w.code for w in self.warnings]

    def to_dict(self) -> Dict:
        return {
            "required_present": self.required_present,
            "required_total": self.required_total,
            "recommended_present": self.recommended_present,
            "recommended_total": self.recommended_total,
            "required_channels": self.required_channels,
            "recommended_channels": self.recommended_channels,
            "warnings": [w.to_dict() for w in self.warnings],
            "warning_codes": self.warning_codes,
            "features_available": self.features_available,
            "features_degraded": self.features_degraded,
            "features_disabled": self.features_disabled,
            "trust_summary": self.trust_summary,
            "confidence_score": round(self.confidence_score, 2),
            "is_ready": self.is_ready,
        }


@dataclass
class NormalizationResult:
    """Result of normalizing a DataFrame to canonical columns."""

    df: pd.DataFrame
    columns_found: Dict[str, str]  # canonical_name -> original_name
    columns_missing: List[str]
    columns_derived: List[str]  # columns computed from others
    warnings: List[str] = field(default_factory=list)
    structured_warnings: List[ChannelWarning] = field(default_factory=list)
    presence: ChannelPresence = field(default_factory=ChannelPresence)

    @property
    def confidence_factor(self) -> float:
        """
        Returns a confidence factor (0.0 to 1.0) based on channel availability.

        Full confidence requires:
        - Required channels (rpm, map_kpa)
        - Per-cylinder AFR and spark
        - Knock data
        """
        score = 0.0

        # Required channels are essential
        if self.presence.has_required:
            score += 0.3
        else:
            return 0.0  # Can't proceed without required channels

        # Per-cylinder vs global
        if self.presence.has_per_cylinder_afr:
            score += 0.2
        elif self.presence.has_global_afr:
            score += 0.1

        if self.presence.has_per_cylinder_spark:
            score += 0.2
        elif self.presence.has_global_spark:
            score += 0.1

        # Knock data
        if self.presence.has_knock:
            score += 0.15

        # Supporting channels
        if self.presence.has_tps:
            score += 0.05
        if self.presence.has_iat:
            score += 0.05
        if self.presence.has_time:
            score += 0.05

        return min(1.0, score)

    @property
    def warning_codes(self) -> List[str]:
        """Get list of warning codes for programmatic use."""
        return [w.code for w in self.structured_warnings]


# =============================================================================
# Core Functions
# =============================================================================


def detect_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Detect which canonical columns exist in the DataFrame.

    Args:
        df: Input DataFrame with arbitrary column names

    Returns:
        Dict mapping canonical column names to original column names found
    """
    found: Dict[str, str] = {}
    df_columns_lower = {col.lower().strip(): col for col in df.columns}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower().strip()
            if alias_lower in df_columns_lower:
                found[canonical] = df_columns_lower[alias_lower]
                break

    return found


def normalize_dataframe(
    df: pd.DataFrame,
    inplace: bool = False,
) -> NormalizationResult:
    """
    Normalize a DataFrame to canonical DynoAI column names.

    Implements graceful degradation:
    - If per-cylinder channels missing, uses global channels
    - If knock missing, analysis proceeds with reduced confidence
    - Computes derived columns where possible (e.g., afr_error)

    Args:
        df: Input DataFrame with arbitrary column names
        inplace: If True, modifies the input DataFrame

    Returns:
        NormalizationResult with normalized DataFrame and metadata
    """
    if not inplace:
        df = df.copy()

    # Detect available columns
    columns_found = detect_columns(df)

    # Rename columns to canonical names
    rename_map = {orig: canonical for canonical, orig in columns_found.items()}
    df = df.rename(columns=rename_map)

    # Track what's missing and derived
    columns_missing: List[str] = []
    columns_derived: List[str] = []
    warnings: List[str] = []

    # Check required columns
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            columns_missing.append(col)

    # Build channel presence
    presence = ChannelPresence()
    presence.has_required = all(col in df.columns for col in REQUIRED_COLUMNS)

    # AFR presence
    presence.has_per_cylinder_afr = ("afr_meas_f" in df.columns
                                     and "afr_meas_r" in df.columns)
    presence.has_global_afr = "afr_meas" in df.columns

    # If no per-cylinder AFR but have global, create synthetic per-cylinder
    if not presence.has_per_cylinder_afr and presence.has_global_afr:
        df["afr_meas_f"] = df["afr_meas"]
        df["afr_meas_r"] = df["afr_meas"]
        columns_derived.extend(["afr_meas_f", "afr_meas_r"])
        warnings.append(
            "Using global AFR for both cylinders (no per-cylinder data)")

    # Spark presence
    presence.has_per_cylinder_spark = ("spark_f" in df.columns
                                       and "spark_r" in df.columns)
    presence.has_global_spark = "spark" in df.columns

    # If no per-cylinder spark but have global, create synthetic per-cylinder
    if not presence.has_per_cylinder_spark and presence.has_global_spark:
        df["spark_f"] = df["spark"]
        df["spark_r"] = df["spark"]
        columns_derived.extend(["spark_f", "spark_r"])
        warnings.append(
            "Using global spark for both cylinders (no per-cylinder data)")

    # AFR commanded - handle similar fallbacks
    has_per_cyl_cmd = "afr_cmd_f" in df.columns and "afr_cmd_r" in df.columns
    has_global_cmd = "afr_cmd" in df.columns

    if not has_per_cyl_cmd and has_global_cmd:
        df["afr_cmd_f"] = df["afr_cmd"]
        df["afr_cmd_r"] = df["afr_cmd"]
        columns_derived.extend(["afr_cmd_f", "afr_cmd_r"])

    # If no commanded AFR at all, use stoich default
    if "afr_cmd_f" not in df.columns:
        df["afr_cmd_f"] = 14.7
        df["afr_cmd_r"] = 14.7
        columns_derived.extend(["afr_cmd_f", "afr_cmd_r"])
        warnings.append(
            "No commanded AFR found, using stoich (14.7) as default")

    # Knock presence
    presence.has_per_cylinder_knock = ("knock_f" in df.columns
                                       and "knock_r" in df.columns)
    presence.has_knock = presence.has_per_cylinder_knock or "knock" in df.columns

    # If global knock only, duplicate to per-cylinder
    if not presence.has_per_cylinder_knock and "knock" in df.columns:
        df["knock_f"] = df["knock"]
        df["knock_r"] = df["knock"]
        columns_derived.extend(["knock_f", "knock_r"])

    # Other channels
    presence.has_tps = "tps" in df.columns
    presence.has_iat = "iat" in df.columns
    presence.has_ect = "ect" in df.columns
    presence.has_time = "time_ms" in df.columns or "timestamp" in df.columns

    # Create time_ms if only timestamp exists
    if not presence.has_time and "timestamp" in df.columns:
        df["time_ms"] = df["timestamp"] * 1000
        columns_derived.append("time_ms")
        presence.has_time = True

    # Compute AFR error columns (measured - commanded)
    if "afr_meas_f" in df.columns and "afr_cmd_f" in df.columns:
        df["afr_error_f"] = df["afr_meas_f"] - df["afr_cmd_f"]
        columns_derived.append("afr_error_f")

    if "afr_meas_r" in df.columns and "afr_cmd_r" in df.columns:
        df["afr_error_r"] = df["afr_meas_r"] - df["afr_cmd_r"]
        columns_derived.append("afr_error_r")

    # Global AFR error
    if "afr_meas" in df.columns:
        cmd_col = "afr_cmd" if "afr_cmd" in df.columns else None
        if cmd_col:
            df["afr_error"] = df["afr_meas"] - df[cmd_col]
        else:
            df["afr_error"] = df["afr_meas"] - 14.7
        columns_derived.append("afr_error")

    # Track missing optional columns
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns and col not in columns_derived:
            if col not in ["time_ms",
                           "timestamp"]:  # Don't report both time variants
                columns_missing.append(col)

    # Build structured warnings with stable codes
    structured_warnings: List[ChannelWarning] = []

    # Required channel warnings
    if "rpm" not in columns_found:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:rpm",
                message=WARNING_CODES["missing_channel:rpm"],
                severity="error",
                feature_impact="All analysis disabled",
            ))

    if "map_kpa" not in columns_found:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:map_kpa",
                message=WARNING_CODES["missing_channel:map_kpa"],
                severity="error",
                feature_impact="All analysis disabled",
            ))

    # TPS warning
    if not presence.has_tps:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:tps",
                message=WARNING_CODES["missing_channel:tps"],
                severity="warning",
                feature_impact="Mode detection accuracy reduced",
            ))

    # IAT warning
    if not presence.has_iat:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:iat",
                message=WARNING_CODES["missing_channel:iat"],
                severity="warning",
                feature_impact="Heat soak detection disabled",
            ))

    # AFR warnings
    if not presence.has_per_cylinder_afr and not presence.has_global_afr:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:afr_meas",
                message=WARNING_CODES["missing_channel:afr_meas"],
                severity="error",
                feature_impact="AFR error surfaces disabled",
            ))
        warnings.append("No AFR data found - AFR analysis will be disabled")
    elif not presence.has_per_cylinder_afr and presence.has_global_afr:
        structured_warnings.append(
            ChannelWarning(
                code="degraded:per_cylinder_afr",
                message=WARNING_CODES["degraded:per_cylinder_afr"],
                severity="info",
                feature_impact="Per-cylinder AFR analysis unavailable",
            ))

    # Spark warnings
    if not presence.has_per_cylinder_spark and not presence.has_global_spark:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:spark",
                message=WARNING_CODES["missing_channel:spark"],
                severity="error",
                feature_impact="Spark valley analysis disabled",
            ))
        warnings.append(
            "No spark data found - spark valley analysis will be disabled")
    elif not presence.has_per_cylinder_spark and presence.has_global_spark:
        structured_warnings.append(
            ChannelWarning(
                code="degraded:per_cylinder_spark",
                message=WARNING_CODES["degraded:per_cylinder_spark"],
                severity="info",
                feature_impact="Per-cylinder spark analysis unavailable",
            ))

    # Knock warnings
    if not presence.has_knock:
        structured_warnings.append(
            ChannelWarning(
                code="missing_channel:knock",
                message=WARNING_CODES["missing_channel:knock"],
                severity="warning",
                feature_impact="Knock surfaces and knock-based reasoning disabled",
            ))
        warnings.append(
            "No knock data found - knock-based reasoning will be disabled")

    # AFR commanded warning
    if "afr_cmd_f" in columns_derived and "afr_cmd" not in columns_found:
        structured_warnings.append(
            ChannelWarning(
                code="degraded:afr_cmd_default",
                message=WARNING_CODES["degraded:afr_cmd_default"],
                severity="info",
                feature_impact="AFR error may be less accurate",
            ))

    return NormalizationResult(
        df=df,
        columns_found=columns_found,
        columns_missing=columns_missing,
        columns_derived=columns_derived,
        warnings=warnings,
        structured_warnings=structured_warnings,
        presence=presence,
    )


def get_cylinder_columns(
    df: pd.DataFrame,
    base_name: str,
) -> List[str]:
    """
    Get available cylinder-specific columns for a given base name.

    Args:
        df: Normalized DataFrame
        base_name: Base column name (e.g., "afr_meas", "spark")

    Returns:
        List of available column names (e.g., ["afr_meas_f", "afr_meas_r"] or ["afr_meas"])
    """
    front = f"{base_name}_f"
    rear = f"{base_name}_r"

    if front in df.columns and rear in df.columns:
        return [front, rear]
    elif base_name in df.columns:
        return [base_name]

    return []


def get_channel_readiness(
        norm_result: NormalizationResult) -> ChannelReadiness:
    """
    Build a channel readiness summary from normalization results.

    This provides a UI-friendly checklist of what channels are present
    and what features are available.

    Args:
        norm_result: Result from normalize_dataframe()

    Returns:
        ChannelReadiness with checklist and feature availability
    """
    presence = norm_result.presence

    # Required channels checklist
    required_channels = [
        {
            "name": "rpm",
            "label": "Engine RPM",
            "present": "rpm" in norm_result.columns_found,
            "required": True,
        },
        {
            "name": "map_kpa",
            "label": "Manifold Pressure (MAP)",
            "present": "map_kpa" in norm_result.columns_found,
            "required": True,
        },
    ]

    # Recommended channels checklist
    recommended_channels = [
        {
            "name": "tps",
            "label": "Throttle Position",
            "present": presence.has_tps,
            "required": False,
            "impact": "Mode detection accuracy",
        },
        {
            "name": "iat",
            "label": "Intake Air Temp",
            "present": presence.has_iat,
            "required": False,
            "impact": "Heat soak detection",
        },
        {
            "name":
            "afr_meas",
            "label":
            "AFR Measured",
            "present":
            presence.can_analyze_afr,
            "required":
            False,
            "impact":
            "AFR error surfaces",
            "note": ("per-cylinder" if presence.has_per_cylinder_afr else
                     "global" if presence.has_global_afr else "missing"),
        },
        {
            "name":
            "afr_cmd",
            "label":
            "AFR Commanded",
            "present":
            "afr_cmd" in norm_result.columns_found
            or "afr_cmd_f" in norm_result.columns_found,
            "required":
            False,
            "impact":
            "AFR error accuracy",
        },
        {
            "name":
            "spark",
            "label":
            "Spark Timing",
            "present":
            presence.can_analyze_spark,
            "required":
            False,
            "impact":
            "Spark valley detection",
            "note": ("per-cylinder" if presence.has_per_cylinder_spark else
                     "global" if presence.has_global_spark else "missing"),
        },
        {
            "name": "knock",
            "label": "Knock Sensor",
            "present": presence.has_knock,
            "required": False,
            "impact": "Knock surfaces & reasoning",
        },
    ]

    # Count present channels
    required_present = sum(1 for c in required_channels if c["present"])
    recommended_present = sum(1 for c in recommended_channels if c["present"])

    # Determine feature availability
    features_available = []
    features_degraded = []
    features_disabled = []

    if presence.has_required:
        features_available.append("Mode detection")
        features_available.append("Coverage gap analysis")

    if presence.can_analyze_afr:
        if presence.has_per_cylinder_afr:
            features_available.append("Per-cylinder AFR error surfaces")
        else:
            features_degraded.append("AFR error surfaces (global only)")
    else:
        features_disabled.append("AFR error surfaces")

    if presence.can_analyze_spark:
        if presence.has_per_cylinder_spark:
            features_available.append("Per-cylinder spark surfaces")
            features_available.append("Spark valley detection")
        else:
            features_degraded.append("Spark surfaces (global only)")
            features_available.append("Spark valley detection")
    else:
        features_disabled.append("Spark valley detection")
        features_disabled.append("Spark surfaces")

    if presence.has_knock:
        features_available.append("Knock activity surfaces")
        features_available.append("Knock-based reasoning")
    else:
        features_disabled.append("Knock activity surfaces")
        features_disabled.append("Knock-based reasoning")

    if presence.has_iat:
        features_available.append("Heat soak detection")
    else:
        features_disabled.append("Heat soak detection")

    # Build trust summary
    confidence = norm_result.confidence_factor
    if confidence >= 0.9:
        trust_summary = (
            "Excellent data quality - all analyses available with high confidence"
        )
    elif confidence >= 0.7:
        trust_summary = "Good data quality - most analyses available"
    elif confidence >= 0.5:
        trust_summary = "Moderate data quality - some features degraded or disabled"
    elif confidence >= 0.3:
        trust_summary = "Limited data quality - basic analysis only"
    else:
        trust_summary = "Insufficient data - required channels missing"

    return ChannelReadiness(
        required_present=required_present,
        required_total=len(required_channels),
        recommended_present=recommended_present,
        recommended_total=len(recommended_channels),
        required_channels=required_channels,
        recommended_channels=recommended_channels,
        warnings=norm_result.structured_warnings,
        features_available=features_available,
        features_degraded=features_degraded,
        features_disabled=features_disabled,
        trust_summary=trust_summary,
        confidence_score=confidence,
    )
