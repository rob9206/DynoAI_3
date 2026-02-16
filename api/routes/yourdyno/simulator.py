"""
YourDyno – Mock TCP Bridge Simulator Routes.

Reuses the JetDrive DynoSimulator physics engine but emits data over a
local TCP socket using the exact same JSON-lines wire format produced by
the real C# DynoAIBridge plugin.  The normal YourDynoClient then connects
to this mock bridge and parses everything through the standard pipeline,
exercising the full chain end-to-end:

    DynoSimulator → MockBridge(:9877) → YourDynoClient → _shared.py → /live/*

Routes mirror the JetDrive simulator blueprint for frontend compatibility.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from datetime import datetime

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

simulator_bp = Blueprint("yourdyno_simulator", __name__)

MOCK_BRIDGE_HOST = os.getenv("YOURDYNO_BRIDGE_HOST", "127.0.0.1")
MOCK_BRIDGE_PORT = int(os.getenv("YOURDYNO_BRIDGE_PORT", "9877"))
FEEDER_HZ = 20  # 20 Hz = 50 ms per sample, matches real bridge rate

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_mock_bridge: _MockTcpBridge | None = None
_bridge_lock = threading.Lock()
_sim_active = False


def _is_sim_active() -> bool:
    return _sim_active


def _set_sim_active(v: bool) -> None:
    global _sim_active
    _sim_active = v


# ---------------------------------------------------------------------------
# Mock TCP Bridge
# ---------------------------------------------------------------------------


class _MockTcpBridge:
    """
    Tiny TCP server on localhost that emits JSON-lines identical to the
    real C# DynoAIBridge ``ChannelMapper`` output.

    On client connect it sends a ``{"type":"hello",...}`` handshake, then
    a background feeder thread polls ``DynoSimulator.channels`` and writes
    newline-delimited JSON to every connected client.
    """

    def __init__(self, host: str = MOCK_BRIDGE_HOST, port: int = MOCK_BRIDGE_PORT):
        self.host = host
        self.port = port
        self._server_sock: socket.socket | None = None
        self._clients: list[socket.socket] = []
        self._clients_lock = threading.Lock()
        self._accept_thread: threading.Thread | None = None
        self._feeder_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._start_time = 0.0

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._stop_event.clear()
        self._start_time = time.time()

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.settimeout(1.0)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(4)

        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="yd-mock-accept", daemon=True
        )
        self._accept_thread.start()

        self._feeder_thread = threading.Thread(
            target=self._feeder_loop, name="yd-mock-feeder", daemon=True
        )
        self._feeder_thread.start()

        logger.info("YourDyno mock bridge listening on %s:%d", self.host, self.port)

    def stop(self) -> None:
        self._stop_event.set()

        # Close server socket to unblock accept()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        # Close all client sockets
        with self._clients_lock:
            for sock in self._clients:
                try:
                    sock.close()
                except Exception:
                    pass
            self._clients.clear()

        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=2.0)
        if self._feeder_thread and self._feeder_thread.is_alive():
            self._feeder_thread.join(timeout=2.0)

        logger.info("YourDyno mock bridge stopped")

    # -- accept loop -------------------------------------------------------

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                client_sock, addr = self._server_sock.accept()  # type: ignore[union-attr]
                logger.info("Mock bridge client connected from %s", addr)
                # Send hello handshake (same shape as real bridge)
                hello = json.dumps({
                    "type": "hello",
                    "plugin": "DynoAIBridge-Simulator",
                    "version": "1.0.0",
                    "dyno_type": "Simulator",
                }) + "\n"
                try:
                    client_sock.sendall(hello.encode("utf-8"))
                except Exception:
                    client_sock.close()
                    continue
                with self._clients_lock:
                    self._clients.append(client_sock)
                    logger.info("Mock bridge client added, total=%d", len(self._clients))
            except socket.timeout:
                continue
            except OSError:
                break  # Server socket closed

    # -- feeder loop -------------------------------------------------------

    def _feeder_loop(self) -> None:
        interval = 1.0 / FEEDER_HZ
        # Wait briefly for simulator physics to initialise
        time.sleep(0.3)
        logger.info("Mock bridge feeder started, interval=%.3fs", interval)
        iteration = 0
        while not self._stop_event.is_set():
            loop_start = time.time()
            try:
                line = self._build_sample_line()
                if line:
                    with self._clients_lock:
                        n_clients = len(self._clients)
                    if iteration < 3:
                        logger.debug(
                            "Feeder iter %d: %d bytes, %d clients",
                            iteration, len(line), n_clients,
                        )
                    self._broadcast(line)
            except Exception as exc:
                logger.error("Mock bridge feeder error: %s", exc, exc_info=True)

            iteration += 1
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, interval - elapsed)
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

    def _build_sample_line(self) -> bytes | None:
        """Build one JSON-lines payload using the exact C# bridge field names."""
        from api.services.simulation.dyno_simulator import get_simulator

        sim = get_simulator()
        ch = sim.channels  # SimulatedChannels dataclass
        cfg = sim.config  # SimulatorConfig -- has environmental conditions

        now = time.time()
        elapsed = now - self._start_time

        # Mirror ChannelMapper.cs field names exactly
        payload: dict = {
            "ts": now,
            "elapsed": round(elapsed, 3),
            "engine_rpm": round(ch.rpm, 1),
            "roller_rpm": round(ch.rpm * 0.95, 1),  # Simulated drivetrain loss
            "engine_hp": round(ch.horsepower, 2),
            "wheel_hp": round(ch.horsepower * 0.88, 2),  # ~12% drivetrain loss
            "engine_torque_ftlb": round(ch.torque_ftlb, 2),
            "wheel_torque_ftlb": round(ch.torque_ftlb * 0.88, 2),
            "engine_kw": round(ch.horsepower * 0.7457, 2),
            "wheel_kw": round(ch.horsepower * 0.88 * 0.7457, 2),
            "engine_torque_nm": round(ch.torque_ftlb * 1.3558, 2),
            "wheel_torque_nm": round(ch.torque_ftlb * 0.88 * 1.3558, 2),
            "afr_front": round(ch.afr_front, 2),
            "afr_rear": round(ch.afr_rear, 2),
            "map_kpa": round(ch.map_kpa, 1),
            "tps": round(ch.tps_pct, 1),
            "iat_f": round(ch.iat_f, 1),
            "engine_temp_f": round(ch.ect_f, 1),
            "force_lbs": round(ch.force_lbs, 2),
            "acceleration": round(ch.acceleration_g, 3),
            "speed_mph": round(ch.rpm * 0.012, 1),  # Rough estimate
            "ambient_temp_f": round(cfg.ambient_temp_f, 1),
            "ambient_pressure_inhg": round(cfg.barometric_pressure_inhg, 2),
            "ambient_humidity": round(cfg.humidity_pct, 1),
            "is_logging": True,
            "dyno_connected": True,
            "dyno_type": "Simulator",
            "current_rpm": round(ch.rpm, 1),
            "gauge_power": round(ch.horsepower, 1),
            "gauge_torque": round(ch.torque_ftlb, 1),
            "env_correction": 1.0,
        }

        line = json.dumps(payload, separators=(",", ":")) + "\n"
        return line.encode("utf-8")

    def _broadcast(self, data: bytes) -> None:
        dead: list[socket.socket] = []
        with self._clients_lock:
            for sock in self._clients:
                try:
                    sock.sendall(data)
                except Exception:
                    dead.append(sock)
            for sock in dead:
                try:
                    sock.close()
                except Exception:
                    pass
                self._clients.remove(sock)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@simulator_bp.route("/simulator/start", methods=["POST"])
