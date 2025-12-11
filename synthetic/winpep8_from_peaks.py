"""
Generate synthetic WinPEP8-style dyno runs from peak HP/TQ values.

This module creates realistic-looking dyno curves that can be used for
testing, training, or simulation purposes. All math is deterministic
(no randomness) to ensure reproducible outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from io_contracts import safe_path


@dataclass
class PeakInfo:
    """Peak values extracted from dyno chart metadata or OCR."""

    hp_peak: float
    hp_peak_rpm: float
    tq_peak: float
    tq_peak_rpm: float

    def __post_init__(self) -> None:
        if self.hp_peak <= 0:
            raise ValueError("hp_peak must be positive")
        if self.tq_peak <= 0:
            raise ValueError("tq_peak must be positive")
        if self.hp_peak_rpm <= 0:
            raise ValueError("hp_peak_rpm must be positive")
        if self.tq_peak_rpm <= 0:
            raise ValueError("tq_peak_rpm must be positive")


@dataclass
class CurveParams:
    """
    Parameters controlling the shape of generated torque curves.

    These defaults are tuned for Harley-Davidson V-twin engines
    (M8, Twin Cam, etc.) but can be adjusted for other engine types.
    """

    # RPM range parameters
    rpm_min: float = 2000.0
    rpm_max: float = 6500.0
    num_points: int = 400

    # Curve shape parameters
    low_rpm_rolloff: float = 0.15  # How much torque drops at low RPM
    high_rpm_rolloff: float = 0.20  # How much torque drops at high RPM
    torque_plateau_width: float = 0.35  # Fraction of RPM range for plateau

    # Engine family presets
    engine_family: Optional[str] = None


def _get_engine_params(engine_family: Optional[str]) -> CurveParams:
    """
    Return CurveParams tuned for specific engine families.

    Args:
        engine_family: Engine type (e.g., "M8", "Twin Cam", "Sportster")

    Returns:
        CurveParams tuned for that engine family.
    """
    family_lower = (engine_family or "").lower().strip()

    if family_lower in ("m8", "milwaukee-eight", "milwaukee eight"):
        # M8: Broad torque curve, peaks around 3500-4000 RPM
        return CurveParams(
            rpm_min=2000.0,
            rpm_max=6000.0,
            num_points=400,
            low_rpm_rolloff=0.12,
            high_rpm_rolloff=0.18,
            torque_plateau_width=0.40,
            engine_family="M8",
        )
    elif family_lower in ("twin cam", "twincam", "tc"):
        # Twin Cam: Similar to M8 but slightly narrower powerband
        return CurveParams(
            rpm_min=2000.0,
            rpm_max=6000.0,
            num_points=400,
            low_rpm_rolloff=0.14,
            high_rpm_rolloff=0.22,
            torque_plateau_width=0.35,
            engine_family="Twin Cam",
        )
    elif family_lower in ("sportster", "evo sportster", "1200", "883"):
        # Sportster: Higher-revving, narrower torque peak
        return CurveParams(
            rpm_min=2000.0,
            rpm_max=7000.0,
            num_points=400,
            low_rpm_rolloff=0.18,
            high_rpm_rolloff=0.25,
            torque_plateau_width=0.30,
            engine_family="Sportster",
        )
    else:
        # Generic V-twin defaults
        return CurveParams(
            rpm_min=2000.0,
            rpm_max=6500.0,
            num_points=400,
            engine_family=engine_family,
        )


def _torque_shape(
    rpm: np.ndarray,
    peak: PeakInfo,
    params: CurveParams,
) -> np.ndarray:
    """
    Generate a deterministic smooth torque curve that hits the supplied peaks.

    The curve uses a combination of Gaussian humps to create a realistic
    V-twin torque profile with:
    - Gradual rise from low RPM
    - Broad plateau around torque peak
    - Gradual rolloff toward redline
    - Proper HP peak placement via blending

    Args:
        rpm: Array of RPM values to generate torque for.
        peak: Peak HP/TQ information.
        params: Curve shape parameters.

    Returns:
        Array of torque values corresponding to each RPM point.
    """
    rpm_range = params.rpm_max - params.rpm_min

    # Center the torque hump between torque peak and power peak
    center = 0.5 * (peak.tq_peak_rpm + peak.hp_peak_rpm)
    span = max(800.0, params.torque_plateau_width * rpm_range)

    # Base Gaussian hump centered on torque peak area
    base = np.exp(-((rpm - center) ** 2) / (2.0 * span**2))

    # Normalize base so that peak matches desired tq_peak
    base_max = float(base.max()) or 1.0
    tq = base * (peak.tq_peak / base_max)

    # Apply low-RPM rolloff (engine struggles to breathe at low RPM)
    low_rpm_factor = np.clip(
        (rpm - params.rpm_min) / (peak.tq_peak_rpm - params.rpm_min + 100),
        params.low_rpm_rolloff,
        1.0,
    )
    tq = tq * low_rpm_factor

    # Apply high-RPM rolloff (volumetric efficiency drops)
    high_rpm_threshold = peak.hp_peak_rpm + 200
    high_rpm_factor = np.where(
        rpm > high_rpm_threshold,
        1.0 - params.high_rpm_rolloff * ((rpm - high_rpm_threshold) / 1000) ** 2,
        1.0,
    )
    high_rpm_factor = np.clip(high_rpm_factor, 0.3, 1.0)
    tq = tq * high_rpm_factor

    # Blend to ensure HP reaches hp_peak at hp_peak_rpm
    # HP = TQ * RPM / 5252, so TQ = HP * 5252 / RPM
    hp_target_at_hp_peak = peak.hp_peak
    tq_required_at_hp_peak = hp_target_at_hp_peak * 5252.0 / peak.hp_peak_rpm

    # Smooth Gaussian blend around hp_peak_rpm
    blend_width = max(400.0, 0.25 * span)
    weight = np.exp(-((rpm - peak.hp_peak_rpm) ** 2) / (2.0 * blend_width**2))
    tq = tq * (1.0 - weight) + tq_required_at_hp_peak * weight

    # Ensure we hit the exact torque peak at tq_peak_rpm
    tq_blend_width = max(300.0, 0.20 * span)
    tq_weight = np.exp(-((rpm - peak.tq_peak_rpm) ** 2) / (2.0 * tq_blend_width**2))
    tq = tq * (1.0 - tq_weight * 0.5) + peak.tq_peak * tq_weight * 0.5

    return tq


def generate_winpep8_like_run(
    peak: PeakInfo,
    rpm_min: Optional[float] = None,
    rpm_max: Optional[float] = None,
    num_points: int = 400,
    engine_family: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate a synthetic WinPEP8-style dyno run from peak values.

    Creates a realistic torque curve and derives horsepower using
    the standard formula: HP = TQ * RPM / 5252

    Args:
        peak: PeakInfo with hp_peak, hp_peak_rpm, tq_peak, tq_peak_rpm.
        rpm_min: Minimum RPM for the run (default: based on engine family).
        rpm_max: Maximum RPM for the run (default: based on engine family).
        num_points: Number of data points to generate.
        engine_family: Engine type for curve shape tuning.

    Returns:
        DataFrame with columns: Engine RPM, Torque, Horsepower
    """
    # Get engine-specific parameters
    params = _get_engine_params(engine_family)

    # Override with explicit values if provided
    if rpm_min is not None:
        params.rpm_min = rpm_min
    if rpm_max is not None:
        params.rpm_max = rpm_max
    params.num_points = num_points

    # Generate RPM array
    rpm = np.linspace(params.rpm_min, params.rpm_max, params.num_points)

    # Generate torque curve
    tq = _torque_shape(rpm, peak, params)

    # Derive horsepower: HP = TQ * RPM / 5252
    hp = tq * rpm / 5252.0

    df = pd.DataFrame(
        {
            "Engine RPM": rpm,
            "Torque": np.round(tq, 2),
            "Horsepower": np.round(hp, 2),
        }
    )

    return df


def write_run_csv(run_id: str, df: pd.DataFrame) -> str:
    """
    Write a synthetic run DataFrame to the standard runs directory.

    Args:
        run_id: Unique identifier for the run (e.g., "fuelmoto/m8_stage2").
        df: DataFrame with dyno data.

    Returns:
        Path to the written CSV file.
    """
    # Sanitize run_id to prevent path traversal
    safe_run_id = run_id.replace("\\", "/").strip("/")
    base = Path(safe_path(f"runs/{safe_run_id}/run.csv"))
    base.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(base, index=False)
    return str(base)


def generate_and_write_run(
    run_id: str,
    peak: PeakInfo,
    engine_family: Optional[str] = None,
) -> str:
    """
    Convenience function to generate and write a synthetic run in one step.

    Args:
        run_id: Unique identifier for the run.
        peak: Peak HP/TQ values.
        engine_family: Optional engine type for curve tuning.

    Returns:
        Path to the written CSV file.
    """
    df = generate_winpep8_like_run(peak, engine_family=engine_family)
    return write_run_csv(run_id, df)


__all__ = [
    "PeakInfo",
    "CurveParams",
    "generate_winpep8_like_run",
    "write_run_csv",
    "generate_and_write_run",
]

