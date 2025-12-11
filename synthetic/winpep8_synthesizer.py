from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from external_scrapers.dyno_models import DynoCurveSpec
from external_scrapers.winpep_synthesizer import generate_synthetic_pull
from io_contracts import safe_path


@dataclass(frozen=True)
class PeakInfo:
    """Peak information extracted from an external dyno chart."""

    max_hp: float
    hp_peak_rpm: float
    max_tq: float
    tq_peak_rpm: float


EngineFamily = Literal["M8", "TwinCam", "Sportbike", "Generic"]


@dataclass(frozen=True)
class EngineConfig:
    """Engine configuration used to shape the synthetic curve."""

    family: EngineFamily
    displacement_ci: float
    idle_rpm: float
    redline_rpm: float
    wot_ramp_end_rpm: float  # RPM where we consider MAP/TPS at full 100%


def default_engine_config(
    family: EngineFamily,
    displacement_ci: float,
    peaks: PeakInfo,
) -> EngineConfig:
    """
    Provide a realistic RPM window for the given engine family.
    """

    if family in ("M8", "TwinCam"):
        idle = 900.0
        redline = max(peaks.hp_peak_rpm + 1500.0, 5800.0)
        redline = min(redline, 6500.0)
        wot_ramp_end = 2600.0
    elif family == "Sportbike":
        idle = 1200.0
        redline = max(peaks.hp_peak_rpm + 2500.0, 10500.0)
        redline = min(redline, 13000.0)
        wot_ramp_end = 6000.0
    else:
        idle = 900.0
        redline = max(peaks.hp_peak_rpm + 1500.0, 6000.0)
        redline = min(redline, 7000.0)
        wot_ramp_end = 2800.0

    return EngineConfig(
        family=family,
        displacement_ci=displacement_ci,
        idle_rpm=idle,
        redline_rpm=redline,
        wot_ramp_end_rpm=wot_ramp_end,
    )


def _resample_dataframe(df: pd.DataFrame, rpm_points: int) -> pd.DataFrame:
    if len(df) == rpm_points:
        return df

    rpm_source = df["Engine RPM"].to_numpy()
    target_rpm = np.linspace(rpm_source.min(), rpm_source.max(), rpm_points)
    resampled = {"Engine RPM": target_rpm}

    for column in df.columns:
        if column == "Engine RPM":
            continue
        values = df[column].to_numpy()
        resampled[column] = np.interp(target_rpm, rpm_source, values)

    result = pd.DataFrame(resampled)
    for column in ["AFR Target F", "AFR Target R", "VE F", "VE R", "Knock"]:
        if column in result.columns:
            result[column] = np.rint(result[column]).astype(int)
    return result


def generate_winpep8_like_run(
    peaks: PeakInfo,
    family: EngineFamily,
    displacement_ci: float,
    rpm_points: int = 400,
) -> pd.DataFrame:
    """
    Build a WinPEP-style dataframe with deterministic torque/HP curves.
    """

    cfg = default_engine_config(family, displacement_ci, peaks)
    spec = DynoCurveSpec(
        idle_rpm=cfg.idle_rpm,
        redline_rpm=cfg.redline_rpm,
        hp_peak_rpm=peaks.hp_peak_rpm,
        max_hp=peaks.max_hp,
        tq_peak_rpm=peaks.tq_peak_rpm,
        max_tq=peaks.max_tq,
        engine_family=family,
        displacement_ci=displacement_ci,
    )

    base_df = generate_synthetic_pull(spec)
    base_df["Horsepower"] = base_df["Torque"] * base_df["Engine RPM"] / 5252.0

    df = _resample_dataframe(
        base_df[
            [
                "Engine RPM",
                "MAP kPa",
                "Torque",
                "Horsepower",
                "AFR Target F",
                "AFR Target R",
                "VE F",
                "VE R",
                "AFR Cmd F",
                "AFR Cmd R",
                "AFR Meas F",
                "AFR Meas R",
                "IAT F",
                "Knock",
                "VBatt",
                "TPS",
            ]
        ],
        rpm_points,
    )

    df["Engine RPM"] = np.round(df["Engine RPM"], 2)
    df["MAP kPa"] = np.round(df["MAP kPa"], 2)
    df["Torque"] = np.round(df["Torque"], 2)
    df["Horsepower"] = np.round(df["Horsepower"], 2)
    df["AFR Cmd F"] = np.round(df["AFR Cmd F"], 2)
    df["AFR Cmd R"] = np.round(df["AFR Cmd R"], 2)
    df["AFR Meas F"] = np.round(df["AFR Meas F"], 2)
    df["AFR Meas R"] = np.round(df["AFR Meas R"], 2)
    df["IAT F"] = np.round(df["IAT F"], 1)
    df["VBatt"] = np.round(df["VBatt"], 2)
    df["TPS"] = np.round(df["TPS"], 1)
    return df


def save_winpep8_run(run_id: str, df: pd.DataFrame) -> str:
    """
    Save the synthetic run under runs/{run_id}/run.csv using safe_path.
    """

    rel = f"runs/{run_id}/run.csv".replace("\\", "/").strip("/")
    path = Path(safe_path(rel))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return str(path)


__all__ = [
    "EngineConfig",
    "EngineFamily",
    "PeakInfo",
    "default_engine_config",
    "generate_winpep8_like_run",
    "save_winpep8_run",
]
