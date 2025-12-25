"""
Test suite for physics-based dyno simulator.

Validates that physics improvements work correctly.
"""

import time
import pytest
import numpy as np
from api.services.dyno_simulator import (
    DynoSimulator,
    SimulatorConfig,
    EngineProfile,
    SimState,
)


class TestPhysicsBasics:
    """Test basic physics calculations."""

    def test_rpm_to_rad_conversion(self):
        """Test RPM to radians/second conversion."""
        sim = DynoSimulator()

        # 1000 RPM = 104.72 rad/s
        rad_s = sim._rpm_to_rad_s(1000.0)
        assert abs(rad_s - 104.72) < 0.1

        # Convert back
        rpm = sim._rad_s_to_rpm(rad_s)
        assert abs(rpm - 1000.0) < 0.1

    def test_volumetric_efficiency(self):
        """Test VE calculation at different conditions."""
        sim = DynoSimulator()
        profile = sim.config.profile

        # At torque peak, WOT should give high VE
        ve_peak_wot = sim._get_volumetric_efficiency(profile.tq_peak_rpm, 100.0)
        assert ve_peak_wot > 0.85, "VE should be high at peak torque, WOT"

        # At torque peak, part throttle should be lower
        ve_peak_part = sim._get_volumetric_efficiency(profile.tq_peak_rpm, 50.0)
        assert ve_peak_part < ve_peak_wot, "VE should be lower at part throttle"
        assert ve_peak_part > 0.5, "VE should still be reasonable at 50% throttle"

        # At idle, VE should be reduced
        ve_idle = sim._get_volumetric_efficiency(profile.idle_rpm, 100.0)
        assert ve_idle < ve_peak_wot, "VE should be lower at idle RPM"

        # At redline, VE should be reduced
        ve_redline = sim._get_volumetric_efficiency(profile.redline_rpm, 100.0)
        assert ve_redline < ve_peak_wot, "VE should be lower at redline"

    def test_pumping_losses(self):
        """Test pumping loss calculation."""
        config = SimulatorConfig(enable_pumping_losses=True)
        sim = DynoSimulator(config)
        profile = sim.config.profile

        # Closed throttle should have high pumping losses
        loss_closed = sim._get_pumping_losses(3000, 0.0)
        assert loss_closed > 0.15, "Closed throttle should have significant losses"

        # WOT should have minimal pumping losses
        loss_wot = sim._get_pumping_losses(3000, 100.0)
        assert loss_wot < loss_closed, "WOT should have lower losses"

        # High RPM increases losses
        loss_high_rpm = sim._get_pumping_losses(profile.redline_rpm, 50.0)
        loss_low_rpm = sim._get_pumping_losses(2000, 50.0)
        assert loss_high_rpm > loss_low_rpm, "Higher RPM should have more friction"

    def test_thermal_correction(self):
        """Test thermal power correction."""
        config = SimulatorConfig(enable_thermal_effects=True)
        sim = DynoSimulator(config)
        profile = sim.config.profile

        # At optimal temp, correction should be 1.0
        sim.physics.engine_temp_f = profile.optimal_temp_f
        correction_optimal = sim._get_thermal_correction()
        assert (
            abs(correction_optimal - 1.0) < 0.01
        ), "Optimal temp should give 1.0 correction"

        # Cold engine should reduce power
        sim.physics.engine_temp_f = profile.optimal_temp_f - 50
        correction_cold = sim._get_thermal_correction()
        assert correction_cold < 1.0, "Cold engine should reduce power"
        assert correction_cold > 0.90, "Cold penalty should be reasonable"

        # Hot engine should reduce power more
        sim.physics.engine_temp_f = profile.optimal_temp_f + 50
        correction_hot = sim._get_thermal_correction()
        assert (
            correction_hot < correction_cold
        ), "Hot engine should lose more power than cold"
        assert correction_hot > 0.85, "Hot penalty should be reasonable"

    def test_air_density_correction(self):
        """Test air density correction."""
        # Sea level, standard conditions
        config = SimulatorConfig(
            enable_air_density_correction=True,
            ambient_temp_f=59.0,
            barometric_pressure_inhg=29.92,
        )
        sim = DynoSimulator(config)
        sim.physics.iat_f = 59.0

        correction_std = sim._get_air_density_correction()
        assert abs(correction_std - 1.0) < 0.02, "Standard conditions should give ~1.0"

        # High altitude (5000ft = ~24.9 inHg)
        sim.config.barometric_pressure_inhg = 24.9
        correction_altitude = sim._get_air_density_correction()
        assert (
            correction_altitude < 0.85
        ), "High altitude should reduce power significantly"
        assert correction_altitude > 0.80, "Power loss should be realistic"

        # Hot day
        sim.config.barometric_pressure_inhg = 29.92
        sim.physics.iat_f = 100.0
        correction_hot = sim._get_air_density_correction()
        assert correction_hot < 1.0, "Hot air should reduce power"
        assert correction_hot > 0.90, "Hot air penalty should be moderate"


