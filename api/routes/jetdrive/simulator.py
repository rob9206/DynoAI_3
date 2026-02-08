"""
JetDrive Auto-Tune – Dyno Simulator Routes.

Sub-blueprint for:
- /simulator/start
- /simulator/stop
- /simulator/status
- /simulator/pull
- /simulator/throttle
- /simulator/pull-data
- /simulator/save-pull
- /simulator/profiles
"""

from __future__ import annotations

import csv
from datetime import datetime

from flask import Blueprint, jsonify, request

from ._shared import (
    _is_simulator_active,
    _set_simulator_active,
    get_project_root,
    logger,
    sanitize_run_id,
)

simulator_bp = Blueprint("jetdrive_simulator", __name__)


@simulator_bp.route("/simulator/start", methods=["POST"])
def start_simulator():
    """Start the dyno simulator for testing without hardware."""
    try:
        from api.services.simulation.dyno_simulator import (
            EngineProfile,
            SimulatorConfig,
            reset_simulator,
        )

        data = request.get_json() or {}

        profile_name = data.get("profile", "m8_114")
        profiles = {
            "m8_114": EngineProfile.m8_114,
            "m8_131": EngineProfile.m8_131,
            "twin_cam_103": EngineProfile.twin_cam_103,
            "sportbike_600": EngineProfile.sportbike_600,
        }

        profile_factory = profiles.get(profile_name)
        if not profile_factory:
            return jsonify({"error": f"Unknown profile: {profile_name}"}), 400

        profile = profile_factory()

        config = SimulatorConfig(
            profile=profile,
            auto_pull=data.get("auto_pull", False),
            auto_pull_interval_sec=data.get("auto_pull_interval", 15.0),
        )

        virtual_ecu = None
        ecu_config = data.get("virtual_ecu")
        if ecu_config and ecu_config.get("enabled", False):
            from api.services.simulation.virtual_ecu import (
                VirtualECU,
                create_afr_target_table,
                create_baseline_ve_table,
                create_intentionally_wrong_ve_table,
            )

            baseline_ve = create_baseline_ve_table(peak_ve=0.85, peak_rpm=4000)

            scenario = ecu_config.get("scenario", "perfect")
            if scenario == "perfect":
                ve_front = baseline_ve
                ve_rear = baseline_ve
            elif scenario == "lean":
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=-10.0, error_pct_std=5.0, seed=42
                )
                ve_rear = ve_front
            elif scenario == "rich":
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=10.0, error_pct_std=5.0, seed=42
                )
                ve_rear = ve_front
            elif scenario == "custom":
                ve_error = ecu_config.get("ve_error_pct", -10.0)
                ve_std = ecu_config.get("ve_error_std", 5.0)
                ve_front = create_intentionally_wrong_ve_table(
                    baseline_ve, error_pct_mean=ve_error, error_pct_std=ve_std, seed=42
                )
                ve_rear = ve_front
            else:
                ve_front = baseline_ve
                ve_rear = baseline_ve

            cylinder_balance = ecu_config.get("cylinder_balance", "same")
            if cylinder_balance == "front_rich":
                ve_front = ve_front * 1.05
            elif cylinder_balance == "rear_rich":
                ve_rear = ve_rear * 1.05

            afr_table = create_afr_target_table(cruise_afr=14.0, wot_afr=12.5)

            virtual_ecu = VirtualECU(
                ve_table_front=ve_front,
                ve_table_rear=ve_rear,
                afr_target_table=afr_table,
                barometric_pressure_inhg=ecu_config.get(
                    "barometric_pressure_inhg", 29.92
                ),
                ambient_temp_f=ecu_config.get("ambient_temp_f", 75.0),
            )

            logger.info(
                f"Virtual ECU enabled: scenario={scenario}, ve_error={ecu_config.get('ve_error_pct', 0)}"
            )

        sim = reset_simulator(config, virtual_ecu=virtual_ecu)
        sim.start()
        _set_simulator_active(True)

        return jsonify(
            {
                "success": True,
                "virtual_ecu_enabled": virtual_ecu is not None,
                "status": "started",
                "profile": {
                    "name": profile.name,
                    "family": profile.family,
                    "displacement_ci": profile.displacement_ci,
                    "idle_rpm": profile.idle_rpm,
                    "redline_rpm": profile.redline_rpm,
                    "max_hp": profile.max_hp,
                    "max_tq": profile.max_tq,
                },
                "auto_pull": config.auto_pull,
            }
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to start simulator: {error_msg}", exc_info=True)
        return (
            jsonify({"success": False, "error": f"Failed to start simulator: {error_msg}"}),
            500,
        )


@simulator_bp.route("/simulator/stop", methods=["POST"])
def stop_simulator():
    """Stop the dyno simulator."""
    from api.services.simulation.dyno_simulator import get_simulator

    sim = get_simulator()
    sim.stop()
    _set_simulator_active(False)

    return jsonify({"success": True, "status": "stopped"})


@simulator_bp.route("/simulator/status", methods=["GET"])
def get_simulator_status():
    """Get current simulator status."""
    if not _is_simulator_active():
        return jsonify({"active": False, "state": "stopped"})

    from api.services.simulation.dyno_simulator import get_simulator

    try:
        sim = get_simulator()
        state = sim.get_state()
        channels = sim.get_channels()
    except Exception as e:
        logger.error(f"Error getting simulator status: {e}")
        return jsonify({"active": True, "state": "idle", "error": str(e)})

    rpm = channels.get("Digital RPM 1", {}).get("value", 0)
    hp = channels.get("Horsepower", {}).get("value", 0)
    tq = channels.get("Torque", {}).get("value", 0)
    afr = channels.get("Air/Fuel Ratio 1", {}).get("value", 0)
    tps = channels.get("TPS", {}).get("value", 0)

    return jsonify(
        {
            "active": True,
            "state": state.value,
            "profile": sim.config.profile.name,
            "current": {
                "rpm": round(rpm, 0),
                "horsepower": round(hp, 1),
                "torque": round(tq, 1),
                "afr": round(afr, 2),
                "tps": round(tps, 1),
            },
        }
    )


@simulator_bp.route("/simulator/pull", methods=["POST"])
def trigger_pull():
    """Manually trigger a WOT pull in the simulator."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.simulation.dyno_simulator import SimState, get_simulator

    sim = get_simulator()
    current_state = sim.get_state()

    if current_state != SimState.IDLE:
        return (
            jsonify(
                {
                    "error": f"Cannot start pull in state: {current_state.value}",
                    "current_state": current_state.value,
                }
            ),
            400,
        )

    sim.trigger_pull()

    return jsonify({"success": True, "status": "pull_started", "state": "pull"})


@simulator_bp.route("/simulator/throttle", methods=["POST"])
def set_simulator_throttle():
    """Set simulator throttle target (TPS %) for manual operator control."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    data = request.get_json() or {}
    try:
        tps = float(data.get("tps"))
    except Exception:
        return jsonify({"error": "Missing or invalid 'tps' (0-100)"}), 400

    if not (0.0 <= tps <= 100.0):
        return jsonify({"error": "'tps' must be between 0 and 100"}), 400

    from api.services.simulation.dyno_simulator import get_simulator

    sim = get_simulator()
    sim.physics.tps_target = tps

    return jsonify({"success": True, "tps_target": tps})


@simulator_bp.route("/simulator/pull-data", methods=["GET"])
def get_pull_data():
    """Get data from the last completed pull."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.simulation.dyno_simulator import get_simulator

    sim = get_simulator()
    sim_state = sim.get_state()
    data = sim.get_pull_data()

    logger.debug(
        f"Pull data request: state={sim_state.value}, data_points={len(data) if data else 0}"
    )

    if not data or len(data) == 0:
        return jsonify(
            {
                "success": True,
                "has_data": False,
                "data": [],
                "state": sim_state.value,
            }
        )

    peak_hp = max((d.get("Horsepower", 0) for d in data), default=0)
    peak_tq = max((d.get("Torque", 0) for d in data), default=0)

    hp_peak_rpm = next(
        (d["Engine RPM"] for d in data if d.get("Horsepower", 0) == peak_hp), 0
    )
    tq_peak_rpm = next(
        (d["Engine RPM"] for d in data if d.get("Torque", 0) == peak_tq), 0
    )

    return jsonify(
        {
            "success": True,
            "has_data": True,
            "points": len(data),
            "peak_hp": round(peak_hp, 1),
            "hp_peak_rpm": round(hp_peak_rpm, 0),
            "peak_tq": round(peak_tq, 1),
            "tq_peak_rpm": round(tq_peak_rpm, 0),
            "state": sim_state.value,
            "data": data,
        }
    )


@simulator_bp.route("/simulator/save-pull", methods=["POST"])
def save_simulator_pull():
    """Save the last simulator pull data to a CSV file."""
    if not _is_simulator_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.simulation.dyno_simulator import get_simulator

    sim = get_simulator()
    data = sim.get_pull_data()

    if not data:
        return jsonify({"error": "No pull data available"}), 400

    request_data = request.get_json() or {}
    try:
        run_id = sanitize_run_id(
            request_data.get("run_id")
            or f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    project_root = get_project_root()
    uploads_dir = project_root / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    csv_filename = f"{run_id}.csv"
    csv_path = uploads_dir / csv_filename

    try:
        with open(csv_path, "w", newline="") as f:
            if data:
                fieldnames = [
                    "timestamp_ms",
                    "RPM",
                    "Torque",
                    "Horsepower",
                    "AFR",
                    "MAP_kPa",
                    "TPS",
                    "IAT",
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for i, row in enumerate(data):
                    afr_avg = (
                        row.get("AFR Meas F", 14.7) + row.get("AFR Meas R", 14.7)
                    ) / 2

                    writer.writerow(
                        {
                            "timestamp_ms": i * 50,
                            "RPM": row.get("Engine RPM", 0),
                            "Torque": row.get("Torque", 0),
                            "Horsepower": row.get("Horsepower", 0),
                            "AFR": afr_avg,
                            "MAP_kPa": row.get("MAP kPa", 0),
                            "TPS": row.get("TPS", 0),
                            "IAT": row.get("IAT F", 85),
                        }
                    )

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "csv_path": str(csv_path),
                "points": len(data),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to save CSV: {str(e)}"}), 500


@simulator_bp.route("/simulator/profiles", methods=["GET"])
def get_profiles():
    """Get available engine profiles for simulation."""
    from api.services.simulation.dyno_simulator import EngineProfile

    profiles = {
        "m8_114": EngineProfile.m8_114(),
        "m8_131": EngineProfile.m8_131(),
        "twin_cam_103": EngineProfile.twin_cam_103(),
        "sportbike_600": EngineProfile.sportbike_600(),
    }

    result = []
    for key, profile in profiles.items():
        result.append(
            {
                "id": key,
                "name": profile.name,
                "family": profile.family,
                "displacement_ci": profile.displacement_ci,
                "idle_rpm": profile.idle_rpm,
                "redline_rpm": profile.redline_rpm,
                "max_hp": profile.max_hp,
                "hp_peak_rpm": profile.hp_peak_rpm,
                "max_tq": profile.max_tq,
                "tq_peak_rpm": profile.tq_peak_rpm,
            }
        )

    return jsonify({"profiles": result})
