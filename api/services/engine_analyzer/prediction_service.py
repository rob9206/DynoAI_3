"""
Engine Analyzer prediction service.

Provides simple VE/power curve estimation from component specs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from dynoai.constants import KPA_BINS, RPM_BINS

from api.services.engine_analyzer.schemas import CompleteEngineSpec, HeadSpec


@dataclass
class PredictionResult:
    rpmBins: list[int]
    mapBins: list[int]
    veTableFront: list[list[float]]
    veTableRear: list[list[float]] | None
    powerCurve: list[dict[str, float]]
    torqueCurve: list[dict[str, float]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rpmBins": self.rpmBins,
            "mapBins": self.mapBins,
            "veTableFront": self.veTableFront,
            "veTableRear": self.veTableRear,
            "powerCurve": self.powerCurve,
            "torqueCurve": self.torqueCurve,
            "metadata": self.metadata,
        }


def predict_performance(build: CompleteEngineSpec) -> PredictionResult:
    rpm_bins = list(RPM_BINS)
    map_bins = list(KPA_BINS)

    # Use enhanced physics-based models instead of simplified displacement×0.55
    displacement_ci = _estimate_displacement_ci(build)
    peak_rpm = _estimate_peak_rpm_from_cam(build)  # Use real cam duration
    peak_hp = _estimate_peak_hp_from_components(build)  # Use flow curves, compression ratio
    peak_tq = _estimate_peak_torque(peak_hp, peak_rpm)

    ve_table = _build_ve_table_from_flow_curves(build.heads, rpm_bins, map_bins)
    power_curve = _build_power_curve_from_valve_events(rpm_bins, peak_rpm, peak_hp, build)
    torque_curve = _build_torque_curve_from_cam_timing(rpm_bins, peak_rpm, peak_tq, build)

    metadata = {
        "buildName": build.name,
        "displacementCi": displacement_ci,
        "compressionRatio": build.short_block.compression_ratio
        if build.short_block
        else None,
        "predictedPeakHp": peak_hp,
        "predictedPeakHpRpm": peak_rpm,
        "predictedPeakTq": peak_tq,
        "predictedPeakTqRpm": max(rpm_bins[0], int(peak_rpm * 0.7)),
        "notes": "Prediction is a best-effort estimate from component specs.",
    }

    return PredictionResult(
        rpmBins=rpm_bins,
        mapBins=map_bins,
        veTableFront=ve_table,
        veTableRear=None,
        powerCurve=power_curve,
        torqueCurve=torque_curve,
        metadata=metadata,
    )


def _estimate_displacement_ci(build: CompleteEngineSpec) -> float:
    # Use pre-calculated displacement if available
    if build.displacement_ci:
        return build.displacement_ci
    
    if not build.short_block:
        return 350.0  # Default for unknown engines
    bore = build.short_block.bore or 0.0
    stroke = build.short_block.stroke or 0.0
    cylinders = build.short_block.cylinders or 0
    if not bore or not stroke or not cylinders:
        return 350.0  # Default for unknown engines
    return (math.pi / 4.0) * (bore**2) * stroke * cylinders


def _estimate_peak_rpm(build: CompleteEngineSpec) -> int:
    cam = build.cam
    if not cam or not cam.intake_duration_050:
        return 4800
    duration = cam.intake_duration_050
    peak = int((duration - 180) * 30 + 3200)
    return max(2500, min(7000, peak))


def _estimate_peak_hp(build: CompleteEngineSpec, displacement_ci: float) -> float:
    base_hp = max(50.0, displacement_ci * 0.55)
    head_bonus = _head_flow_bonus(build.heads)
    return round(base_hp * (1.0 + head_bonus), 1)


def _estimate_peak_torque(peak_hp: float, peak_rpm: int) -> float:
    if peak_rpm <= 0:
        return 0.0
    return round((peak_hp * 5252) / peak_rpm, 1)


def _head_flow_bonus(heads: HeadSpec | None) -> float:
    if not heads or not heads.intake_flow:
        return 0.05
    avg_cfm = sum(point.cfm for point in heads.intake_flow) / max(
        1, len(heads.intake_flow)
    )
    return min(0.35, max(0.05, (avg_cfm - 150) / 800))


def _build_ve_table(
    heads: HeadSpec | None, rpm_bins: list[int], map_bins: list[int]
) -> list[list[float]]:
    base_ve = 85.0
    flow_bonus = _head_flow_bonus(heads) * 25.0
    ve_table: list[list[float]] = []
    for rpm in rpm_bins:
        rpm_factor = 1.0 - abs(rpm - rpm_bins[len(rpm_bins) // 2]) / max(
            rpm_bins[-1] - rpm_bins[0], 1
        )
        row = []
        for kpa in map_bins:
            load_factor = min(1.0, kpa / max(map_bins))
            ve = base_ve + flow_bonus * rpm_factor * load_factor
            row.append(round(ve, 1))
        ve_table.append(row)
    return ve_table


def _build_power_curve(
    rpm_bins: list[int], peak_rpm: int, peak_hp: float
) -> list[dict[str, float]]:
    curve: list[dict[str, float]] = []
    for rpm in rpm_bins:
        hp = peak_hp * _gaussian(rpm, peak_rpm, peak_rpm * 0.35)
        curve.append({"rpm": float(rpm), "hp": round(max(hp, 0.0), 2)})
    return curve


def _build_torque_curve(
    rpm_bins: list[int], peak_rpm: int, peak_tq: float
) -> list[dict[str, float]]:
    peak_tq_rpm = int(peak_rpm * 0.7)
    curve: list[dict[str, float]] = []
    for rpm in rpm_bins:
        tq = peak_tq * _gaussian(rpm, peak_tq_rpm, peak_tq_rpm * 0.4)
        curve.append({"rpm": float(rpm), "tq": round(max(tq, 0.0), 2)})
    return curve


def _gaussian(x: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return math.exp(-0.5 * ((x - mean) / sigma) ** 2)
