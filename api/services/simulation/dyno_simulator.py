"""
Dyno Simulator Service - Generates realistic live dyno data for testing.

Physics-Based Simulation:
- Rotational dynamics with realistic inertia
- Torque-based acceleration (not time-based)
- Volumetric efficiency modeling
- Thermal effects on power output
- Drivetrain losses and friction
- Air density corrections
- Realistic throttle response

This allows full testing of the JetDrive Command Center without hardware.

Dyno Configuration:
- Uses actual drum specs from DynoConfig (Dynoware RT-150)
- Drum 1: Mass 14.121 slugs, Circumference 4.673 ft
- Force calculation: F = τ / r (torque / drum radius)
- HP calculation: P = F × v / 550 (force × velocity / conversion)
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import numpy as np

from api.config import get_config

# Physics Constants
# =================
# Unit conversion factors for rotational dynamics

# Torque (lb·ft) to angular acceleration (rad/s²) scaling factor
# This accounts for:
# 1. Dyno gearing ratio (~2.5:1 typical)
# 2. Unit conversions between imperial and SI
# 3. Empirical calibration to match real dyno pull times (8-10 seconds)
# Formula: α = (τ × SCALE) / I, where I is total inertia in lb·ft²
# Reduced from 80.0 to 50.0 for realistic acceleration rate
TORQUE_TO_ANGULAR_ACCEL_SCALE = 50.0

# Drag coefficient for aerodynamic/mechanical losses
# Quadratic drag: drag_factor = 1.0 - (DRAG_COEFF × rpm/1000) × dt
DRAG_COEFFICIENT = 0.00015

# Default engine braking coefficient during deceleration (configurable via SimulatorConfig)
# Angular velocity reduction: ω_new = ω × (1.0 - brake_coeff * dt)
# Tuned so coastdown is gradual (multi-second), not an instant RPM cliff.
DEFAULT_ENGINE_BRAKE_COEFFICIENT = 0.18

# Knock detection thresholds
KNOCK_AFR_LEAN_THRESHOLD = 1.0  # AFR above target at high load triggers knock
KNOCK_IAT_THRESHOLD_F = 120.0  # Intake air temp that increases knock risk
KNOCK_TIMING_RETARD_DEG = 4.0  # Degrees of timing retarded when knock detected


class SimState(Enum):
    """Simulation state machine states."""

    IDLE = "idle"
    PULL = "pull"
    DECEL = "decel"
    COOLDOWN = "cooldown"
    STOPPED = "stopped"


@dataclass
class EngineProfile:
    """Engine profile for simulation."""

    name: str
    family: str
    displacement_ci: float
    idle_rpm: float
    redline_rpm: float
    max_hp: float
    hp_peak_rpm: float
    max_tq: float
    tq_peak_rpm: float
    target_afr_idle: float = 14.0
    target_afr_wot: float = 12.5

    # Physics parameters
    num_cylinders: int = 2
    bore_inches: float = 4.0
    stroke_inches: float = 4.5
    compression_ratio: float = 10.5

    # Inertia (lb·ft²) - engine + flywheel + dyno drum
    engine_inertia: float = 0.8  # Typical V-twin
    dyno_inertia: float = 2.5  # Dyno drum inertia

    # Efficiency parameters
    mechanical_efficiency: float = 0.85  # Friction losses
    volumetric_efficiency_peak: float = 0.90  # VE at optimal RPM

    # Thermal
    optimal_temp_f: float = 180.0  # Optimal operating temp
    heat_rate: float = 0.15  # How fast engine heats during pull

    @classmethod
    def m8_114(cls) -> "EngineProfile":
        """Milwaukee-Eight 114 profile."""
        return cls(
            name="M8-114 Stage 2",
            family="M8",
            displacement_ci=114.0,
            idle_rpm=900.0,
            redline_rpm=5800.0,
            max_hp=110.0,
            hp_peak_rpm=5000.0,
            max_tq=122.0,
            tq_peak_rpm=3200.0,
            num_cylinders=2,
            bore_inches=4.016,
            stroke_inches=4.5,
            compression_ratio=10.5,
            engine_inertia=0.85,
            dyno_inertia=4.5,  # Increased from 2.8 to slow acceleration
            mechanical_efficiency=0.87,
            volumetric_efficiency_peak=0.88,
        )

    @classmethod
    def m8_131(cls) -> "EngineProfile":
        """Milwaukee-Eight 131 profile."""
        return cls(
            name="M8-131 Big Bore",
            family="M8",
            displacement_ci=131.0,
            idle_rpm=900.0,
            redline_rpm=5600.0,
            max_hp=145.0,
            hp_peak_rpm=5000.0,
            max_tq=158.0,
            tq_peak_rpm=3500.0,
            num_cylinders=2,
            bore_inches=4.25,
            stroke_inches=4.5,
            compression_ratio=10.8,
            engine_inertia=0.90,
            dyno_inertia=4.5,  # Increased from 2.8 to slow acceleration
            mechanical_efficiency=0.86,
            volumetric_efficiency_peak=0.90,
        )

    @classmethod
    def twin_cam_103(cls) -> "EngineProfile":
        """Twin Cam 103 profile."""
        return cls(
            name="Twin Cam 103",
            family="TwinCam",
            displacement_ci=103.0,
            idle_rpm=900.0,
            redline_rpm=5500.0,
            max_hp=85.0,
            hp_peak_rpm=4800.0,
            max_tq=100.0,
            tq_peak_rpm=3000.0,
            num_cylinders=2,
            bore_inches=3.875,
            stroke_inches=4.375,
            compression_ratio=9.7,
            engine_inertia=0.75,
            dyno_inertia=2.8,
            mechanical_efficiency=0.84,
            volumetric_efficiency_peak=0.85,
        )

    @classmethod
    def sportbike_600(cls) -> "EngineProfile":
        """Sport bike 600cc profile."""
        return cls(
            name="CBR600RR",
            family="Sportbike",
            displacement_ci=36.6,  # 600cc = 36.6ci
            idle_rpm=1200.0,
            redline_rpm=14500.0,
            max_hp=118.0,
            hp_peak_rpm=13500.0,
            max_tq=48.0,
            tq_peak_rpm=10500.0,
            target_afr_wot=12.8,
            num_cylinders=4,
            bore_inches=2.64,  # 67mm
            stroke_inches=1.65,  # 42mm
            compression_ratio=12.2,
            engine_inertia=0.25,  # Much lighter
            dyno_inertia=1.5,
            mechanical_efficiency=0.90,  # High-performance engine
            volumetric_efficiency_peak=0.95,
        )


@dataclass
class SimulatorConfig:
    """Configuration for the dyno simulator."""

    profile: EngineProfile = field(default_factory=EngineProfile.m8_114)

    # Timing
    update_rate_hz: float = 50.0  # Data points per second (higher for physics)

    # Physics scaling
    # Torque -> angular acceleration scaling factor (units/gear calibration)
    # Default is tuned so a typical V-twin pull lasts ~8-10s from idle to redline.
    torque_to_angular_accel_scale: float = 5.5

    # Behavior
    auto_pull: bool = False  # Auto-start pulls periodically
    auto_pull_interval_sec: float = 15.0

    # Throttle response
    throttle_response_rate: float = 200.0  # TPS % per second (fast DBW/cable snap)

    # Environmental conditions
    ambient_temp_f: float = 75.0
    barometric_pressure_inhg: float = 29.92  # Sea level
    humidity_pct: float = 50.0

    # Noise/realism
    rpm_noise_pct: float = 0.3  # ±0.3% RPM noise
    afr_noise: float = 0.12  # ±0.12 AFR noise
    torque_noise_pct: float = 1.5  # ±1.5% torque noise

    # Physics realism
    enable_thermal_effects: bool = True
    enable_air_density_correction: bool = True
    enable_pumping_losses: bool = True

    # Coastdown / engine braking
    engine_brake_coefficient: float = DEFAULT_ENGINE_BRAKE_COEFFICIENT


@dataclass
class PhysicsState:
    """Internal physics state for simulation."""

    rpm: float = 900.0
    angular_velocity: float = 0.0  # rad/s
    angular_acceleration: float = 0.0  # rad/s²

    tps_actual: float = 0.0  # Actual throttle position
    tps_target: float = 0.0  # Target throttle position

    engine_temp_f: float = 180.0  # Current engine temp
    iat_f: float = 85.0  # Intake air temp

    total_inertia: float = 3.3  # lb·ft²

    # Accumulated values
    fuel_consumed_gal: float = 0.0
    heat_generated_btu: float = 0.0

    # Knock detection
    knock_detected: bool = False
    knock_count: int = 0


@dataclass
class PhysicsSnapshot:
    """
    Complete physics state snapshot for detailed analysis.

    Captures all internal physics calculations at a single timestep,
    useful for debugging, validation, and research.
    """

    timestamp: float
    rpm: float
    angular_velocity: float  # rad/s
    angular_acceleration: float  # rad/s²

    # Throttle
    tps_actual: float
    tps_target: float

    # Torque breakdown
    torque_base: float  # Base torque from curve
    torque_effective: float  # After all corrections
    horsepower: float

    # Correction factors
    volumetric_efficiency: float
    pumping_loss: float
    thermal_factor: float
    air_density_factor: float
    mechanical_efficiency: float

    # Thermal state
    engine_temp_f: float
    iat_f: float

    # Environmental
    ambient_temp_f: float
    barometric_pressure_inhg: float
    humidity_pct: float

    # Knock
    knock_detected: bool
    knock_risk_score: float  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "timestamp": self.timestamp,
            "rpm": self.rpm,
            "angular_velocity": self.angular_velocity,
            "angular_acceleration": self.angular_acceleration,
            "tps_actual": self.tps_actual,
            "tps_target": self.tps_target,
            "torque_base": self.torque_base,
            "torque_effective": self.torque_effective,
            "horsepower": self.horsepower,
            "volumetric_efficiency": self.volumetric_efficiency,
            "pumping_loss": self.pumping_loss,
            "thermal_factor": self.thermal_factor,
            "air_density_factor": self.air_density_factor,
            "mechanical_efficiency": self.mechanical_efficiency,
            "engine_temp_f": self.engine_temp_f,
            "iat_f": self.iat_f,
            "ambient_temp_f": self.ambient_temp_f,
            "barometric_pressure_inhg": self.barometric_pressure_inhg,
            "humidity_pct": self.humidity_pct,
            "knock_detected": self.knock_detected,
            "knock_risk_score": self.knock_risk_score,
        }


@dataclass
class SimulatedChannels:
    """Current simulated channel values."""

    rpm: float = 0.0
    force_lbs: float = 0.0
    torque_ftlb: float = 0.0
    horsepower: float = 0.0
    afr_front: float = 14.7
    afr_rear: float = 14.7
    map_kpa: float = 30.0
    tps_pct: float = 0.0
    iat_f: float = 85.0
    vbatt: float = 13.8
    acceleration_g: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to channel dictionary for API response."""
        now = int(time.time() * 1000)
        return {
            "Digital RPM 1": {
                "id": 42,
                "name": "Digital RPM 1",
                "value": self.rpm,
                "timestamp": now,
            },
            "Digital RPM 2": {
                "id": 43,
                "name": "Digital RPM 2",
                "value": self.rpm * 0.98,
                "timestamp": now,
            },
            "Force Drum 1": {
                "id": 39,
                "name": "Force Drum 1",
                "value": self.force_lbs,
                "timestamp": now,
            },
            "Acceleration": {
                "id": 40,
                "name": "Acceleration",
                "value": self.acceleration_g,
                "timestamp": now,
            },
            "Air/Fuel Ratio 1": {
                "id": 23,
                "name": "Air/Fuel Ratio 1",
                "value": self.afr_front,
                "timestamp": now,
            },
            "Air/Fuel Ratio 2": {
                "id": 28,
                "name": "Air/Fuel Ratio 2",
                "value": self.afr_rear,
                "timestamp": now,
            },
            # Also include chan_X format for compatibility
            "Torque": {
                "id": 100,
                "name": "Torque",
                "value": self.torque_ftlb,
                "timestamp": now,
            },
            "Horsepower": {
                "id": 101,
                "name": "Horsepower",
                "value": self.horsepower,
                "timestamp": now,
            },
            "MAP kPa": {
                "id": 102,
                "name": "MAP kPa",
                "value": self.map_kpa,
                "timestamp": now,
            },
            "TPS": {"id": 103, "name": "TPS", "value": self.tps_pct, "timestamp": now},
            "IAT": {"id": 104, "name": "IAT", "value": self.iat_f, "timestamp": now},
            "VBatt": {
                "id": 105,
                "name": "VBatt",
                "value": self.vbatt,
                "timestamp": now,
            },
        }


