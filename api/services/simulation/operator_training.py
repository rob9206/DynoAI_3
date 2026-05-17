"""
Operator Training Simulator - Virtual dyno operator training system.

Extends the base dyno simulator with:
- Load control (eddy current brake simulation)
- RPM hold modes (PID-based steady-state control)
- Safety scenario training (overrev, knock, thermal, lean)
- Configurable dyno types (inertia, inertia+load, load holding)

This module provides training capabilities for dyno operators without
risking damage to real equipment or engines.
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional

from api.services.simulation.dyno_simulator import (
    DynoLoadMode,
    DynoSimulator,
    EddyBrakeConfig,
    EngineProfile,
    PhysicsState,
    SimState,
    SimulatedChannels,
    SimulatorConfig,
    get_simulator,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Dyno Type Configuration
# =============================================================================


class DynoType(Enum):
    """Types of dynamometer configurations."""

    INERTIA = "inertia"  # Pure inertia (current behavior)
    INERTIA_LOAD = "inertia_load"  # Inertia + eddy brake (Dynojet 424x)
    LOAD_HOLDING = "load_holding"  # Full load control (Mustang/SuperFlow)


@dataclass
class DynoTypeConfig:
    """Configuration for different dyno types."""

    dyno_type: DynoType = DynoType.INERTIA
    max_brake_torque: float = 800.0  # ft-lb max absorption
    brake_response_rate: float = 100.0  # ft-lb/second transition rate
    eddy_rpm_factor: float = 0.8  # RPM scaling for eddy brake effectiveness


# =============================================================================
# PID Controller for RPM Hold Mode
# =============================================================================


class RPMHoldController:
    """
    PID controller for maintaining target RPM in load-holding dyno mode.

    The operator controls throttle, and the PID adjusts brake load
    to maintain a steady RPM for calibration work.
    """

    def __init__(
        self,
        kp: float = 0.8,
        ki: float = 0.05,
        kd: float = 0.15,
        max_integral: float = 100.0,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_integral = max_integral

        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.time()

    def update(self, target_rpm: float, actual_rpm: float, dt: float) -> float:
        """
        Calculate load adjustment to maintain target RPM.

        Args:
            target_rpm: Desired RPM setpoint
            actual_rpm: Current engine RPM
            dt: Time delta in seconds

        Returns:
            Load adjustment value (-100 to +100)
        """
        error = target_rpm - actual_rpm

        # Integral with anti-windup
        self.integral += error * dt
        self.integral = max(-self.max_integral, min(self.max_integral, self.integral))

        # Derivative
        derivative = (error - self.last_error) / max(dt, 0.001)
        self.last_error = error

        # PID output
        output = self.kp * error + self.ki * self.integral + self.kd * derivative

        return max(-100.0, min(100.0, output))

    def reset(self):
        """Reset controller state."""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.time()


# =============================================================================
# Safety Alert System
# =============================================================================


@dataclass
class SafetyAlert:
    """Represents a safety alert during training."""

    type: str  # "overrev", "knock", "thermal", "lean"
    severity: str  # "warning", "critical"
    message: str
    timestamp: float
    value: float  # The problematic reading
    acknowledged: bool = False


@dataclass
class SafetyLimits:
    """Configurable safety thresholds."""

    rpm_warning: float = 6200.0
    rpm_critical: float = 6800.0
    afr_lean_warning: float = 13.5
    afr_lean_critical: float = 14.5
    egt_front_warning: float = 1350.0  # °F
    egt_front_critical: float = 1450.0
    egt_rear_warning: float = 1400.0
    egt_rear_critical: float = 1500.0
    knock_threshold: float = 3.0  # severity units
    oil_temp_warning: float = 250.0
    oil_temp_critical: float = 280.0


class SafetyMonitor:
    """
    Monitors simulator state for safety conditions and generates alerts.

    Tracks operator response times and calculates training scores.
    """

    def __init__(self, limits: SafetyLimits | None = None):
        self.limits = limits or SafetyLimits()
        self.alerts: List[SafetyAlert] = []
        self.response_timers: dict[str, float] = {}
        self.safety_score: float = 100.0
        self.total_alerts: int = 0
        self.acknowledged_alerts: int = 0

    def check(self, state: "TrainingPhysicsState") -> List[SafetyAlert]:
        """
        Check current state for safety conditions.

        Args:
            state: Current training physics state

        Returns:
            List of active safety alerts
        """
        self.alerts = []

        # Over-rev check
        if state.rpm >= self.limits.rpm_critical:
            self._add_alert(
                "overrev",
                "critical",
                f"RPM {int(state.rpm)} - CRITICAL OVER-REV!",
                state.rpm,
            )
        elif state.rpm >= self.limits.rpm_warning:
            self._add_alert(
                "overrev",
                "warning",
                f"RPM {int(state.rpm)} - approaching redline",
                state.rpm,
            )

        # Lean condition check
        if state.afr >= self.limits.afr_lean_critical:
            self._add_alert(
                "lean",
                "critical",
                f"AFR {state.afr:.1f} - DANGEROUSLY LEAN!",
                state.afr,
            )
        elif state.afr >= self.limits.afr_lean_warning:
            self._add_alert(
                "lean",
                "warning",
                f"AFR {state.afr:.1f} - approaching lean limit",
                state.afr,
            )

        # EGT checks (front cylinder)
        if state.egt_front >= self.limits.egt_front_critical:
            self._add_alert(
                "thermal",
                "critical",
                f"Front EGT {int(state.egt_front)}°F - CRITICAL TEMP!",
                state.egt_front,
            )
        elif state.egt_front >= self.limits.egt_front_warning:
            self._add_alert(
                "thermal",
                "warning",
                f"Front EGT {int(state.egt_front)}°F - high temp",
                state.egt_front,
            )

        # EGT checks (rear cylinder)
        if state.egt_rear >= self.limits.egt_rear_critical:
            self._add_alert(
                "thermal",
                "critical",
                f"Rear EGT {int(state.egt_rear)}°F - CRITICAL TEMP!",
                state.egt_rear,
            )
        elif state.egt_rear >= self.limits.egt_rear_warning:
            self._add_alert(
                "thermal",
                "warning",
                f"Rear EGT {int(state.egt_rear)}°F - high temp",
                state.egt_rear,
            )

        # Knock detection
        if state.knock_level >= self.limits.knock_threshold:
            self._add_alert(
                "knock",
                "critical",
                f"Knock detected - {state.knock_level:.1f} severity",
                state.knock_level,
            )

        # Oil temperature
        if state.oil_temp >= self.limits.oil_temp_critical:
            self._add_alert(
                "oil_temp",
                "critical",
                f"Oil temp {int(state.oil_temp)}°F - CRITICAL!",
                state.oil_temp,
            )
        elif state.oil_temp >= self.limits.oil_temp_warning:
            self._add_alert(
                "oil_temp",
                "warning",
                f"Oil temp {int(state.oil_temp)}°F - high",
                state.oil_temp,
            )

        return self.alerts

    def _add_alert(self, alert_type: str, severity: str, message: str, value: float):
        """Add a new alert and start response timer if critical."""
        alert = SafetyAlert(
            type=alert_type,
            severity=severity,
            message=message,
            timestamp=time.time(),
            value=value,
        )
        self.alerts.append(alert)
        self.total_alerts += 1

        # Start response timer for critical alerts
        if severity == "critical" and alert_type not in self.response_timers:
            self.response_timers[alert_type] = time.time()

    def acknowledge_alert(self, alert_type: str):
        """
        Record operator acknowledgment/response to an alert.
        Updates safety score based on response time.
        """
        if alert_type in self.response_timers:
            response_time = time.time() - self.response_timers[alert_type]
            self.acknowledged_alerts += 1

            # Score based on response time
            if response_time < 1.0:
                self.safety_score = min(100.0, self.safety_score + 2.0)
            elif response_time < 2.0:
                self.safety_score = max(0.0, self.safety_score - 5.0)
            elif response_time < 5.0:
                self.safety_score = max(0.0, self.safety_score - 15.0)
            else:
                self.safety_score = max(0.0, self.safety_score - 25.0)

            del self.response_timers[alert_type]

    def reset(self):
        """Reset all monitoring state."""
        self.alerts = []
        self.response_timers = {}
        self.safety_score = 100.0
        self.total_alerts = 0
        self.acknowledged_alerts = 0


# =============================================================================
# Training Physics State Extension
# =============================================================================


@dataclass
class TrainingPhysicsState:
    """
    Extended physics state for operator training.

    Adds load control, EGT simulation, and detailed thermal modeling.
    """

    # Base physics (mirrors PhysicsState)
    rpm: float = 900.0
    tps_actual: float = 0.0
    tps_target: float = 0.0

    # Power output
    engine_torque: float = 0.0
    horsepower: float = 0.0

    # Load control
    load_target: float = 0.0  # 0-100% brake demand
    brake_torque: float = 0.0  # Calculated brake torque (ft-lb)
    current_load: float = 0.0  # Actual load (with lag)

    # RPM hold mode
    rpm_hold_active: bool = False
    rpm_hold_target: float = 3500.0

    # AFR
    afr: float = 14.0
    afr_front: float = 14.0
    afr_rear: float = 14.0

    # Thermal (extended with EGT)
    egt_front: float = 650.0  # Exhaust gas temp front cylinder
    egt_rear: float = 680.0  # Exhaust gas temp rear cylinder
    oil_temp: float = 180.0
    coolant_temp: float = 185.0
    engine_temp: float = 180.0
    iat: float = 85.0

    # Knock detection
    knock_level: float = 0.0
    knock_detected: bool = False

    # Calculated values
    map_kpa: float = 30.0
    acceleration_g: float = 0.0


# =============================================================================
# Training Scenario System
# =============================================================================


class TrainingScenario(Enum):
    """Available training scenarios."""

    NONE = "none"
    OVERREV = "overrev"  # Sudden load drop causing RPM spike
    LEAN = "lean"  # Fuel delivery problem
    THERMAL = "thermal"  # Extended WOT thermal buildup
    KNOCK = "knock"  # Detonation condition
    LOAD_SHED = "load_shed"  # Brake failure simulation


@dataclass
class ScenarioConfig:
    """Configuration for training scenarios."""

    scenario: TrainingScenario = TrainingScenario.NONE
    start_time: float = 0.0
    duration: float = 10.0  # Scenario active duration
    intensity: float = 1.0  # 0.0 to 1.0 scaling


# =============================================================================
# Operator Training Simulator
# =============================================================================


class OperatorTrainingSimulator:
    """
    Extended dyno simulator for operator training.

    Wraps the base DynoSimulator and adds:
    - Load control with eddy current brake model
    - RPM hold mode with PID control
    - Safety monitoring and alerts
    - Training scenarios for practice
    - Detailed thermal modeling
    """

    def __init__(
        self,
        base_simulator: DynoSimulator | None = None,
        dyno_config: DynoTypeConfig | None = None,
    ):
        self.base_sim = base_simulator or get_simulator()
        self.dyno_config = dyno_config or DynoTypeConfig()

        # Training state
        self.training_state = TrainingPhysicsState()
        self.pid_controller = RPMHoldController()
        self.safety_monitor = SafetyMonitor()

        # Scenario
        self.active_scenario = ScenarioConfig()

        # Threading
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_alert: Callable[[SafetyAlert], None] | None = None

        self._apply_dyno_config()

    def _apply_dyno_config(self):
        """Apply dyno type configuration to the base simulator."""
        if self.dyno_config.dyno_type == DynoType.INERTIA:
            self.base_sim.set_load_mode(DynoLoadMode.INERTIA)
            self.training_state.load_target = 0.0
            self.training_state.current_load = 0.0
            self.training_state.brake_torque = 0.0
            self.training_state.rpm_hold_active = False
            return

        self.base_sim.set_eddy_brake_config(
            EddyBrakeConfig(
                max_brake_torque=self.dyno_config.max_brake_torque,
                brake_response_rate=self.dyno_config.brake_response_rate,
                eddy_rpm_factor=self.dyno_config.eddy_rpm_factor,
            )
        )
        self.base_sim.set_load_mode(DynoLoadMode.EDDY_BRAKE)
        if self.dyno_config.dyno_type == DynoType.LOAD_HOLDING:
            self.base_sim.set_rpm_hold(True, self.training_state.rpm_hold_target)
            self.training_state.rpm_hold_active = True
        else:
            self.base_sim.set_rpm_hold(False)
            self.training_state.rpm_hold_active = False

    def start(self):
        """Start the training simulator."""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        # Start base simulator if not running
        if self.base_sim.state == SimState.STOPPED:
            self.base_sim.start()

        # Start training loop
        self._thread = threading.Thread(target=self._training_loop, daemon=True)
        self._thread.start()

        logger.info("Operator Training Simulator started")

    def stop(self):
        """Stop the training simulator."""
        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("Operator Training Simulator stopped")

    def reset(self):
        """Reset training state."""
        with self._lock:
            self.training_state = TrainingPhysicsState()
            self.pid_controller.reset()
            self.safety_monitor.reset()
            self.active_scenario = ScenarioConfig()

    def set_dyno_type(self, dyno_type: DynoType):
        """Change dyno type configuration."""
        with self._lock:
            self.dyno_config.dyno_type = dyno_type
            self._apply_dyno_config()

    def set_throttle(self, tps: float):
        """Set throttle position (0-100%)."""
        with self._lock:
            self.training_state.tps_target = max(0.0, min(100.0, tps))
            # Also update base simulator
            self.base_sim.physics.tps_target = self.training_state.tps_target

    def set_load_target(self, load: float):
        """Set brake load target (0-100%)."""
        if self.dyno_config.dyno_type == DynoType.INERTIA:
            return  # No load control on inertia dyno

        with self._lock:
            self.training_state.load_target = max(0.0, min(100.0, load))
            self.base_sim.set_load_target(self.training_state.load_target)

    def set_rpm_hold(self, active: bool, target_rpm: float | None = None):
        """Enable/disable RPM hold mode."""
        if self.dyno_config.dyno_type != DynoType.LOAD_HOLDING:
            return  # Only available on load-holding dyno

        with self._lock:
            self.training_state.rpm_hold_active = active
            if target_rpm is not None:
                self.training_state.rpm_hold_target = max(
                    1500.0, min(6500.0, target_rpm)
                )
            self.base_sim.set_rpm_hold(active, self.training_state.rpm_hold_target)
            if not active:
                self.pid_controller.reset()

    def trigger_scenario(self, scenario: TrainingScenario, duration: float = 10.0):
        """Trigger a training scenario."""
        with self._lock:
            self.active_scenario = ScenarioConfig(
                scenario=scenario,
                start_time=time.time(),
                duration=duration,
                intensity=1.0,
            )
            logger.info(f"Training scenario triggered: {scenario.value}")

    def acknowledge_alert(self, alert_type: str):
        """Acknowledge a safety alert."""
        with self._lock:
            self.safety_monitor.acknowledge_alert(alert_type)

    def get_state(self) -> dict[str, Any]:
        """Get current training state as dictionary."""
        with self._lock:
            alerts = self.safety_monitor.alerts
            return {
                "rpm": self.training_state.rpm,
                "throttle": self.training_state.tps_actual,
                "load_target": self.training_state.load_target,
                "current_load": self.training_state.current_load,
                "brake_torque": self.training_state.brake_torque,
                "engine_torque": self.training_state.engine_torque,
                "horsepower": self.training_state.horsepower,
                "afr": self.training_state.afr,
                "afr_front": self.training_state.afr_front,
                "afr_rear": self.training_state.afr_rear,
                "egt_front": self.training_state.egt_front,
                "egt_rear": self.training_state.egt_rear,
                "oil_temp": self.training_state.oil_temp,
                "coolant_temp": self.training_state.coolant_temp,
                "knock_level": self.training_state.knock_level,
                "map_kpa": self.training_state.map_kpa,
                "rpm_hold_active": self.training_state.rpm_hold_active,
                "rpm_hold_target": self.training_state.rpm_hold_target,
                "dyno_type": self.dyno_config.dyno_type.value,
                "alerts": [
                    {
                        "type": a.type,
                        "severity": a.severity,
                        "message": a.message,
                        "value": a.value,
                    }
                    for a in alerts
                ],
                "safety_score": self.safety_monitor.safety_score,
                "active_scenario": self.active_scenario.scenario.value,
            }

    def _training_loop(self):
        """Main training simulation loop."""
        dt = 0.02  # 50Hz update rate

        while not self._stop_event.is_set():
            loop_start = time.time()

            with self._lock:
                self._update_physics(dt)
                self._update_thermal(dt)
                self._apply_scenario_effects(dt)

                # Safety monitoring
                alerts = self.safety_monitor.check(self.training_state)

                # Notify on new critical alerts
                for alert in alerts:
                    if alert.severity == "critical" and self._on_alert:
                        self._on_alert(alert)

            # Maintain loop rate
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, dt - elapsed)
            time.sleep(sleep_time)

    def _update_physics(self, dt: float):
        """Update physics state from base simulator and add load control."""
        # Sync from base simulator
        base_channels = self.base_sim.channels
        base_physics = self.base_sim.physics

        self.training_state.rpm = base_channels.rpm
        self.training_state.tps_actual = base_physics.tps_actual
        self.training_state.engine_torque = base_channels.torque_ftlb
        self.training_state.horsepower = base_channels.horsepower
        self.training_state.afr_front = base_channels.afr_front
        self.training_state.afr_rear = base_channels.afr_rear
        self.training_state.afr = (base_channels.afr_front + base_channels.afr_rear) / 2
        self.training_state.map_kpa = base_channels.map_kpa
        self.training_state.iat = base_channels.iat_f

        # Sync load/brake data from base simulator
        self._calculate_brake_torque(dt)

        # RPM hold handled by base simulator

    def _calculate_brake_torque(self, dt: float):
        """Sync brake/load values from base simulator."""
        load_state = self.base_sim.get_load_state()
        self.training_state.load_target = float(load_state.get("load_target", 0.0))
        self.training_state.current_load = float(load_state.get("current_load", 0.0))
        self.training_state.brake_torque = float(load_state.get("brake_torque", 0.0))

    def _update_thermal(self, dt: float):
        """Update thermal state (EGT, oil temp, etc.)."""
        tps = self.training_state.tps_actual
        rpm = self.training_state.rpm

        # EGT model - rises with throttle and RPM
        target_egt_base = 600 + (tps / 100.0) * 700 + (rpm / 7000.0) * 200

        # Front cylinder (slightly cooler due to airflow)
        target_egt_front = target_egt_base
        # Rear cylinder (runs hotter)
        target_egt_rear = target_egt_base + 50

        # Thermal lag (heat up faster than cool down)
        heat_rate = 0.02
        cool_rate = 0.005

        if self.training_state.egt_front < target_egt_front:
            self.training_state.egt_front += (
                target_egt_front - self.training_state.egt_front
            ) * heat_rate
        else:
            self.training_state.egt_front += (
                target_egt_front - self.training_state.egt_front
            ) * cool_rate

        if self.training_state.egt_rear < target_egt_rear:
            self.training_state.egt_rear += (
                target_egt_rear - self.training_state.egt_rear
            ) * heat_rate
        else:
            self.training_state.egt_rear += (
                target_egt_rear - self.training_state.egt_rear
            ) * cool_rate

        # Oil temperature
        target_oil = 180 + (tps / 100.0) * 40 + (rpm / 7000.0) * 20
        self.training_state.oil_temp += (
            target_oil - self.training_state.oil_temp
        ) * 0.001

        # Coolant temperature
        target_coolant = 185 + (tps / 100.0) * 15
        self.training_state.coolant_temp += (
            target_coolant - self.training_state.coolant_temp
        ) * 0.002

        # Knock level calculation
        self._calculate_knock()

    def _calculate_knock(self):
        """Calculate knock risk based on conditions."""
        knock_risk = 0.0
        afr = self.training_state.afr
        rpm = self.training_state.rpm
        tps = self.training_state.tps_actual

        # Lean condition increases knock risk
        if afr > 13.5:
            knock_risk += (afr - 13.5) * 2.0

        # High load + high RPM
        if rpm > 4500 and tps > 80:
            knock_risk += 0.5

        # Add noise
        knock_risk += (random.random() - 0.5) * 0.3

        self.training_state.knock_level = max(0.0, knock_risk)
        self.training_state.knock_detected = knock_risk >= 3.0

    def _apply_scenario_effects(self, dt: float):
        """Apply effects from active training scenario."""
        scenario = self.active_scenario

        # Check if scenario is active
        if scenario.scenario == TrainingScenario.NONE:
            return

        elapsed = time.time() - scenario.start_time
        if elapsed > scenario.duration:
            self.active_scenario = ScenarioConfig()  # Scenario complete
            return

        # Apply scenario-specific effects
        if scenario.scenario == TrainingScenario.OVERREV:
            # Sudden load drop causing RPM spike
            if elapsed < 0.5 and self.training_state.rpm > 5000:
                self.training_state.load_target = 0.0
                self.training_state.current_load *= 0.5

        elif scenario.scenario == TrainingScenario.LEAN:
            # AFR goes lean at high throttle
            if self.training_state.tps_actual > 80:
                self.training_state.afr += 1.5 * scenario.intensity
                self.training_state.afr_front += 1.5 * scenario.intensity
                self.training_state.afr_rear += 1.5 * scenario.intensity

        elif scenario.scenario == TrainingScenario.THERMAL:
            # EGT rises faster
            if self.training_state.tps_actual > 60:
                self.training_state.egt_front += 5.0 * scenario.intensity
                self.training_state.egt_rear += 6.0 * scenario.intensity

        elif scenario.scenario == TrainingScenario.KNOCK:
            # Knock appears at moderate throttle
            if self.training_state.tps_actual > 70 and self.training_state.rpm > 3000:
                self.training_state.knock_level += 4.0 * scenario.intensity

        elif scenario.scenario == TrainingScenario.LOAD_SHED:
            # Brake failure - load drops suddenly
            self.training_state.load_target = 0.0
            self.training_state.current_load *= 0.9


# =============================================================================
# Module-level singleton
# =============================================================================

_training_simulator: OperatorTrainingSimulator | None = None
_training_lock = threading.Lock()


def get_training_simulator() -> OperatorTrainingSimulator:
    """Get or create the global training simulator instance."""
    global _training_simulator
    with _training_lock:
        if _training_simulator is None:
            _training_simulator = OperatorTrainingSimulator()
        return _training_simulator


def reset_training_simulator(
    dyno_config: DynoTypeConfig | None = None,
) -> OperatorTrainingSimulator:
    """Reset the training simulator with new configuration."""
    global _training_simulator
    with _training_lock:
        if _training_simulator is not None:
            _training_simulator.stop()
        _training_simulator = OperatorTrainingSimulator(dyno_config=dyno_config)
        return _training_simulator


__all__ = [
    "OperatorTrainingSimulator",
    "DynoType",
    "DynoTypeConfig",
    "RPMHoldController",
    "SafetyMonitor",
    "SafetyAlert",
    "SafetyLimits",
    "TrainingPhysicsState",
    "TrainingScenario",
    "ScenarioConfig",
    "get_training_simulator",
    "reset_training_simulator",
]
