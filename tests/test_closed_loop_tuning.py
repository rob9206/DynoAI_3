"""
Tests for closed-loop tuning orchestrator.

Quick tests to verify the system works without running full iterations.
"""

import numpy as np
import pytest

from api.services.dyno_simulator import EngineProfile
from api.services.virtual_tuning_session import (
    TuningSessionConfig,
    TuningStatus,
    VirtualTuningOrchestrator,
)


class TestTuningOrchestrator:
    """Tests for VirtualTuningOrchestrator."""

    def test_create_session(self):
        """Test session creation."""
        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="lean",
            max_iterations=5,
        )

        orchestrator = VirtualTuningOrchestrator()
        session = orchestrator.create_session(config)

        assert session is not None
        assert session.session_id.startswith("tune_")
        assert session.status == TuningStatus.INITIALIZING
        assert session.current_iteration == 0
        assert session.baseline_ve is not None
        assert session.current_ve_front is not None
        assert session.current_ve_rear is not None

    def test_session_scenarios(self):
        """Test different VE scenarios."""
        orchestrator = VirtualTuningOrchestrator()

        # Test each scenario
        scenarios = ["perfect", "lean", "rich", "custom"]

        for scenario in scenarios:
            config = TuningSessionConfig(
                engine_profile=EngineProfile.m8_114(),
                base_ve_scenario=scenario,
                base_ve_error_pct=-15.0,  # For custom
                max_iterations=3,
            )

            session = orchestrator.create_session(config)

            assert session.current_ve_front is not None
            assert session.current_ve_rear is not None
            assert session.baseline_ve is not None

            # Check that VE tables are different for non-perfect scenarios
            if scenario != "perfect":
                assert not np.allclose(session.current_ve_front, session.baseline_ve)

    def test_session_to_dict(self):
        """Test session serialization."""
        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="lean",
            max_iterations=5,
        )

        orchestrator = VirtualTuningOrchestrator()
        session = orchestrator.create_session(config)

        data = session.to_dict()

        assert "session_id" in data
        assert "status" in data
        assert "current_iteration" in data
        assert "max_iterations" in data
        assert "iterations" in data
        assert isinstance(data["iterations"], list)

    def test_get_session(self):
        """Test session retrieval."""
        orchestrator = VirtualTuningOrchestrator()

        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="lean",
        )

        session = orchestrator.create_session(config)
        session_id = session.session_id

        # Retrieve session
        retrieved = orchestrator.get_session(session_id)

        assert retrieved is not None
        assert retrieved.session_id == session_id

    def test_stop_session(self):
        """Test stopping a session."""
        orchestrator = VirtualTuningOrchestrator()

        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="lean",
        )

        session = orchestrator.create_session(config)
        session.status = TuningStatus.RUNNING

        # Stop session
        stopped = orchestrator.stop_session(session.session_id)

        assert stopped is True
        assert session.status == TuningStatus.STOPPED
        assert session.end_time is not None


class TestTuningSessionConfig:
    """Tests for TuningSessionConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = TuningSessionConfig(engine_profile=EngineProfile.m8_114())

        assert config.base_ve_scenario == "lean"
        assert config.max_iterations == 10
        assert config.convergence_threshold_afr == 0.3
        assert config.max_correction_per_iteration_pct == 15.0
        assert config.oscillation_detection_enabled is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = TuningSessionConfig(
            engine_profile=EngineProfile.m8_114(),
            base_ve_scenario="custom",
            base_ve_error_pct=-20.0,
            max_iterations=15,
            convergence_threshold_afr=0.2,
        )

        assert config.base_ve_scenario == "custom"
        assert config.base_ve_error_pct == -20.0
        assert config.max_iterations == 15
        assert config.convergence_threshold_afr == 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
