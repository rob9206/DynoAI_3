"""
DynoAI NextGen Mode Detection

Labels each sample in a log with an operating mode tag for targeted analysis.
Modes include: IDLE, CRUISE, TIP_IN, TIP_OUT, WOT, DECEL, HEAT_SOAK.

All detection is deterministic and threshold-based (no ML).

Usage:
    from dynoai.core.mode_detection import label_modes, ModeDetectionConfig, ModeTag

    config = ModeDetectionConfig()  # Use defaults or customize
    result = label_modes(df, config)

    print(f"Mode distribution: {result.summary_counts}")
    # Access labeled DataFrame: result.df (has 'mode' column)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

__all__ = [
    "ModeTag",
    "ModeDetectionConfig",
    "ModeLabeledFrame",
    "label_modes",
    "compute_derivatives",
]

# =============================================================================
# Mode Tag Enum
# =============================================================================


class ModeTag(str, Enum):
    """Operating mode tags for sample classification."""

    IDLE = "idle"
    CRUISE = "cruise"
    TIP_IN = "tip_in"
    TIP_OUT = "tip_out"
    WOT = "wot"
    DECEL = "decel"
    HEAT_SOAK = "heat_soak"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ModeDetectionConfig:
    """
    Configuration for mode detection thresholds.

    All thresholds are deterministic - no machine learning involved.
    """

    # WOT detection
    tps_wot_threshold: float = 85.0  # TPS % above which is WOT
    map_wot_threshold: float = 85.0  # MAP kPa above which is WOT (high load)

    # Idle detection
    rpm_idle_ceiling: float = 1200.0  # RPM below which is idle candidate
    tps_idle_ceiling: float = 5.0  # TPS % below which is idle candidate
    map_idle_ceiling: float = 45.0  # MAP kPa below which is idle candidate

    # Cruise detection (between idle and WOT)
    tps_cruise_max: float = 50.0  # TPS % ceiling for cruise
    map_cruise_max: float = 70.0  # MAP kPa ceiling for cruise
    rpm_cruise_min: float = 1500.0  # RPM floor for cruise

    # Transient detection (tip-in/tip-out)
    tpsdot_tipin_threshold: float = 20.0  # TPS rate (%/s) for tip-in
    mapdot_tipin_threshold: float = 15.0  # MAP rate (kPa/s) for tip-in
    tpsdot_tipout_threshold: float = -15.0  # TPS rate (%/s) for tip-out
    mapdot_tipout_threshold: float = -10.0  # MAP rate (kPa/s) for tip-out

    # Decel detection
    tps_decel_ceiling: float = 3.0  # TPS % below which is decel candidate
    rpm_decel_floor: float = 1500.0  # RPM above which decel is possible

    # Heat soak detection
    iat_soak_threshold: float = 130.0  # IAT (°F) above which heat soak suspected
    rpm_soak_ceiling: float = 3500.0  # RPM below which heat soak can occur
    tps_soak_ceiling: float = 15.0  # TPS % below which heat soak can occur

    # Time column handling
    sample_time_col: str = "time_ms"  # Column name for timestamps
    default_sample_rate_hz: float = 100.0  # Assumed if no time column (10ms intervals)

    # Derivative smoothing
    derivative_window: int = 5  # Samples to average for derivative calculation


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ModeLabeledFrame:
    """Result of mode labeling operation."""

    df: pd.DataFrame  # DataFrame with 'mode' column added
    summary_counts: Dict[str, int] = field(default_factory=dict)
    mode_durations_sec: Dict[str, float] = field(default_factory=dict)
    config_used: ModeDetectionConfig = field(
        default_factory=ModeDetectionConfig)

    @property
    def total_samples(self) -> int:
        """Total number of samples."""
        return len(self.df)

    @property
    def mode_distribution(self) -> Dict[str, float]:
        """Mode distribution as percentages."""
        total = self.total_samples
        if total == 0:
            return {}
        return {
            mode: count / total * 100
            for mode, count in self.summary_counts.items()
        }

    def get_mode_mask(self, mode: ModeTag) -> pd.Series:
        """Get boolean mask for a specific mode."""
        return self.df["mode"] == mode.value

    def filter_by_mode(self, mode: ModeTag) -> pd.DataFrame:
        """Get DataFrame filtered to a specific mode."""
        return self.df[self.get_mode_mask(mode)]

    def filter_by_modes(self, modes: List[ModeTag]) -> pd.DataFrame:
        """Get DataFrame filtered to multiple modes."""
        mode_values = [m.value for m in modes]
        return self.df[self.df["mode"].isin(mode_values)]

    def to_summary_dict(self) -> Dict:
        """Serialize mode summary to JSON-compatible dict."""
        return {
            "counts": self.summary_counts,
            "distribution_pct": {
                k: round(v, 1)
                for k, v in self.mode_distribution.items()
            },
            "durations_sec": {
                k: round(v, 2)
                for k, v in self.mode_durations_sec.items()
            },
            "total_samples": self.total_samples,
            "total_duration_sec": round(sum(self.mode_durations_sec.values()),
                                        2),
        }


# =============================================================================
# Core Functions
# =============================================================================


def compute_derivatives(
    df: pd.DataFrame,
    config: ModeDetectionConfig,
) -> pd.DataFrame:
    """
    Compute rate-of-change columns for TPS and MAP.

    Args:
        df: Input DataFrame with tps and map_kpa columns
        config: Mode detection configuration

    Returns:
        DataFrame with tps_dot and map_dot columns added
    """
    df = df.copy()

    # Determine time delta
    if config.sample_time_col in df.columns:
        # Use actual timestamps
        time_ms = df[config.sample_time_col].values
        dt_ms = np.diff(time_ms, prepend=time_ms[0])
        dt_s = np.maximum(dt_ms / 1000.0, 0.001)  # Prevent division by zero
    else:
        # Use assumed sample rate
        dt_s = np.full(len(df), 1.0 / config.default_sample_rate_hz)

    df["_dt_s"] = dt_s

    # Compute TPS derivative if available
    if "tps" in df.columns:
        tps_diff = df["tps"].diff().fillna(0)
        tps_dot_raw = tps_diff / dt_s
        # Apply smoothing window
        df["tps_dot"] = (tps_dot_raw.rolling(window=config.derivative_window,
                                             min_periods=1).mean().fillna(0))
    else:
        df["tps_dot"] = 0.0

    # Compute MAP derivative
    if "map_kpa" in df.columns:
        map_diff = df["map_kpa"].diff().fillna(0)
        map_dot_raw = map_diff / dt_s
        # Apply smoothing window
        df["map_dot"] = (map_dot_raw.rolling(window=config.derivative_window,
                                             min_periods=1).mean().fillna(0))
    else:
        df["map_dot"] = 0.0

    return df


def classify_sample(
    row: pd.Series,
    config: ModeDetectionConfig,
) -> ModeTag:
    """
    Classify a single sample into a mode.

    Priority order (first match wins):
    1. HEAT_SOAK (if conditions met)
    2. TIP_IN (transient positive)
    3. TIP_OUT (transient negative)
    4. WOT (high load)
    5. DECEL (closed throttle, above idle RPM)
    6. IDLE (low RPM, low load)
    7. CRUISE (everything else)

    Args:
        row: Single row from DataFrame
        config: Detection thresholds

    Returns:
        ModeTag classification
    """
    # Extract values with defaults
    rpm = row.get("rpm", 0)
    tps = row.get("tps", 50)  # Default to mid-throttle if missing
    map_kpa = row.get("map_kpa", 50)
    iat = row.get("iat", 77)  # Default to room temp
    tps_dot = row.get("tps_dot", 0)
    map_dot = row.get("map_dot", 0)

    # 1. Check for heat soak conditions
    if (iat > config.iat_soak_threshold and rpm < config.rpm_soak_ceiling
            and tps < config.tps_soak_ceiling):
        return ModeTag.HEAT_SOAK

    # 2. Check for tip-in transient
    if (tps_dot > config.tpsdot_tipin_threshold
            or map_dot > config.mapdot_tipin_threshold):
        return ModeTag.TIP_IN

    # 3. Check for tip-out transient
    if (tps_dot < config.tpsdot_tipout_threshold
            or map_dot < config.mapdot_tipout_threshold):
        return ModeTag.TIP_OUT

    # 4. Check for WOT
    if tps >= config.tps_wot_threshold or map_kpa >= config.map_wot_threshold:
        return ModeTag.WOT

    # 5. Check for decel (closed throttle above idle)
    if tps <= config.tps_decel_ceiling and rpm > config.rpm_decel_floor:
        return ModeTag.DECEL

    # 6. Check for idle
    if (rpm < config.rpm_idle_ceiling and tps < config.tps_idle_ceiling
            and map_kpa < config.map_idle_ceiling):
        return ModeTag.IDLE

    # 7. Default to cruise
    return ModeTag.CRUISE


def label_modes(
    df: pd.DataFrame,
    config: Optional[ModeDetectionConfig] = None,
) -> ModeLabeledFrame:
    """
    Label each sample in the DataFrame with an operating mode.

    This function is fully deterministic - same inputs always produce
    same outputs.

    Args:
        df: Input DataFrame (should be normalized first)
        config: Detection thresholds (uses defaults if not provided)

    Returns:
        ModeLabeledFrame with labeled DataFrame and summary statistics
    """
    if config is None:
        config = ModeDetectionConfig()

    # Make a copy to avoid modifying original
    df = df.copy()

    # Compute derivatives for transient detection
    df = compute_derivatives(df, config)

    # Classify each sample
    modes = df.apply(lambda row: classify_sample(row, config).value, axis=1)
    df["mode"] = modes

    # Build summary counts
    summary_counts = df["mode"].value_counts().to_dict()

    # Ensure all modes are represented (even if zero)
    for mode in ModeTag:
        if mode.value not in summary_counts:
            summary_counts[mode.value] = 0

    # Compute per-mode durations
    mode_durations_sec: Dict[str, float] = {}
    sample_rate_hz = config.default_sample_rate_hz

    # Try to compute actual sample rate from time column
    if config.sample_time_col in df.columns and len(df) > 1:
        time_ms = df[config.sample_time_col].values
        total_time_ms = time_ms[-1] - time_ms[0]
        if total_time_ms > 0:
            sample_rate_hz = (len(df) - 1) / (total_time_ms / 1000.0)

    sample_duration_sec = 1.0 / sample_rate_hz

    for mode in ModeTag:
        count = summary_counts.get(mode.value, 0)
        mode_durations_sec[mode.value] = count * sample_duration_sec

    # Clean up temporary columns
    cols_to_drop = ["_dt_s"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    return ModeLabeledFrame(
        df=df,
        summary_counts=summary_counts,
        mode_durations_sec=mode_durations_sec,
        config_used=config,
    )


def get_steady_state_mask(labeled_df: pd.DataFrame) -> pd.Series:
    """
    Get a mask for steady-state samples (suitable for VE correction).

    Steady state excludes: TIP_IN, TIP_OUT, HEAT_SOAK

    Args:
        labeled_df: DataFrame with 'mode' column

    Returns:
        Boolean Series mask
    """
    excluded_modes = [
        ModeTag.TIP_IN.value,
        ModeTag.TIP_OUT.value,
        ModeTag.HEAT_SOAK.value,
    ]
    return ~labeled_df["mode"].isin(excluded_modes)


def get_wot_mask(labeled_df: pd.DataFrame) -> pd.Series:
    """
    Get a mask for WOT samples.

    Args:
        labeled_df: DataFrame with 'mode' column

    Returns:
        Boolean Series mask
    """
    return labeled_df["mode"] == ModeTag.WOT.value


def get_transient_mask(labeled_df: pd.DataFrame) -> pd.Series:
    """
    Get a mask for transient samples (tip-in or tip-out).

    Args:
        labeled_df: DataFrame with 'mode' column

    Returns:
        Boolean Series mask
    """
    transient_modes = [ModeTag.TIP_IN.value, ModeTag.TIP_OUT.value]
    return labeled_df["mode"].isin(transient_modes)
