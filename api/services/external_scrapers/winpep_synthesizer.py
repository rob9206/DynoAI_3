from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from external_scrapers import get_stdout_logger
from external_scrapers.dyno_models import DynoChartMeta, DynoCurveSpec
from dynoai.core.io_contracts import safe_path

logger = get_stdout_logger(__name__)

COLUMN_ORDER: List[str] = [
    "Engine RPM",
    "MAP kPa",
    "Torque",
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


def build_curve_spec(meta: DynoChartMeta) -> Optional[DynoCurveSpec]:
    required = [
        meta.max_power_hp,
        meta.max_power_rpm,
        meta.max_torque_ftlb,
        meta.max_torque_rpm,
        meta.engine_family,
        meta.displacement_ci,
    ]
    if any(v is None for v in required):
        return None

    engine_family = str(meta.engine_family)
    displacement = float(meta.displacement_ci)  # type: ignore[arg-type]

    idle_defaults = {"M8": 900.0, "Twin Cam": 900.0, "Sportster": 1100.0}
    idle_rpm = idle_defaults.get(engine_family, 1000.0)

    redline_candidate = max(float(meta.max_power_rpm) + 1500.0, 5500.0)
    harley_like = engine_family in {"M8", "Twin Cam", "Sportster"}
    redline_cap = 7000.0 if harley_like else 9000.0
    redline_rpm = min(redline_candidate, redline_cap)

    return DynoCurveSpec(
        idle_rpm=idle_rpm,
        redline_rpm=redline_rpm,
        hp_peak_rpm=float(meta.max_power_rpm),  # type: ignore[arg-type]
        max_hp=float(meta.max_power_hp),  # type: ignore[arg-type]
        tq_peak_rpm=float(meta.max_torque_rpm),  # type: ignore[arg-type]
        max_tq=float(meta.max_torque_ftlb),  # type: ignore[arg-type]
        engine_family=engine_family,
        displacement_ci=displacement,
    )


def _rpm_vector(spec: DynoCurveSpec) -> np.ndarray:
    step = max(75.0, min(100.0, (spec.redline_rpm - spec.idle_rpm) / 120))
    base = np.arange(spec.idle_rpm, spec.redline_rpm + step, step, dtype=float)
    critical = np.array([spec.tq_peak_rpm, spec.hp_peak_rpm])
    combined = np.unique(np.concatenate([base, critical]))
    return np.sort(combined)


def generate_synthetic_pull(spec: DynoCurveSpec) -> pd.DataFrame:
    rpm = _rpm_vector(spec)
    left_sigma = max(350.0, (spec.tq_peak_rpm - spec.idle_rpm) / 2.5)
    right_sigma = max(450.0, (spec.redline_rpm - spec.tq_peak_rpm) / 3.0)
    hp_sigma = max(400.0, (spec.redline_rpm - spec.idle_rpm) / 5.0)

    left_mask = rpm <= spec.tq_peak_rpm
    right_mask = ~left_mask
    base_curve = np.empty_like(rpm)
    base_curve[left_mask] = np.exp(
        -((rpm[left_mask] - spec.tq_peak_rpm) ** 2) / (2 * (left_sigma**2))
    )
    base_curve[right_mask] = np.exp(
        -((rpm[right_mask] - spec.tq_peak_rpm) ** 2) / (2 * (right_sigma**2))
    )
    base_curve /= np.max(base_curve)

    hp_component = np.exp(-((rpm - spec.hp_peak_rpm) ** 2) / (2 * (hp_sigma**2)))

    target_torque_at_hp = spec.max_hp * 5252.0 / spec.hp_peak_rpm
    base_at_hp = np.interp(spec.hp_peak_rpm, rpm, base_curve)
    base_at_tq = np.interp(spec.tq_peak_rpm, rpm, base_curve)
    hp_at_tq = np.interp(spec.tq_peak_rpm, rpm, hp_component)
    hp_at_hp = np.interp(spec.hp_peak_rpm, rpm, hp_component)

    ratio = target_torque_at_hp / spec.max_tq
    denominator = (ratio * hp_at_tq) - hp_at_hp
    if abs(denominator) < 1e-9:
        adjust_coeff = 0.0
    else:
        adjust_coeff = (base_at_hp - (ratio * base_at_tq)) / denominator

    combined = base_curve + adjust_coeff * hp_component
    combined = np.clip(combined, 1e-6, None)
    value_at_tq_peak = np.interp(spec.tq_peak_rpm, rpm, combined)
    combined = np.minimum(combined, value_at_tq_peak)
    value_at_tq_peak = np.interp(spec.tq_peak_rpm, rpm, combined)
    scale = spec.max_tq / value_at_tq_peak
    torque = combined * scale
    horsepower = torque * rpm / 5252.0

    afr_target = np.interp(
        rpm,
        [spec.idle_rpm, spec.tq_peak_rpm, spec.redline_rpm],
        [13.4, 12.8, 13.3],
    )
    afr_target_int = np.rint(afr_target * 10).astype(int)

    map_kpa = np.where(
        rpm < 2800,
        30 + (rpm - spec.idle_rpm) / max(1.0, (2800 - spec.idle_rpm)) * 70,
        100,
    )
    map_kpa = np.clip(map_kpa, 30, 100)

    ve_front = 60 + (torque / spec.max_tq) * 35
    ve_rear = np.clip(ve_front + 2.0, 0, 100)

    afr_cmd = afr_target_int / 10.0
    afr_meas = afr_cmd - 0.12

    iat = (
        100 + (rpm - spec.idle_rpm) / max(1.0, (spec.redline_rpm - spec.idle_rpm)) * 15
    )
    vbatt = (
        13.8
        + (rpm - spec.idle_rpm) / max(1.0, (spec.redline_rpm - spec.idle_rpm)) * 0.2
    )
    tps = np.clip(
        5 + (rpm - spec.idle_rpm) / max(1.0, (2500 - spec.idle_rpm)) * 95, 5, 100
    )

    data = {
        "Engine RPM": rpm,
        "MAP kPa": map_kpa,
        "Torque": torque,
        "AFR Target F": afr_target_int,
        "AFR Target R": afr_target_int,
        "VE F": ve_front,
        "VE R": ve_rear,
        "AFR Cmd F": afr_cmd,
        "AFR Cmd R": afr_cmd,
        "AFR Meas F": afr_meas,
        "AFR Meas R": afr_meas,
        "IAT F": iat,
        "Knock": np.zeros_like(rpm),
        "VBatt": vbatt,
        "TPS": tps,
    }
    df = pd.DataFrame(data)
    return df[COLUMN_ORDER]


def save_winpep_csv(df: pd.DataFrame, meta: DynoChartMeta, base_dir: str) -> str:
    target_path = safe_path(str(Path(base_dir) / "runs" / meta.id / "run1.csv"))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target_path, index=False)
    rel_path = target_path.relative_to(Path.cwd())
    logger.info("Saved synthetic WinPEP CSV for %s to %s", meta.id, rel_path)
    return str(rel_path)


__all__ = [
    "build_curve_spec",
    "generate_synthetic_pull",
    "save_winpep_csv",
    "COLUMN_ORDER",
]