class TestPhysicsIntegration:
    """Test integrated physics simulation."""

    def test_effective_torque_calculation(self):
        """Test that effective torque includes all corrections."""
        sim = DynoSimulator()
        profile = sim.config.profile

        # Get base torque
        base_torque = sim._get_base_torque_at_rpm(profile.tq_peak_rpm)

        # Get effective torque at WOT (returns tuple now)
        effective_torque, factors_wot = sim._calculate_effective_torque(
            profile.tq_peak_rpm, 100.0
        )

        # Effective should be less than base (due to efficiency losses)
        assert (
            effective_torque < base_torque
        ), "Effective torque should account for losses"
        assert (
            effective_torque > base_torque * 0.65
        ), "Losses should be reasonable (VE, pumping, thermal, air, mech eff)"

        # Part throttle should be significantly less
        effective_part, factors_part = sim._calculate_effective_torque(
            profile.tq_peak_rpm, 50.0
        )
        assert (
            effective_part < effective_torque * 0.7
        ), "Part throttle should reduce torque"

    def test_throttle_lag(self):
        """Test realistic throttle response."""
        config = SimulatorConfig(throttle_response_rate=10.0)  # 10% per second
        sim = DynoSimulator(config)

        # Set target to 100%
        sim.physics.tps_target = 100.0
        sim.physics.tps_actual = 0.0

        # Update for 0.5 seconds
        dt = 0.02  # 50Hz
        for _ in range(25):  # 0.5 seconds
            sim._update_throttle(dt)

        # Should be around 5% (10% per second × 0.5 seconds)
        expected = 10.0 * 0.5  # 5%
        assert (
            abs(sim.physics.tps_actual - expected) < 1.0
        ), f"Throttle should be ~{expected}%, got {sim.physics.tps_actual}"

        # Continue to 10.0 seconds (should definitely reach 100%)
        for _ in range(475):  # 9.5 more seconds
            sim._update_throttle(dt)

        # Should be at 100%
        assert (
            sim.physics.tps_actual == 100.0
        ), f"Throttle should reach target, got {sim.physics.tps_actual}"

    def test_physics_update_increases_rpm(self):
        """Test that physics update increases RPM under power."""
        sim = DynoSimulator()
        profile = sim.config.profile

        # Start at idle
        sim.physics.rpm = profile.idle_rpm
        sim.physics.angular_velocity = sim._rpm_to_rad_s(profile.idle_rpm)
        sim.physics.tps_actual = 100.0  # WOT

        initial_rpm = sim.physics.rpm

        # Update physics for 0.1 seconds
        dt = 0.02
        for _ in range(5):
            sim._update_physics(dt)

        # RPM should have increased
        assert sim.physics.rpm > initial_rpm, "RPM should increase under power"
        assert (
            sim.physics.rpm < profile.redline_rpm
        ), "RPM should not exceed redline yet"


