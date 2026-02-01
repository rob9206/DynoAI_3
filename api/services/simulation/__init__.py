"""
Simulation services for DynoAI.

Includes:
- DynoSimulator: Physics-based dyno simulation
- OperatorTrainingSimulator: Virtual operator training system
"""

from .dyno_simulator import (
    DynoSimulator,
    SimulatorConfig,
    SimState,
    EngineProfile,
    PhysicsState,
    SimulatedChannels,
    get_simulator,
    reset_simulator,
)

from .operator_training import (
    OperatorTrainingSimulator,
    DynoType,
    DynoTypeConfig,
    RPMHoldController,
    SafetyMonitor,
    SafetyAlert,
    SafetyLimits,
    TrainingPhysicsState,
    TrainingScenario,
    ScenarioConfig,
    get_training_simulator,
    reset_training_simulator,
)

__all__ = [
    # Base simulator
    "DynoSimulator",
    "SimulatorConfig",
    "SimState",
    "EngineProfile",
    "PhysicsState",
    "SimulatedChannels",
    "get_simulator",
    "reset_simulator",
    # Training simulator
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
