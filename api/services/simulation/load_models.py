"""
Load models for dyno simulation.

Provides:
- Eddy current brake absorption model
- Road load resistance model (SAE J2264)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class EddyCurrentBrake:
    """Eddy current brake model with response lag."""

    max_brake_torque: float = 800.0
    brake_response_rate: float = 100.0  # ft-lb/second
    eddy_rpm_factor: float = 0.8

    load_target: float = 0.0  # 0-100%
    current_load: float = 0.0  # 0-100%

    def set_load_target(self, load_pct: float) -> None:
        self.load_target = max(0.0, min(100.0, load_pct))

    def update(self, rpm: float, dt: float) -> float:
        """Update current load and return brake torque (ft-lb)."""
        load_diff = self.load_target - self.current_load
        max_change = self.brake_response_rate * dt
        self.current_load += max(-max_change, min(max_change, load_diff))

        rpm_factor = min(1.0, rpm / 6000.0)
        rpm_factor *= self.eddy_rpm_factor

        return self.max_brake_torque * (self.current_load / 100.0) * rpm_factor


@dataclass
class RoadLoadModel:
    """SAE J2264 road load model."""

    rolling_a: float = 80.0  # lb
    speed_b: float = 0.6  # lb/mph
    aero_c: float = 0.03  # lb/mph^2
    vehicle_weight_lbs: float = 850.0
    drivetrain_ratio: float = 1.0
    tire_circumference_ft: float = 6.8
    grade_pct: float = 0.0

    def speed_mph_from_drum(self, drum_rpm: float) -> float:
        wheel_rpm = drum_rpm / max(self.drivetrain_ratio, 1e-3)
        return self.tire_circumference_ft * wheel_rpm * 60.0 / 5280.0

    def road_force_lbs(self, speed_mph: float) -> float:
        rolling = self.rolling_a
        speed_term = self.speed_b * speed_mph
        aero = self.aero_c * (speed_mph**2)
        grade = self.vehicle_weight_lbs * (self.grade_pct / 100.0)
        return rolling + speed_term + aero + grade

    def torque_ftlb(self, drum_rpm: float, drum_radius_ft: float) -> float:
        speed_mph = self.speed_mph_from_drum(drum_rpm)
        force = self.road_force_lbs(speed_mph)
        return force * drum_radius_ft

    @classmethod
    def preset_street_glide(cls) -> "RoadLoadModel":
        return cls(
            rolling_a=85.0,
            speed_b=0.65,
            aero_c=0.035,
            vehicle_weight_lbs=900.0,
            drivetrain_ratio=1.0,
            tire_circumference_ft=6.9,
            grade_pct=0.0,
        )