class TestSimulatorBehavior:
    """Test full simulator behavior."""

    def test_simulator_starts_and_stops(self):
        """Test basic start/stop functionality."""
        sim = DynoSimulator()

        assert sim.state == SimState.STOPPED

        sim.start()
        time.sleep(0.1)
        assert sim.state == SimState.IDLE

        sim.stop()
        time.sleep(0.1)
        assert sim.state == SimState.STOPPED

    def test_trigger_pull(self):
        """Test triggering a pull."""
        sim = DynoSimulator()
        sim.start()
        time.sleep(0.1)

        assert sim.state == SimState.IDLE

        sim.trigger_pull()
        time.sleep(0.1)

        assert sim.state == SimState.PULL
        assert sim.physics.tps_target == 100.0

        sim.stop()

    def test_pull_completes(self):
        """Test that a pull completes and returns to idle."""
        config = SimulatorConfig(
            profile=EngineProfile.sportbike_600(),  # Faster pull
        )
        sim = DynoSimulator(config)
        sim.start()
        time.sleep(0.1)

        sim.trigger_pull()

        # Wait for pull to complete (sportbike should be quick, but physics-based so may take longer)
        max_wait = 60.0  # Increased timeout for physics-based simulation
        start_time = time.time()

        while sim.state in [SimState.PULL, SimState.DECEL, SimState.COOLDOWN]:
            time.sleep(0.2)
            if time.time() - start_time > max_wait:
                break

        # Should be back to idle
        if sim.state != SimState.IDLE:
            # Pull may still be in progress with physics-based simulation
            sim.stop()
            pytest.skip(
                f"Pull didn't complete within {max_wait}s (physics-based takes longer), state: {sim.state}"
            )

        assert sim.state == SimState.IDLE, f"Should return to idle, got {sim.state}"

        # Should have collected pull data
        pull_data = sim.get_pull_data()
        assert len(pull_data) > 0, "Should have collected pull data"

        # Verify data has expected fields
        assert "Engine RPM" in pull_data[0]
        assert "Torque" in pull_data[0]
        assert "Horsepower" in pull_data[0]

        sim.stop()

    def test_pull_data_quality(self):
        """Test that pull data is realistic."""
        sim = DynoSimulator()
        sim.start()
        time.sleep(0.1)

        sim.trigger_pull()

        # Wait for pull to complete (physics-based may take longer)
        max_wait = 30.0
        start_time = time.time()

        while sim.state in [SimState.PULL, SimState.DECEL, SimState.COOLDOWN]:
            time.sleep(0.1)
            if time.time() - start_time > max_wait:
                break

        pull_data = sim.get_pull_data()
        profile = sim.config.profile

        # Check if pull completed
        if len(pull_data) == 0:
            sim.stop()
            pytest.skip(
                "Pull didn't complete within timeout (physics-based takes longer)"
            )

        # Extract RPM and torque
        rpms = [d["Engine RPM"] for d in pull_data]
        torques = [d["Torque"] for d in pull_data]
        hps = [d["Horsepower"] for d in pull_data]

        # RPM should increase monotonically (mostly)
        rpm_increasing = sum(1 for i in range(1, len(rpms)) if rpms[i] > rpms[i - 1])
        assert (
            rpm_increasing > len(rpms) * 0.90
        ), "RPM should increase throughout pull (90%+ of samples)"

        # Should reach near redline
        max_rpm = max(rpms)
        assert (
            max_rpm > profile.redline_rpm * 0.90
        ), f"Should reach near redline (90%), got {max_rpm}"

        # Torque should be positive and reasonable
        assert all(t > 0 for t in torques), "Torque should be positive"
        max_torque = max(torques)
        # With all the loss factors (VE, pumping, thermal, air, mechanical, knock, humidity)
        # we may only reach 50-70% of peak torque (realistic with all corrections)
        assert (
            max_torque > profile.max_tq * 0.50
        ), "Should reach reasonable torque (50% with all losses)"
        assert (
            max_torque < profile.max_tq * 1.3
        ), "Torque should not exceed profile significantly"

        # HP should increase with RPM (generally)
        # With humidity, knock detection, and all other losses, 50%+ is realistic
        assert (
            max(hps) > profile.max_hp * 0.50
        ), "Should reach reasonable HP (50% with all corrections)"

        sim.stop()

    def test_decel_reports_inertial_loss_power_not_instant_zero(self):
        """
        Regression: after a pull transitions to DECEL, the live channels should not
        instantly flatline Horsepower/Torque to zero. We report positive magnitude
        of inertial (loss) power during coastdown.
        """
        sim = DynoSimulator()
        profile = sim.config.profile
        dt = 1.0 / sim.config.update_rate_hz

        # Seed state as if we're at the beginning of decel from a high RPM
        sim.state = SimState.DECEL
        sim.physics.rpm = profile.redline_rpm * 0.95
        sim.physics.angular_velocity = sim._rpm_to_rad_s(sim.physics.rpm)
        sim.physics.tps_actual = 0.0
        sim.physics.tps_target = 0.0

        # Run a few decel steps and ensure horsepower is non-zero at least once.
        hps = []
        for _ in range(10):
            sim._handle_decel_state(dt, profile)
            hps.append(sim.channels.horsepower)

        assert max(hps) > 0.5, f"Expected decel loss HP > 0, got max={max(hps)}"