def start_simulator():
    """Start YourDyno simulator: physics engine + mock TCP bridge."""
    global _mock_bridge
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

        # Virtual ECU (optional, same logic as JetDrive simulator)
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

            if scenario == "lean":
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
                barometric_pressure_inhg=ecu_config.get("barometric_pressure_inhg", 29.92),
                ambient_temp_f=ecu_config.get("ambient_temp_f", 75.0),
            )

        # 1. Start physics engine
        sim = reset_simulator(config, virtual_ecu=virtual_ecu)
        sim.start()

        # 2. Start mock TCP bridge
        with _bridge_lock:
            if _mock_bridge is not None:
                _mock_bridge.stop()
            _mock_bridge = _MockTcpBridge()
            _mock_bridge.start()

        _set_sim_active(True)

        # 3. Give bridge a moment to bind, then start live capture
        #    (connects YourDynoClient to our mock bridge)
        time.sleep(0.15)
        _trigger_live_start()

        return jsonify({
            "success": True,
            "status": "started",
            "virtual_ecu_enabled": virtual_ecu is not None,
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
        })
    except Exception as e:
        logger.error("Failed to start YourDyno simulator: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@simulator_bp.route("/simulator/stop", methods=["POST"])
def stop_simulator():
    """Stop YourDyno simulator and mock bridge."""
    global _mock_bridge

    # 1. Stop live capture (disconnects YourDynoClient)
    _trigger_live_stop()

    # 2. Stop mock bridge
    with _bridge_lock:
        if _mock_bridge is not None:
            _mock_bridge.stop()
            _mock_bridge = None

    # 3. Stop physics engine
    from api.services.simulation.dyno_simulator import get_simulator

    sim = get_simulator()
    sim.stop()
    _set_sim_active(False)

    return jsonify({"success": True, "status": "stopped"})


@simulator_bp.route("/simulator/status", methods=["GET"])
def get_simulator_status():
    """Get current YourDyno simulator status."""
    if not _is_sim_active():
        return jsonify({"active": False, "state": "stopped"})

    from api.services.simulation.dyno_simulator import get_simulator

    try:
        sim = get_simulator()
        state = sim.get_state()
        ch = sim.channels
    except Exception as e:
        logger.error("Error getting YourDyno simulator status: %s", e)
        return jsonify({"active": True, "state": "idle", "error": str(e)})

    return jsonify({
        "active": True,
        "state": state.value,
        "profile": sim.config.profile.name,
        "current": {
            "rpm": round(ch.rpm, 0),
            "horsepower": round(ch.horsepower, 1),
            "torque": round(ch.torque_ftlb, 1),
            "afr": round((ch.afr_front + ch.afr_rear) / 2, 2),
            "tps": round(ch.tps_pct, 1),
        },
    })


@simulator_bp.route("/simulator/pull", methods=["POST"])
def trigger_pull():
    """Trigger a dyno pull."""
    if not _is_sim_active():
        return jsonify({"error": "Simulator not running"}), 400

    from api.services.simulation.dyno_simulator import SimState, get_simulator

    sim = get_simulator()
    current_state = sim.get_state()
    if current_state != SimState.IDLE:
        return jsonify({
            "error": f"Cannot start pull in state: {current_state.value}",
            "current_state": current_state.value,
        }), 400

    data = request.get_json() or {}
    raw_throttle = data.get("throttle", data.get("tps", 100.0))
    try:
        throttle_pct = float(raw_throttle)
    except Exception:
        return jsonify({"error": "Invalid throttle/tps (0-100)"}), 400

    if not (0.0 <= throttle_pct <= 100.0):
        return jsonify({"error": "throttle/tps must be between 0 and 100"}), 400

    sim.trigger_pull(throttle_pct=throttle_pct)
    return jsonify({
        "success": True,
        "status": "pull_started",
        "state": "pull",
        "throttle_pct": throttle_pct,
    })


@simulator_bp.route("/simulator/throttle", methods=["POST"])
def set_throttle():
    """Set simulator throttle (TPS %)."""
    if not _is_sim_active():
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


@simulator_bp.route("/simulator/profiles", methods=["GET"])
def get_profiles():
    """List available engine profiles."""
    from api.services.simulation.dyno_simulator import EngineProfile

    profiles = {
        "m8_114": EngineProfile.m8_114(),
        "m8_131": EngineProfile.m8_131(),
        "twin_cam_103": EngineProfile.twin_cam_103(),
        "sportbike_600": EngineProfile.sportbike_600(),
    }

    result = []
    for key, profile in profiles.items():
        result.append({
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
        })

    return jsonify({"profiles": result})


# ---------------------------------------------------------------------------
# Helpers -- programmatic live start/stop (avoids circular HTTP call)
# ---------------------------------------------------------------------------


def _trigger_live_start() -> None:
    """Start YourDynoClient capture programmatically (same as POST /live/start)."""
    from api.services.yourdyno import get_yourdyno_live_queue_manager, reset_yourdyno_live_queue_manager
    from api.services.yourdyno.yourdyno_client import YourDynoSample

    from ._shared import (
        _live_data,
        _live_data_event,
        _live_data_lock,
        _sample_ring,
        clear_live_buffers,
        get_client,
        mark_status,
    )
    from .live import _sample_to_channels

    with _live_data_lock:
        if _live_data.get("capturing"):
            return
        _live_data["capturing"] = True
        _live_data["connected"] = False
        _live_data["status"] = "starting"
        _live_data["error"] = None

    clear_live_buffers()
    reset_yourdyno_live_queue_manager()
    queue_mgr = get_yourdyno_live_queue_manager()
    queue_mgr.start_processing()

    def on_sample(sample: YourDynoSample) -> None:
        queue_mgr.on_sample(sample)
        channels = _sample_to_channels(sample)
        now_ts = time.time()
        with _live_data_lock:
            if not _live_data.get("capturing"):
                return
            live_channels = _live_data.get("channels")
            if not isinstance(live_channels, dict):
                live_channels = {}
                _live_data["channels"] = live_channels
            live_channels.update(channels)
            _live_data["last_update_ts"] = now_ts
            _live_data["last_update"] = datetime.fromtimestamp(now_ts).isoformat()
            _live_data["connected"] = True
            _live_data["status"] = "capturing"
            _live_data["error"] = None
            _sample_ring.append(sample.to_dict())
        _live_data_event.set()

    def on_status(status: dict) -> None:
        status_type = str(status.get("type", "unknown"))
        if status_type == "connected":
            mark_status("connected", connected=True)
        elif status_type == "hello":
            mark_status("hello", connected=True)
        elif status_type == "error":
            mark_status("error", connected=False, error=str(status.get("message", "error")))

    # Stop any existing client so we can re-register our callbacks.
    # The singleton may already be running from a previous /live/start or
    # from the frontend's autoConnect polling.
    client = get_client()
    if client._running:
        client.stop()
    client.start(on_sample=on_sample, on_status=on_status)


def _trigger_live_stop() -> None:
    """Stop YourDynoClient capture programmatically (same as POST /live/stop)."""
    from api.services.yourdyno import get_yourdyno_live_queue_manager

    from ._shared import _live_data, _live_data_event, _live_data_lock, get_client

    client = get_client()
    client.stop()

    queue_mgr = get_yourdyno_live_queue_manager()
    queue_mgr.force_flush()
    queue_mgr.stop_processing()

    with _live_data_lock:
        _live_data["capturing"] = False
        _live_data["connected"] = False
        _live_data["status"] = "stopped"
    _live_data_event.set()