class DynoSimulator:
    """
    Simulates a dyno session with realistic physics-based data generation.

    Physics Model:
    - Rotational dynamics: τ = I·α (Torque = Inertia × Angular Acceleration)
    - Volumetric efficiency affects cylinder filling
    - Thermal effects reduce power as engine heats
    - Air density corrections for temperature/pressure
    - Realistic throttle lag and response

    NEW: Virtual ECU Integration
    - Can simulate ECU fuel delivery based on VE tables
    - Creates realistic AFR errors when VE tables are wrong
    - Enables closed-loop tuning simulation
    """

    def __init__(self, config: SimulatorConfig | None = None, virtual_ecu=None):
        self.config = config or SimulatorConfig()
        self.state = SimState.STOPPED
        self.channels = SimulatedChannels()
        self.physics = PhysicsState()

        # Virtual ECU for simulating fuel delivery (optional)
        self.virtual_ecu = virtual_ecu

        # Pull state
        self._pull_start_time: float = 0.0
        self._pull_progress: float = 0.0  # 0.0 to 1.0

        # Thread management
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Callbacks
        self._on_state_change: Callable[[SimState], None] | None = None
        self._on_pull_complete: Callable[[list[dict]], None] | None = None

        # Pull data collection
        self._pull_data: list[dict[str, float]] = []
        self._pull_elapsed_s: float = 0.0

        # Physics snapshot collection (for detailed analysis)
        self._physics_snapshots: list[PhysicsSnapshot] = []
        self._collect_snapshots: bool = False  # Enable/disable snapshot collection

        # Pre-compute torque/HP curves
        self._precompute_curves()

        # Initialize physics state
        self._init_physics()

    def _init_physics(self):
        """Initialize physics state."""
        profile = self.config.profile
        self.physics.rpm = profile.idle_rpm
        self.physics.angular_velocity = self._rpm_to_rad_s(profile.idle_rpm)

        # Ensure total inertia is never zero (would cause division by zero in physics)
        # Prefer the configured dyno drum inertia when available, so the simulator matches
        # your actual RT-150 drum inertia. Fall back to the profile's dyno_inertia.
        dyno_inertia = float(profile.dyno_inertia)
        try:
            dyno_cfg = get_config().dyno
            cfg_inertia = float(dyno_cfg.drum1.rotational_inertia_lbft2)
            if cfg_inertia > 0:
                dyno_inertia = cfg_inertia
        except Exception:
            pass

        total_inertia = float(profile.engine_inertia) + dyno_inertia
        self.physics.total_inertia = max(0.1, total_inertia)  # Minimum 0.1 lb·ft²

        self.physics.engine_temp_f = profile.optimal_temp_f
        self.physics.iat_f = self.config.ambient_temp_f + 10  # Slightly warmer

    def _rpm_to_rad_s(self, rpm: float) -> float:
        """Convert RPM to radians per second."""
        return rpm * 2.0 * math.pi / 60.0

    def _rad_s_to_rpm(self, rad_s: float) -> float:
        """Convert radians per second to RPM."""
        return rad_s * 60.0 / (2.0 * math.pi)

    def _precompute_curves(self):
        """Pre-compute base torque and HP curves for the profile."""
        profile = self.config.profile

        # Generate RPM points
        rpm_points = np.linspace(profile.idle_rpm, profile.redline_rpm, 1000)

        # Build a base torque curve that matches BOTH:
        # - peak torque (max_tq @ tq_peak_rpm)
        # - peak horsepower (max_hp @ hp_peak_rpm), by ensuring torque at hp_peak_rpm is consistent:
        #   hp = tq * rpm / 5252  => tq_required = hp * 5252 / rpm
        #
        # The previous implementation only matched max_tq, which can produce unrealistic HP peaks/values.
        if profile.hp_peak_rpm > 0:
            tq_at_hp_peak = float(profile.max_hp) * 5252.0 / float(profile.hp_peak_rpm)
        else:
            tq_at_hp_peak = float(profile.max_tq) * 0.8

        # Sanity clamp: HP peak torque should never exceed peak torque for typical NA engines.
        tq_at_hp_peak = max(0.0, min(float(profile.max_tq), tq_at_hp_peak))

        # Anchor points for a plausible curve (piecewise linear, then smoothed/adjusted).
        # Idle torque roughly 35% of peak torque for big twins; sportbikes will be corrected by VE/efficiency later.
        tq_idle = float(profile.max_tq) * 0.35
        tq_redline = max(0.0, tq_at_hp_peak * 0.78)

        anchor_rpm = np.array(
            [
                float(profile.idle_rpm),
                float(profile.tq_peak_rpm),
                float(profile.hp_peak_rpm),
                float(profile.redline_rpm),
            ]
        )
        anchor_tq = np.array(
            [tq_idle, float(profile.max_tq), tq_at_hp_peak, tq_redline]
        )

        # Ensure anchors are strictly increasing in RPM (guard against bad profile inputs).
        order = np.argsort(anchor_rpm)
        anchor_rpm = anchor_rpm[order]
        anchor_tq = anchor_tq[order]

        torque = np.interp(rpm_points, anchor_rpm, anchor_tq)

        # Gentle smoothing to avoid sharp corners (simple moving average).
        # Keep window small so we don't destroy peaks.
        window = 9
        kernel = np.ones(window) / window
        torque = np.convolve(torque, kernel, mode="same")

        # Enforce exact peak torque at tq_peak_rpm via global scaling (smoothing can reduce the peak slightly).
        tq_at_tq_peak_now = float(
            np.interp(float(profile.tq_peak_rpm), rpm_points, torque)
        )
        if tq_at_tq_peak_now > 1e-6:
            torque *= float(profile.max_tq) / tq_at_tq_peak_now

        # Enforce torque at hp_peak_rpm with a smooth high-RPM adjustment that doesn't perturb low-RPM torque.
        tq_at_hp_now = float(np.interp(float(profile.hp_peak_rpm), rpm_points, torque))
        if tq_at_hp_now > 1e-6 and tq_at_hp_peak > 0:
            f = tq_at_hp_peak / tq_at_hp_now
            # Smoothstep from tq_peak_rpm -> hp_peak_rpm
            start = float(profile.tq_peak_rpm)
            end = (
                float(profile.hp_peak_rpm)
                if float(profile.hp_peak_rpm) > start
                else start + 1.0
            )
            x = np.clip((rpm_points - start) / (end - start), 0.0, 1.0)
            w = x * x * (3.0 - 2.0 * x)  # smoothstep
            torque *= 1.0 + (f - 1.0) * w

        torque = np.maximum(0.0, torque)

        # HP = TQ * RPM / 5252
        horsepower = torque * rpm_points / 5252.0

        # Store for interpolation
        self._rpm_curve = rpm_points
        self._base_torque_curve = torque
        self._base_hp_curve = horsepower

    def _get_base_torque_at_rpm(self, rpm: float) -> float:
        """Get base interpolated torque at given RPM (no corrections)."""
        return float(np.interp(rpm, self._rpm_curve, self._base_torque_curve))

    def _get_volumetric_efficiency(self, rpm: float, tps: float) -> float:
        """
        Calculate volumetric efficiency based on RPM and throttle.

        VE represents how well the cylinders fill with air/fuel mixture.
        - Peak VE at optimal RPM range
        - Reduced at low RPM (poor scavenging)
        - Reduced at high RPM (flow restrictions)
        - Reduced at partial throttle (pumping losses)
        """
        profile = self.config.profile

        # RPM-based VE (breathing efficiency)
        #
        # Important realism note:
        # The simulator already has a shaped base torque curve. If we apply a symmetric
        # gaussian VE curve on top (centered at tq_peak_rpm), the resulting torque/HP
        # often becomes an unrealistic "bell" early in the pull.
        #
        # To avoid that, at (near) WOT we use a flatter, more realistic VE profile:
        # - ramps up from idle
        # - plateaus through midrange
        # - gently tapers near redline
        ve_peak = float(profile.volumetric_efficiency_peak)

        # Guard against invalid profile values
        idle = float(profile.idle_rpm)
        tq_peak = float(profile.tq_peak_rpm) if profile.tq_peak_rpm > 0 else idle * 2.5
        hp_peak = (
            float(profile.hp_peak_rpm)
            if profile.hp_peak_rpm > 0
            else max(tq_peak + 500.0, idle * 4.0)
        )
        redline = (
            float(profile.redline_rpm) if profile.redline_rpm > 0 else hp_peak + 500.0
        )

        rpm_f = float(rpm)
        rpm_f = max(idle * 0.5, min(redline * 1.05, rpm_f))

        if tps >= 80.0:
            # WOT: flat-ish VE so HP keeps building with RPM (no early bell).
            # Start slightly under peak, reach peak by tq_peak, hold until hp_peak, then taper.
            ve_low = ve_peak * 0.88
            ve_high = ve_peak * 0.86

            if rpm_f <= tq_peak:
                denom = max(1.0, tq_peak - idle)
                x = (rpm_f - idle) / denom
                x = max(0.0, min(1.0, x))
                # Smoothstep ramp
                w = x * x * (3.0 - 2.0 * x)
                rpm_ve = ve_low + (ve_peak - ve_low) * w
            elif rpm_f <= hp_peak:
                rpm_ve = ve_peak
            else:
                denom = max(1.0, redline - hp_peak)
                x = (rpm_f - hp_peak) / denom
                x = max(0.0, min(1.0, x))
                w = x * x * (3.0 - 2.0 * x)
                rpm_ve = ve_peak + (ve_high - ve_peak) * w
        else:
            # Part-throttle: keep a stronger RPM-shaped VE (helps realism under load transitions).
            if tq_peak > 0:
                rpm_ratio = rpm_f / tq_peak
            else:
                rpm_ratio = 1.0
            rpm_ve = ve_peak * math.exp(-0.5 * ((rpm_ratio - 1.0) / 0.45) ** 2)

            # Low RPM penalty (poor scavenging)
            if rpm_f < idle * 1.5 and idle > 0:
                low_rpm_factor = rpm_f / (idle * 1.5)
                rpm_ve *= 0.6 + 0.4 * low_rpm_factor

            # High RPM penalty (flow restrictions)
            if rpm_f > hp_peak:
                rpm_range = redline - hp_peak
                if rpm_range > 0:
                    high_rpm_factor = (redline - rpm_f) / rpm_range
                    rpm_ve *= 0.75 + 0.25 * max(0.0, high_rpm_factor)

        # Throttle-based VE (pumping losses at partial throttle)
        # At closed throttle (0%), engine barely breathes (5% VE)
        # This ensures proper deceleration with closed throttle
        throttle_ve = 0.05 + 0.95 * (tps / 100.0)  # 5% at closed, 100% at WOT

        return min(1.0, max(0.0, rpm_ve * throttle_ve))

    def _get_pumping_losses(self, rpm: float, tps: float) -> float:
        """
        Calculate pumping losses (parasitic losses from moving air).

        Higher at:
        - Low throttle (high vacuum)
        - High RPM (more pumping cycles)

        At closed throttle + high RPM, pumping losses should exceed torque production,
        effectively making net torque zero (engine acts as brake, not motor).
        """
        if not self.config.enable_pumping_losses:
            return 0.0

        profile = self.config.profile

        # Vacuum-related losses (much worse at low throttle)
        # At closed throttle, engine is pumping against high vacuum
        # This should consume more power than the minimal combustion produces
        vacuum_loss = (100 - tps) / 100.0 * 0.40  # Up to 40% loss at closed throttle

        # Extra penalty at very low throttle (< 5%) to simulate fuel cut / near-zero combustion
        # Note: Reduced from 0.30 to 0.15 because dyno inertia already provides gradual decel
        if tps < 5.0:
            vacuum_loss += 0.15  # Additional 15% loss when essentially closed

        # RPM-related losses (friction increases with speed)
        if profile.redline_rpm > 0:
            rpm_ratio = rpm / profile.redline_rpm
        else:
            rpm_ratio = 0.5  # Fallback

        friction_loss = (
            rpm_ratio * 0.15
        )  # Up to 15% loss at redline (increased from 8%)

        return min(1.0, vacuum_loss + friction_loss)  # Cap at 100% loss

    def _get_thermal_correction(self) -> float:
        """
        Calculate power correction factor based on engine temperature.

        - Optimal power at optimal temp
        - Reduced when too cold (poor atomization, rich mixture)
        - Reduced when too hot (detonation risk, timing retard, density loss)
        """
        if not self.config.enable_thermal_effects:
            return 1.0

        profile = self.config.profile
        temp_diff = abs(self.physics.engine_temp_f - profile.optimal_temp_f)

        # Power loss increases with temperature deviation
        if self.physics.engine_temp_f < profile.optimal_temp_f:
            # Cold: 1% loss per 10°F below optimal
            return 1.0 - (temp_diff / 10.0 * 0.01)
        else:
            # Hot: 1.5% loss per 10°F above optimal (worse than cold)
            return 1.0 - (temp_diff / 10.0 * 0.015)

    def _get_air_density_correction(self) -> float:
        """
        Calculate air density correction factor using SAE J1349 method.

        Power is proportional to air density:
        - Higher density = more oxygen = more power
        - Affected by temperature, pressure, humidity

        Includes humidity correction as water vapor displaces oxygen.
        """
        if not self.config.enable_air_density_correction:
            return 1.0

        # Standard conditions: 59°F, 29.92 inHg, 0% humidity
        std_temp_r = 518.67  # Rankine (459.67 + 59)
        std_pressure = 29.92

        # Current conditions
        temp_r = self.physics.iat_f + 459.67
        temp_f = self.physics.iat_f
        pressure = self.config.barometric_pressure_inhg
        humidity = self.config.humidity_pct

        # Protect against invalid temperature (absolute zero or below)
        if temp_r <= 0:
            temp_r = 518.67  # Fallback to standard temp

        # Protect against zero pressure
        if pressure <= 0:
            pressure = std_pressure  # Fallback to standard pressure

        # Base air density ratio (ideal gas law)
        density_ratio = (pressure / std_pressure) * (std_temp_r / temp_r)

        # Humidity correction
        # Water vapor has lower density than air, reducing oxygen content
        # Using simplified vapor pressure calculation (Antoine equation approximation)
        if humidity > 0:
            # Saturation vapor pressure (inHg) - simplified Magnus formula
            vapor_pressure_sat = 0.02953 * math.exp(
                17.27 * (temp_f - 32) / (237.3 + (temp_f - 32))
            )

            # Actual vapor pressure
            vapor_pressure = vapor_pressure_sat * (humidity / 100.0)

            # Humidity correction factor (water vapor displaces dry air)
            # Molecular weight ratio: H2O (18) / Air (28.97) = 0.622
            # Protect against division by zero
            if pressure > 0:
                humidity_correction = 1.0 - 0.378 * (vapor_pressure / pressure)
                density_ratio *= humidity_correction

        return density_ratio

    def _check_knock_conditions(
        self, rpm: float, tps: float, afr: float
    ) -> tuple[bool, float]:
        """
        Check for conditions that would cause engine knock/detonation.

        Returns:
            (knock_detected, knock_risk_score)

        Knock risk factors:
        - Too lean at high load (most common)
        - High intake air temperature
        - High engine temperature
        - High load + high RPM
        """
        profile = self.config.profile

        # Calculate target AFR for current conditions
        target_afr = self._get_target_afr(rpm, tps)

        risk_score = 0.0
        knock = False

        # Factor 1: Lean condition at high load (40% weight)
        if tps > 80:  # High load
            afr_error = afr - target_afr
            if afr_error > KNOCK_AFR_LEAN_THRESHOLD:
                lean_risk = min(1.0, (afr_error - KNOCK_AFR_LEAN_THRESHOLD) / 2.0)
                risk_score += lean_risk * 0.4
                if afr_error > KNOCK_AFR_LEAN_THRESHOLD + 1.0:
                    knock = True

        # Factor 2: High intake air temperature (25% weight)
        if self.physics.iat_f > KNOCK_IAT_THRESHOLD_F:
            iat_risk = min(1.0, (self.physics.iat_f - KNOCK_IAT_THRESHOLD_F) / 30.0)
            risk_score += iat_risk * 0.25
            if self.physics.iat_f > KNOCK_IAT_THRESHOLD_F + 20:
                knock = True

        # Factor 3: High engine temperature (20% weight)
        if self.physics.engine_temp_f > profile.optimal_temp_f + 20:
            temp_excess = self.physics.engine_temp_f - (profile.optimal_temp_f + 20)
            temp_risk = min(1.0, temp_excess / 40.0)
            risk_score += temp_risk * 0.20

        # Factor 4: High load + high RPM (15% weight)
        if tps > 85 and rpm > profile.hp_peak_rpm:
            rpm_load_risk = (rpm / profile.redline_rpm) * (tps / 100.0)
            risk_score += rpm_load_risk * 0.15

        risk_score = min(1.0, risk_score)

        return knock, risk_score

    def _calculate_effective_torque(
        self, rpm: float, tps: float, afr: float = 0.0
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate effective torque with all physics corrections applied.

        Returns:
            (effective_torque, correction_factors_dict)

        Torque_eff = Torque_base × VE × (1 - pumping_loss) × thermal × air_density × mechanical_eff × knock_penalty
        """
        profile = self.config.profile

        # Base torque from engine curve
        base_torque = self._get_base_torque_at_rpm(rpm)

        # Volumetric efficiency (cylinder filling)
        ve = self._get_volumetric_efficiency(rpm, tps)

        # Pumping losses
        pumping_loss = self._get_pumping_losses(rpm, tps)

        # Thermal effects
        thermal_factor = self._get_thermal_correction()

        # Air density
        air_density_factor = self._get_air_density_correction()

        # Mechanical efficiency (friction, etc.)
        mech_eff = profile.mechanical_efficiency

        # Knock detection (if AFR provided)
        knock_factor = 1.0
        knock_risk = 0.0
        if afr > 0:
            knock, knock_risk = self._check_knock_conditions(rpm, tps, afr)
            if knock:
                # Timing retard reduces torque ~1% per degree
                knock_factor = 1.0 - (KNOCK_TIMING_RETARD_DEG * 0.01)
                self.physics.knock_detected = True
                self.physics.knock_count += 1
            else:
                self.physics.knock_detected = False

        # Combine all factors
        effective_torque = (
            base_torque
            * ve
            * (1.0 - pumping_loss)
            * thermal_factor
            * air_density_factor
            * mech_eff
            * knock_factor
        )

        # Return torque and correction factors for snapshot
        factors = {
            "base_torque": base_torque,
            "ve": ve,
            "pumping_loss": pumping_loss,
            "thermal_factor": thermal_factor,
            "air_density_factor": air_density_factor,
            "mechanical_efficiency": mech_eff,
            "knock_factor": knock_factor,
            "knock_risk": knock_risk,
        }

        return max(0, effective_torque), factors

    def _update_throttle(self, dt: float):
        """Update actual throttle position with realistic lag."""
        # Throttle moves toward target at a limited rate (% per second)
        tps_diff = self.physics.tps_target - self.physics.tps_actual
        max_change_per_sec = self.config.throttle_response_rate
        max_change = max_change_per_sec * dt  # Scale by timestep

        if abs(tps_diff) <= max_change:
            self.physics.tps_actual = self.physics.tps_target
        else:
            self.physics.tps_actual += math.copysign(max_change, tps_diff)

        self.physics.tps_actual = max(0, min(100, self.physics.tps_actual))

    def _update_thermal(self, dt: float, power_hp: float):
        """Update engine temperature based on power output."""
        if not self.config.enable_thermal_effects:
            return

        profile = self.config.profile

        # Heat generation proportional to power
        heat_rate = power_hp * self.config.profile.heat_rate * dt

        # Cooling (radiator, oil, etc.)
        cooling_rate = (
            (self.physics.engine_temp_f - self.config.ambient_temp_f) * 0.02 * dt
        )

        # Update temperature
        self.physics.engine_temp_f += heat_rate - cooling_rate

        # Clamp to reasonable range
        self.physics.engine_temp_f = max(
            self.config.ambient_temp_f + 20, min(250, self.physics.engine_temp_f)
        )

        # IAT follows engine temp but lags
        iat_target = (
            self.config.ambient_temp_f
            + (self.physics.engine_temp_f - profile.optimal_temp_f) * 0.3
        )
        self.physics.iat_f += (iat_target - self.physics.iat_f) * 0.1 * dt

    def _update_physics(
        self, dt: float, afr: float = 0.0
    ) -> tuple[float, float, dict[str, float]]:
        """
        Update physics simulation for one timestep.

        Uses rotational dynamics: τ = I·α
        α = τ / I
        ω_new = ω_old + α·dt
        RPM_new = ω_new × (60 / 2π)

        Args:
            dt: Time step in seconds
            afr: Current air/fuel ratio (for knock detection)

        Returns:
            (torque, horsepower, correction_factors)
        """
        profile = self.config.profile

        # Net angular acceleration (and thus dyno-inferred torque/HP) is computed from the
        # drum's change in angular velocity over time. Capture ω_old so we can compute it.
        omega_prev = float(self.physics.angular_velocity)

        # Get effective engine torque at current RPM and throttle
        torque, factors = self._calculate_effective_torque(
            self.physics.rpm, self.physics.tps_actual, afr
        )

        # Calculate angular acceleration: α = τ / I
        # Using documented scaling factor for unit conversions and dyno gearing
        torque_scaled = torque * float(self.config.torque_to_angular_accel_scale)
        alpha_from_engine = torque_scaled / self.physics.total_inertia

        # Update angular velocity: ω = ω + α·dt
        self.physics.angular_velocity += alpha_from_engine * dt

        # Apply drag/friction (quadratic with RPM)
        drag_factor = 1.0 - (DRAG_COEFFICIENT * self.physics.rpm / 1000.0) * dt
        # Prevent negative drag factor (numerical stability)
        drag_factor = max(0.0, drag_factor)
        self.physics.angular_velocity *= drag_factor

        # Convert back to RPM
        self.physics.rpm = self._rad_s_to_rpm(self.physics.angular_velocity)

        # Clamp to valid range
        self.physics.rpm = max(
            profile.idle_rpm * 0.5, min(profile.redline_rpm * 1.05, self.physics.rpm)
        )

        # Resync angular velocity
        self.physics.angular_velocity = self._rpm_to_rad_s(self.physics.rpm)

        # Compute NET angular acceleration from the drum's actual ω change this step.
        omega_now = float(self.physics.angular_velocity)
        alpha_net = (omega_now - omega_prev) / max(dt, 1e-6)
        self.physics.angular_acceleration = alpha_net

        # Dyno-inferred torque and HP from inertia physics of the drum:
        # τ_dyno ≈ I_total * α / SCALE
        # HP_dyno = τ_dyno * RPM / 5252
        scale = float(self.config.torque_to_angular_accel_scale) or 1.0
        dyno_torque = (float(self.physics.total_inertia) * alpha_net) / scale
        dyno_hp = dyno_torque * float(self.physics.rpm) / 5252.0

        # Engine power (for thermal model)
        hp_engine = torque * self.physics.rpm / 5252.0

        # Update thermal state
        self._update_thermal(dt, hp_engine)

        # Expose dyno-inferred values in factors so the pull can log/display them
        factors["dyno_torque"] = dyno_torque
        factors["dyno_hp"] = dyno_hp
        factors["alpha_net"] = alpha_net
        factors["hp_engine"] = hp_engine

        return torque, hp_engine, factors

    def _get_target_afr(self, rpm: float, tps: float) -> float:
        """Calculate target AFR based on RPM and throttle position."""
        profile = self.config.profile

        if tps < 20:
            # Light throttle / idle
            return profile.target_afr_idle
        elif tps < 50:
            # Part throttle - blend
            t = (tps - 20) / 30.0
            return profile.target_afr_idle + t * (
                profile.target_afr_wot - profile.target_afr_idle
            )
        else:
            # WOT
            # Rich up more at higher RPM for safety
            rpm_factor = (rpm - profile.idle_rpm) / (
                profile.redline_rpm - profile.idle_rpm
            )
            return profile.target_afr_wot - (
                rpm_factor * 0.5
            )  # Goes richer at high RPM

    def _calculate_simulated_afr(self, rpm: float, map_kpa: float, tps: float) -> float:
        """
        Calculate AFR based on ECU fueling vs actual engine VE.

        This is the KEY function for virtual tuning!

        If virtual_ecu is provided:
            - Get actual VE from physics engine
            - ECU calculates fuel delivery based on its VE table
            - If ECU's VE table is wrong, AFR will be wrong
            - This creates realistic tuning errors

        If no virtual_ecu:
            - Return perfect target AFR (no tuning errors)

        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            tps: Throttle position (0-100%)

        Returns:
            Simulated AFR that would be measured by wideband O2 sensor
        """
        if self.virtual_ecu is None:
            # No ECU simulation - return perfect target AFR
            target_afr = self._get_target_afr(rpm, tps)
            # Add small sensor noise for realism
            afr_with_noise = target_afr + random.gauss(0, 0.05)
            # Clamp to sensor range
            return max(10.0, min(20.0, afr_with_noise))

        # Get actual VE from physics engine
        actual_ve = self._get_volumetric_efficiency(rpm, tps)

        # ECU calculates resulting AFR based on its (possibly wrong) VE table
        # For V-twin, we'll use front cylinder (could alternate or average)
        resulting_afr = self.virtual_ecu.calculate_resulting_afr(
            rpm, map_kpa, actual_ve, cylinder="front"
        )

        # Add realistic sensor noise (±0.05 AFR typical for wideband)
        afr_with_noise = resulting_afr + random.gauss(0, 0.05)

        # Clamp to sensor range
        return max(10.0, min(20.0, afr_with_noise))

    def _add_noise(self, value: float, noise_pct: float) -> float:
        """Add gaussian noise to a value."""
        noise = random.gauss(0, value * noise_pct / 100.0)
        return value + noise

    def start(self):
        """Start the simulator."""
        with self._lock:
            if self.state != SimState.STOPPED:
                return

            self._stop_event.clear()
            self.state = SimState.IDLE
            self._init_physics()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the simulator."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

        with self._lock:
            self.state = SimState.STOPPED
            self.channels = SimulatedChannels()

    def trigger_pull(self):
        """Manually trigger a WOT pull."""
        with self._lock:
            if self.state == SimState.IDLE:
                self.state = SimState.PULL
                self._pull_start_time = time.time()
                self._pull_progress = 0.0
                self._pull_data = []
                self._physics_snapshots = []
                self._pull_elapsed_s = 0.0

                # Set throttle target to WOT
                self.physics.tps_target = 100.0

                if self._on_state_change:
                    self._on_state_change(self.state)

    def get_state(self) -> SimState:
        """Get current simulation state."""
        with self._lock:
            return self.state

    def get_channels(self) -> dict[str, Any]:
        """Get current channel values for API."""
        with self._lock:
            return self.channels.to_dict()

    def get_pull_data(self) -> list[dict[str, float]]:
        """Get data from the last completed pull."""
        with self._lock:
            return list(self._pull_data)

    def get_physics_snapshots(self) -> list[PhysicsSnapshot]:
        """Get detailed physics snapshots from the last pull."""
        with self._lock:
            return list(self._physics_snapshots)

    def enable_snapshot_collection(self, enabled: bool = True):
        """Enable or disable detailed physics snapshot collection."""
        with self._lock:
            self._collect_snapshots = enabled
            if enabled:
                self._physics_snapshots = []

    def _create_physics_snapshot(
        self, torque: float, hp: float, factors: dict[str, float]
    ) -> PhysicsSnapshot:
        """Create a physics snapshot from current state."""
        return PhysicsSnapshot(
            timestamp=time.time(),
            rpm=self.physics.rpm,
            angular_velocity=self.physics.angular_velocity,
            angular_acceleration=self.physics.angular_acceleration,
            tps_actual=self.physics.tps_actual,
            tps_target=self.physics.tps_target,
            torque_base=factors.get("base_torque", 0),
            torque_effective=torque,
            horsepower=hp,
            volumetric_efficiency=factors.get("ve", 0),
            pumping_loss=factors.get("pumping_loss", 0),
            thermal_factor=factors.get("thermal_factor", 1.0),
            air_density_factor=factors.get("air_density_factor", 1.0),
            mechanical_efficiency=factors.get("mechanical_efficiency", 1.0),
            engine_temp_f=self.physics.engine_temp_f,
            iat_f=self.physics.iat_f,
            ambient_temp_f=self.config.ambient_temp_f,
            barometric_pressure_inhg=self.config.barometric_pressure_inhg,
            humidity_pct=self.config.humidity_pct,
            knock_detected=self.physics.knock_detected,
            knock_risk_score=factors.get("knock_risk", 0),
        )

    def set_profile(self, profile: EngineProfile):
        """Change the engine profile."""
        with self._lock:
            self.config.profile = profile
            self._precompute_curves()
            self._init_physics()

    def _handle_idle_state(self, dt: float, profile: EngineProfile):
        """Handle IDLE state behavior."""
        # Idle speed control (simulated ECU maintaining idle RPM)
        # Adjust throttle based on RPM error with proportional control
        rpm_error = self.physics.rpm - profile.idle_rpm

        # Proportional control: throttle based on RPM error direction and magnitude
        if rpm_error < -50:
            # RPM too low - add throttle proportionally
            self.physics.tps_target = 8.0
        elif rpm_error > 50:
            # RPM too high - close throttle immediately and force actual closed
            self.physics.tps_target = 0.0
            self.physics.tps_actual = 0.0  # Force immediate closure to prevent creep
        elif rpm_error > 0:
            # RPM slightly above idle - keep throttle closed to prevent creep
            self.physics.tps_target = 0.0
            # Force actual closed if it's still open to prevent gradual creep
            if self.physics.tps_actual > 0.5:
                self.physics.tps_actual = 0.0
        else:
            # RPM slightly below idle - minimal throttle to maintain idle
            # Use proportional control: more throttle the further below idle
            throttle_needed = max(
                0.0, min(2.0, abs(rpm_error) * 0.02)
            )  # 0-2% based on error
            self.physics.tps_target = throttle_needed

        self._update_throttle(dt)

        # Update physics (but at idle, we want minimal torque)
        torque, hp, factors = self._update_physics(dt)

        # Apply additional drag at idle to prevent runaway
        # Simulates dyno brake holding engine at idle
        if self.physics.rpm > profile.idle_rpm + 100:
            # Strong braking if RPM gets too high
            brake_factor = 1.0 - 0.1 * dt  # 10% per second braking
            self.physics.angular_velocity *= brake_factor
            self.physics.rpm = self._rad_s_to_rpm(self.physics.angular_velocity)

        # Add idle oscillation
        rpm_noise = random.gauss(0, 15)

        self.channels.rpm = self.physics.rpm + rpm_noise
        self.channels.tps_pct = self.physics.tps_actual
        self.channels.map_kpa = 30 + random.gauss(0, 2)
        self.channels.torque_ftlb = 0.0  # No load at idle
        self.channels.horsepower = 0.0
        self.channels.force_lbs = random.gauss(0, 2)
        self.channels.acceleration_g = random.gauss(0, 0.01)

        # Idle AFR (lean)
        target_afr = profile.target_afr_idle
        self.channels.afr_front = self._add_noise(target_afr, 1.5)
        self.channels.afr_rear = self._add_noise(target_afr, 1.5)

        self.channels.iat_f = self.physics.iat_f
        self.channels.vbatt = 13.6 + random.gauss(0, 0.1)

    def _handle_pull_state(self, dt: float, profile: EngineProfile):
        """Handle PULL state behavior."""
        # WOT acceleration - physics-based
        elapsed = time.time() - self._pull_start_time
        self._pull_elapsed_s += dt

        # Update throttle (realistic lag)
        self._update_throttle(dt)

        # If the operator chops throttle during an active pull, end the power-sweep immediately
        # and transition to DECEL (coastdown). This prevents the live HP trace from flatlining
        # for a few ticks while TPS is closed but we're still in the PULL handler.
        if (
            self._pull_elapsed_s > 0.5
            and self.physics.tps_target < 5.0
            and self.physics.tps_actual < 5.0
            and self.physics.rpm > profile.idle_rpm * 1.5
        ):
            self.state = SimState.DECEL
            self._pull_start_time = time.time()
            self.physics.tps_target = 0.0
            self.physics.tps_actual = 0.0
            if self._on_state_change:
                self._on_state_change(self.state)
            return

        # Get target AFR for knock detection
        target_afr = self._get_target_afr(self.physics.rpm, self.physics.tps_actual)

        # Calculate AFR based on ECU simulation (if enabled) or use default behavior
        if self.virtual_ecu is not None:
            # Virtual ECU mode: AFR based on VE table errors
            current_afr = self._calculate_simulated_afr(
                self.physics.rpm, self.channels.map_kpa, self.physics.tps_actual
            )
        else:
            # Default mode: Add systematic lean/rich regions for realism
            rpm_range = profile.redline_rpm - profile.idle_rpm
            if rpm_range > 0:
                rpm_pct = (self.physics.rpm - profile.idle_rpm) / rpm_range
            else:
                rpm_pct = 0.5  # Fallback if invalid profile

            # Lean spots in mid-range, rich at high RPM (typical before tune)
            if 0.3 < rpm_pct < 0.5:
                afr_error = 0.3  # Lean in mid-range
            elif rpm_pct > 0.7:
                afr_error = -0.4  # Rich at top
            else:
                afr_error = 0.0

            current_afr = target_afr + afr_error

        # Physics update with AFR for knock detection
        engine_torque, engine_hp, factors = self._update_physics(dt, current_afr)

        # Dyno-measured torque/HP are inferred from drum inertia (I * α), not directly from engine torque.
        # This matches how an inertia dyno derives power from drum acceleration.
        dyno_torque = float(factors.get("dyno_torque", engine_torque))
        dyno_hp = float(factors.get("dyno_hp", engine_hp))

        # Add realistic noise
        rpm_display = self._add_noise(self.physics.rpm, self.config.rpm_noise_pct)
        # When throttle closes, dyno-inferred power can go negative (engine braking / coast).
        # If we clamp negatives to 0, the UI appears to "spike then instantly drop to zero".
        # Instead, show positive magnitude as "loss power" so the trace remains continuous.
        if dyno_hp < 0.0:
            disp_tq = abs(dyno_torque)
            disp_hp = abs(dyno_hp)
        else:
            disp_tq = max(0.0, dyno_torque)
            disp_hp = max(0.0, dyno_hp)

        torque_display = self._add_noise(disp_tq, self.config.torque_noise_pct)
        hp_display = self._add_noise(disp_hp, self.config.torque_noise_pct)

        # Force calculation (dyno drum force)
        # F = τ / r (Torque / Drum Radius)
        # Using actual drum specs from DynoConfig (Dynoware RT-150)
        dyno_config = get_config().dyno
        drum_radius_ft = dyno_config.drum1.radius_ft

        if drum_radius_ft > 0:
            # Real calculation: Force = Torque / Radius
            force = dyno_torque / drum_radius_ft
        else:
            # Fallback to approximation if drum not configured
            force = dyno_torque * 2.5

        # MAP follows throttle, but also dips slightly at high RPM as VE drops (more realistic than a flat ~100kPa).
        # This also helps avoid a perfectly flat load trace in the UI.
        ve_now = factors.get("ve", 1.0)
        rpm_norm = (self.physics.rpm - profile.idle_rpm) / max(
            1.0, (profile.redline_rpm - profile.idle_rpm)
        )
        high_rpm_drop = 1.0 - 0.03 * max(0.0, min(1.0, rpm_norm))  # up to ~3% drop
        map_target = (
            (30.0 + (self.physics.tps_actual / 100.0) * 70.0)
            * (0.92 + 0.08 * max(0.0, min(1.0, ve_now)))
            * high_rpm_drop
        )
        self.channels.map_kpa = self._add_noise(map_target, 2)

        # Acceleration (from angular acceleration)
        # Convert rad/s² to g's (very rough approximation)
        accel_g = self.physics.angular_acceleration / 30.0

        self.channels.rpm = rpm_display
        self.channels.tps_pct = self.physics.tps_actual
        self.channels.torque_ftlb = torque_display
        self.channels.horsepower = hp_display
        self.channels.force_lbs = self._add_noise(force, self.config.torque_noise_pct)
        self.channels.acceleration_g = self._add_noise(accel_g, 10)

        # AFR during WOT
        # If using virtual ECU, front/rear can have different AFRs based on their VE tables
        if self.virtual_ecu is not None:
            # Front cylinder AFR (already calculated)
            self.channels.afr_front = current_afr

            # Rear cylinder AFR (calculate separately - V-twins often have different VE)
            actual_ve_rear = self._get_volumetric_efficiency(
                self.physics.rpm, self.physics.tps_actual
            )
            afr_rear = self.virtual_ecu.calculate_resulting_afr(
                self.physics.rpm, self.channels.map_kpa, actual_ve_rear, cylinder="rear"
            )
            # Add realistic sensor noise and clamp to sensor range
            afr_rear_with_noise = afr_rear + random.gauss(0, 0.05)
            self.channels.afr_rear = max(10.0, min(20.0, afr_rear_with_noise))
        else:
            # Default mode: Add noise to current AFR
            # Protect against division by zero if AFR is invalid
            if current_afr > 0.1:  # Sanity check
                noise_pct = self.config.afr_noise / current_afr * 100
            else:
                noise_pct = 10.0  # Fallback to 10% noise

            self.channels.afr_front = self._add_noise(current_afr, noise_pct)
            self.channels.afr_rear = self._add_noise(current_afr + 0.1, noise_pct)

        self.channels.iat_f = self.physics.iat_f
        self.channels.vbatt = 14.0 + random.gauss(0, 0.1)

        # Collect pull data
        self._pull_data.append(
            {
                "Engine RPM": self.physics.rpm,
                # Dyno-inferred values (what the UI/analysis expects for an inertia dyno)
                "Torque": dyno_torque,
                "Horsepower": dyno_hp,
                "Force": force,
                "AFR Meas F": self.channels.afr_front,
                "AFR Meas R": self.channels.afr_rear,
                "AFR Target": target_afr,
                "MAP kPa": self.channels.map_kpa,
                "TPS": self.physics.tps_actual,
                "IAT F": self.physics.iat_f,
                "timestamp": time.time(),
                "Knock": 1 if self.physics.knock_detected else 0,
                # Extra debug/telemetry fields (safe to ignore downstream)
                "Engine Torque": engine_torque,
                "Engine HP": engine_hp,
                "Alpha Net": float(factors.get("alpha_net", 0.0)),
            }
        )

        # Collect physics snapshot if enabled
        if self._collect_snapshots:
            snapshot = self._create_physics_snapshot(torque, hp, factors)
            self._physics_snapshots.append(snapshot)

        # Update progress based on RPM
        self._pull_progress = (self.physics.rpm - profile.idle_rpm) / (
            profile.redline_rpm - profile.idle_rpm
        )

        # Check if pull complete (reached redline)
        if self.physics.rpm >= profile.redline_rpm * 0.98:
            # Clamp RPM to redline to prevent overshoot
            self.physics.rpm = min(self.physics.rpm, profile.redline_rpm)
            self.physics.angular_velocity = self._rpm_to_rad_s(self.physics.rpm)

            self.state = SimState.DECEL
            self._pull_start_time = time.time()
            self.physics.tps_target = 0.0  # Close throttle
            self.physics.tps_actual = 0.0  # Force immediate closure for safety

            if self._on_state_change:
                self._on_state_change(self.state)

    def _handle_decel_state(self, dt: float, profile: EngineProfile):
        """Handle DECEL state behavior."""
        # Deceleration back to idle
        elapsed = time.time() - self._pull_start_time

        # Close throttle immediately (no lag during decel for safety)
        self.physics.tps_target = 0.0
        self.physics.tps_actual = 0.0  # Force immediate throttle closure

        # Capture ω at the start of the timestep so we can compute inertial decel power.
        omega_prev = float(self.physics.angular_velocity)

        # Physics with engine braking (throttle closed, so minimal torque)
        engine_torque, engine_hp, factors = self._update_physics(dt)

        # Additional engine braking for realistic deceleration
        # Apply stronger braking than drag alone to simulate engine compression braking
        brake_coeff = float(self.config.engine_brake_coefficient)
        self.physics.angular_velocity *= 1.0 - (brake_coeff * dt)
        self.physics.rpm = self._rad_s_to_rpm(self.physics.angular_velocity)

        # Clamp RPM to prevent going below idle or exceeding redline
        # This prevents any runaway acceleration during decel
        self.physics.rpm = max(
            profile.idle_rpm * 0.8, min(profile.redline_rpm, self.physics.rpm)
        )
        self.physics.angular_velocity = self._rpm_to_rad_s(self.physics.rpm)

        # Inertia-derived decel "power" (loss power). This avoids the live trace dropping to 0
        # instantly at the pull->decel transition while still representing drum inertia physics.
        omega_now = float(self.physics.angular_velocity)
        alpha_net = (omega_now - omega_prev) / max(dt, 1e-6)  # negative during decel
        scale = float(self.config.torque_to_angular_accel_scale) or 1.0
        dyno_torque = (float(self.physics.total_inertia) * alpha_net) / scale
        dyno_hp = dyno_torque * float(self.physics.rpm) / 5252.0

        # Report positive magnitude as "loss power" during coastdown (common dyno concept).
        loss_torque = abs(dyno_torque)
        loss_hp = abs(dyno_hp)

        self.channels.rpm = self._add_noise(self.physics.rpm, self.config.rpm_noise_pct)
        self.channels.tps_pct = self.physics.tps_actual
        self.channels.map_kpa = 30 + (self.physics.tps_actual / 100.0) * 70
        self.channels.torque_ftlb = self._add_noise(
            loss_torque, self.config.torque_noise_pct
        )
        self.channels.horsepower = self._add_noise(
            loss_hp, self.config.torque_noise_pct
        )

        dyno_config = get_config().dyno
        drum_radius_ft = dyno_config.drum1.radius_ft
        if drum_radius_ft > 0:
            force = loss_torque / drum_radius_ft
        else:
            force = loss_torque * 2.5
        self.channels.force_lbs = self._add_noise(force, self.config.torque_noise_pct)
        self.channels.acceleration_g = self._add_noise(-0.3, 20)

        # AFR goes lean during decel fuel cut
        if self.physics.rpm > profile.idle_rpm * 1.5:
            self.channels.afr_front = self._add_noise(18.0, 5)
            self.channels.afr_rear = self._add_noise(18.0, 5)
        else:
            self.channels.afr_front = self._add_noise(14.7, 2)
            self.channels.afr_rear = self._add_noise(14.7, 2)

        self.channels.iat_f = self.physics.iat_f
        self.channels.vbatt = 13.8 + random.gauss(0, 0.1)

        # Check if back to idle (allow more time for gradual decel)
        # Transition when RPM drops to 120% of idle (was 110%)
        if self.physics.rpm <= profile.idle_rpm * 1.2:
            self.state = SimState.COOLDOWN
            self._pull_start_time = time.time()

            # Notify pull complete with data
            if self._on_pull_complete:
                self._on_pull_complete(list(self._pull_data))

            if self._on_state_change:
                self._on_state_change(self.state)

    def _handle_cooldown_state(
        self, dt: float, profile: EngineProfile, last_auto_pull: float
    ) -> float:
        """Handle COOLDOWN state behavior. Returns updated last_auto_pull time."""
        # Brief pause - idle behavior (similar to idle state to prevent throttle creep)
        elapsed = time.time() - self._pull_start_time

        # Use same idle control logic to prevent throttle creep
        rpm_error = self.physics.rpm - profile.idle_rpm
        if rpm_error > 0:
            # RPM above idle - keep throttle closed to prevent creep
            self.physics.tps_target = 0.0
            if self.physics.tps_actual > 0.5:
                self.physics.tps_actual = 0.0  # Force immediate closure
        else:
            # RPM at or below idle - minimal throttle
            self.physics.tps_target = max(0.0, min(3.0, abs(rpm_error) * 0.03))

        self._update_throttle(dt)
        torque, hp, factors = self._update_physics(dt)

        self.channels.rpm = self.physics.rpm + random.gauss(0, 20)
        self.channels.tps_pct = self.physics.tps_actual
        self.channels.map_kpa = 30 + random.gauss(0, 2)
        self.channels.torque_ftlb = 0.0
        self.channels.horsepower = 0.0
        self.channels.force_lbs = random.gauss(0, 2)
        self.channels.acceleration_g = random.gauss(0, 0.01)
        self.channels.afr_front = self._add_noise(14.7, 1)
        self.channels.afr_rear = self._add_noise(14.7, 1)
        self.channels.iat_f = self.physics.iat_f
        self.channels.vbatt = 13.6 + random.gauss(0, 0.1)

        if elapsed >= 2.0:  # 2 second cooldown
            self.state = SimState.IDLE
            new_last_auto_pull = time.time()

            if self._on_state_change:
                self._on_state_change(self.state)

            return new_last_auto_pull

        return last_auto_pull

    def _run_loop(self):
        """Main simulation loop - dispatches to state handlers."""
        profile = self.config.profile
        dt = 1.0 / self.config.update_rate_hz
        last_auto_pull = time.time()

        while not self._stop_event.is_set():
            loop_start = time.time()

            with self._lock:
                state = self.state

                if state == SimState.IDLE:
                    self._handle_idle_state(dt, profile)

                    # Auto-pull check
                    if self.config.auto_pull:
                        if (
                            time.time() - last_auto_pull
                            > self.config.auto_pull_interval_sec
                        ):
                            self.state = SimState.PULL
                            self._pull_start_time = time.time()
                            self._pull_progress = 0.0
                            self._pull_data = []
                            self._physics_snapshots = []
                            self.physics.tps_target = 100.0
                            last_auto_pull = time.time()

                elif state == SimState.PULL:
                    self._handle_pull_state(dt, profile)

                elif state == SimState.DECEL:
                    self._handle_decel_state(dt, profile)

                elif state == SimState.COOLDOWN:
                    last_auto_pull = self._handle_cooldown_state(
                        dt, profile, last_auto_pull
                    )

            # Sleep to maintain update rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, dt - elapsed)
            time.sleep(sleep_time)


# Global simulator instance
_simulator: DynoSimulator | None = None
_simulator_lock = threading.Lock()


def get_simulator() -> DynoSimulator:
    """Get or create the global simulator instance."""
    global _simulator
    with _simulator_lock:
        if _simulator is None:
            _simulator = DynoSimulator()
        return _simulator


def reset_simulator(
    config: SimulatorConfig | None = None, virtual_ecu=None
) -> DynoSimulator:
    """Reset the simulator with new config and optional Virtual ECU."""
    global _simulator
    with _simulator_lock:
        if _simulator is not None:
            try:
                # Stop the existing simulator with a short timeout
                _simulator._stop_event.set()
                if _simulator._thread and _simulator._thread.is_alive():
                    # Don't wait - the thread will finish on its own
                    pass
            except Exception:
                # Ignore errors during stop
                pass
        _simulator = DynoSimulator(config, virtual_ecu=virtual_ecu)
        return _simulator


__all__ = [
    "DynoSimulator",
    "SimulatorConfig",
    "SimState",
    "EngineProfile",
    "SimulatedChannels",
    "PhysicsState",
    "PhysicsSnapshot",
    "get_simulator",
    "reset_simulator",
]