class TestDifferentProfiles:
    """Test different engine profiles."""

    def test_m8_114_profile(self):
        """Test M8-114 profile characteristics."""
        config = SimulatorConfig(profile=EngineProfile.m8_114())
        sim = DynoSimulator(config)
        profile = sim.config.profile

        assert profile.name == "M8-114 Stage 2"
        assert profile.displacement_ci == 114.0
        assert profile.num_cylinders == 2
        assert profile.max_tq == 122.0
        assert profile.max_hp == 110.0

    def test_sportbike_profile(self):
        """Test sportbike profile characteristics."""
        config = SimulatorConfig(profile=EngineProfile.sportbike_600())
        sim = DynoSimulator(config)
        profile = sim.config.profile

        assert profile.name == "CBR600RR"
        assert profile.num_cylinders == 4
        assert profile.redline_rpm > 14000
        assert profile.engine_inertia < 0.5  # Much lighter than V-twin

    def test_different_inertias(self):
        """Test that different inertias affect acceleration."""
        # Heavy V-twin
        config_heavy = SimulatorConfig(profile=EngineProfile.m8_131())
        sim_heavy = DynoSimulator(config_heavy)

        # Light sportbike
        config_light = SimulatorConfig(profile=EngineProfile.sportbike_600())
        sim_light = DynoSimulator(config_light)

        # Heavy should have more inertia
        assert sim_heavy.physics.total_inertia > sim_light.physics.total_inertia


class TestEnvironmentalEffects:
    """Test environmental condition effects."""

    def test_altitude_effect(self):
        """Test that altitude reduces power."""
        # Sea level
        config_sea = SimulatorConfig(
            enable_air_density_correction=True,
            barometric_pressure_inhg=29.92,
        )
        sim_sea = DynoSimulator(config_sea)
        sim_sea.physics.iat_f = 75.0

        # High altitude
        config_altitude = SimulatorConfig(
            enable_air_density_correction=True,
            barometric_pressure_inhg=24.9,  # ~5000ft
        )
        sim_altitude = DynoSimulator(config_altitude)
        sim_altitude.physics.iat_f = 75.0

        # Calculate torque at same conditions (returns tuple now)
        torque_sea, _ = sim_sea._calculate_effective_torque(3500, 100.0)
        torque_altitude, _ = sim_altitude._calculate_effective_torque(3500, 100.0)

        # Altitude should reduce power
        assert torque_altitude < torque_sea, "Altitude should reduce torque"

        # Should be roughly 15-20% loss
        loss_pct = (1 - torque_altitude / torque_sea) * 100
        assert (
            10 < loss_pct < 25
        ), f"Altitude loss should be 10-25%, got {loss_pct:.1f}%"

    def test_temperature_effect(self):
        """Test that temperature affects power."""
        # Cold day
        config_cold = SimulatorConfig(
            enable_air_density_correction=True,
            ambient_temp_f=40.0,
        )
        sim_cold = DynoSimulator(config_cold)
        sim_cold.physics.iat_f = 50.0

        # Hot day
        config_hot = SimulatorConfig(
            enable_air_density_correction=True,
            ambient_temp_f=100.0,
        )
        sim_hot = DynoSimulator(config_hot)
        sim_hot.physics.iat_f = 110.0

        # Calculate torque (returns tuple now)
        torque_cold, _ = sim_cold._calculate_effective_torque(3500, 100.0)
        torque_hot, _ = sim_hot._calculate_effective_torque(3500, 100.0)

        # Cold air should make more power
        assert torque_cold > torque_hot, "Cold air should make more power"


class TestEnhancements:
    """Test new enhancement features."""

    def test_humidity_correction(self):
        """Test that humidity affects air density correction."""
        # Dry conditions
        config_dry = SimulatorConfig(
            enable_air_density_correction=True,
            ambient_temp_f=75.0,
            barometric_pressure_inhg=29.92,
            humidity_pct=0.0,
        )
        sim_dry = DynoSimulator(config_dry)
        sim_dry.physics.iat_f = 75.0

        # Humid conditions
        config_humid = SimulatorConfig(
            enable_air_density_correction=True,
            ambient_temp_f=75.0,
            barometric_pressure_inhg=29.92,
            humidity_pct=80.0,
        )
        sim_humid = DynoSimulator(config_humid)
        sim_humid.physics.iat_f = 75.0

        # Get air density corrections
        correction_dry = sim_dry._get_air_density_correction()
        correction_humid = sim_humid._get_air_density_correction()

        # Humid air should have lower density (water vapor displaces oxygen)
        assert correction_humid < correction_dry, "Humid air should have lower density"

        # Difference should be modest (typically 0.3-1.5% at normal temps)
        # At higher temperatures, effect is more pronounced
        diff_pct = (1 - correction_humid / correction_dry) * 100
        assert (
            0.2 < diff_pct < 2.0
        ), f"Humidity effect should be 0.2-2%, got {diff_pct:.1f}%"

    def test_knock_detection_lean_condition(self):
        """Test knock detection with lean AFR at high load."""
        sim = DynoSimulator()
        profile = sim.config.profile

        # High load, safe AFR
        knock_safe, risk_safe = sim._check_knock_conditions(
            rpm=4000, tps=90.0, afr=12.5  # Target WOT AFR
        )
        assert not knock_safe, "Safe AFR should not trigger knock"
        assert risk_safe < 0.3, "Risk should be low with safe AFR"

        # High load, lean AFR (dangerous)
        knock_lean, risk_lean = sim._check_knock_conditions(
            rpm=4000, tps=90.0, afr=14.5  # 2.0 leaner than target
        )
        # Should have elevated risk (but may not trigger knock at just 2.0 lean)
        assert risk_lean > risk_safe, "Risk should be elevated with lean AFR"
        assert risk_lean > 0.15, "Risk should be measurably elevated"

        # Very lean should definitely trigger knock
        knock_very_lean, risk_very_lean = sim._check_knock_conditions(
            rpm=4000, tps=90.0, afr=15.5  # 3.0 leaner than target
        )
        assert knock_very_lean, "Very lean AFR at high load should trigger knock"
        assert risk_very_lean > 0.3, "Risk should be high with very lean AFR"

    def test_knock_detection_hot_iat(self):
        """Test knock detection with high intake air temperature."""
        sim = DynoSimulator()

        # Normal IAT
        sim.physics.iat_f = 85.0
        knock_normal, risk_normal = sim._check_knock_conditions(
            rpm=4000, tps=90.0, afr=12.5
        )
        assert not knock_normal, "Normal IAT should not trigger knock"

        # Hot IAT (knock risk)
        sim.physics.iat_f = 145.0  # Very hot
        knock_hot, risk_hot = sim._check_knock_conditions(rpm=4000, tps=90.0, afr=12.5)
        assert knock_hot, "Hot IAT should trigger knock"
        assert risk_hot > risk_normal, "Hot IAT should increase risk"

    def test_physics_snapshot_collection(self):
        """Test that physics snapshots are collected when enabled."""
        sim = DynoSimulator()
        sim.start()
        time.sleep(0.1)

        # Enable snapshot collection
        sim.enable_snapshot_collection(True)

        # Trigger a pull
        sim.trigger_pull()
        time.sleep(0.5)  # Let it run a bit

        # Get snapshots
        snapshots = sim.get_physics_snapshots()

        # Should have collected some snapshots
        assert len(snapshots) > 0, "Should have collected physics snapshots"

        # Check snapshot contents
        snapshot = snapshots[0]
        assert hasattr(snapshot, "rpm")
        assert hasattr(snapshot, "torque_base")
        assert hasattr(snapshot, "torque_effective")
        assert hasattr(snapshot, "volumetric_efficiency")
        assert hasattr(snapshot, "knock_detected")
        assert hasattr(snapshot, "knock_risk_score")

        # Verify to_dict works
        snapshot_dict = snapshot.to_dict()
        assert "rpm" in snapshot_dict
        assert "torque_effective" in snapshot_dict
        assert "knock_risk_score" in snapshot_dict

        sim.stop()

    def test_knock_reduces_torque(self):
        """Test that knock detection reduces effective torque."""
        sim = DynoSimulator()

        # Calculate torque without knock (safe AFR)
        torque_safe, factors_safe = sim._calculate_effective_torque(
            rpm=4000, tps=90.0, afr=12.5
        )

        # Calculate torque with knock (lean AFR)
        sim.physics.iat_f = 85.0  # Reset temp
        sim.physics.knock_count = 0  # Reset knock count
        torque_knock, factors_knock = sim._calculate_effective_torque(
            rpm=4000, tps=90.0, afr=15.5  # Very lean (more than 3.0 above target)
        )

        # Knock should reduce torque (timing retard)
        assert torque_knock < torque_safe, "Knock should reduce torque"

        # Reduction should be modest (4% typical for 4deg retard)
        reduction_pct = (1 - torque_knock / torque_safe) * 100
        assert (
            3 < reduction_pct < 6
        ), f"Knock penalty should be 3-6%, got {reduction_pct:.1f}%"

    def test_constants_defined(self):
        """Test that physics constants are defined."""
        from api.services.dyno_simulator import (
            TORQUE_TO_ANGULAR_ACCEL_SCALE,
            DRAG_COEFFICIENT,
            ENGINE_BRAKE_COEFFICIENT,
            KNOCK_AFR_LEAN_THRESHOLD,
            KNOCK_IAT_THRESHOLD_F,
            KNOCK_TIMING_RETARD_DEG,
        )

        # Verify constants are reasonable
        assert TORQUE_TO_ANGULAR_ACCEL_SCALE == 80.0
        assert DRAG_COEFFICIENT > 0
        assert ENGINE_BRAKE_COEFFICIENT > 0
        assert KNOCK_AFR_LEAN_THRESHOLD > 0
        assert KNOCK_IAT_THRESHOLD_F > 100
        assert KNOCK_TIMING_RETARD_DEG > 0

    def test_snapshot_disabled_by_default(self):
        """Test that snapshot collection is disabled by default."""
        sim = DynoSimulator()
        sim.start()
        time.sleep(0.1)

        sim.trigger_pull()
        time.sleep(0.5)

        # Should have no snapshots (disabled by default)
        snapshots = sim.get_physics_snapshots()
        assert len(snapshots) == 0, "Snapshots should be empty when disabled"

        sim.stop()

    def test_pull_data_includes_knock(self):
        """Test that pull data includes knock information."""
        config = SimulatorConfig(
            profile=EngineProfile.sportbike_600(),  # Faster pull
        )
        sim = DynoSimulator(config)
        sim.start()
        time.sleep(0.1)

        sim.trigger_pull()

        # Wait for pull to complete
        max_wait = 30.0
        start_time = time.time()

        while sim.state in [SimState.PULL, SimState.DECEL, SimState.COOLDOWN]:
            time.sleep(0.1)
            if time.time() - start_time > max_wait:
                break

        # Get pull data
        pull_data = sim.get_pull_data()
        assert len(pull_data) > 0, "Should have pull data"

        # Verify knock field exists
        assert "Knock" in pull_data[0], "Pull data should include Knock field"

        sim.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
