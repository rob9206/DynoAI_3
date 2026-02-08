"""
JetDrive Auto-Tune – Hardware Discovery, Live Data, Monitoring & Health Routes.

Sub-blueprint for:
- /hardware/diagnostics, /hardware/discover, /hardware/discover/multi
- /hardware/monitor/*
- /hardware/live/* (start, stop, data, stream, debug, health)
- /hardware/validate, /hardware/heartbeat, /hardware/connect
- /hardware/start, /hardware/stop, /hardware/status
- /hardware/channels/discover, /hardware/health
"""

from __future__ import annotations

import asyncio
import json
import math
import socket
import sys
import threading
import time
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ._shared import (
    JETDRIVE_IFACE,
    JETDRIVE_MCAST_GROUP,
    JETDRIVE_PORT,
    _is_simulator_active,
    _live_data,
    _live_data_lock,
    _monitor_lock,
    _monitor_state,
    get_network_interfaces,
    get_project_root,
    logger,
    test_multicast_support,
    test_port_available,
)

hardware_bp = Blueprint("jetdrive_hardware", __name__)


# ---------------------------------------------------------------------------
# Hardware Diagnostics
# ---------------------------------------------------------------------------


@hardware_bp.route("/hardware/diagnostics", methods=["GET"])
def run_diagnostics():
    """Run hardware diagnostics for JetDrive connectivity."""
    results: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "ok",
        "checks": [],
    }

    errors = 0

    # 1. Network interfaces
    interfaces = get_network_interfaces()
    results["checks"].append(
        {
            "name": "network_interfaces",
            "status": "ok" if interfaces else "error",
            "message": f"Found {len(interfaces)} interface(s)",
            "details": interfaces,
        }
    )
    if not interfaces:
        errors += 1

    # 2. Multicast support
    multicast_results: list[dict[str, Any]] = []
    multicast_ok = False

    for iface in interfaces:
        if iface["is_loopback"]:
            continue
        ok, msg = test_multicast_support(iface["ip"])
        multicast_results.append(
            {
                "interface": iface["ip"],
                "status": "ok" if ok else "warning",
                "message": msg,
            }
        )
        if ok:
            multicast_ok = True

    ok, msg = test_multicast_support("0.0.0.0")
    multicast_results.append(
        {
            "interface": "0.0.0.0 (any)",
            "status": "ok" if ok else "error",
            "message": msg,
        }
    )
    if ok:
        multicast_ok = True
    else:
        errors += 1

    results["checks"].append(
        {
            "name": "multicast_support",
            "status": "ok" if multicast_ok else "error",
            "message": f"Multicast group: {JETDRIVE_MCAST_GROUP}",
            "details": multicast_results,
        }
    )

    # 3. Port availability
    ok, msg = test_port_available(JETDRIVE_PORT)
    results["checks"].append(
        {
            "name": "port_availability",
            "status": "ok" if ok else "error",
            "message": msg,
            "details": {"port": JETDRIVE_PORT},
        }
    )
    if not ok:
        errors += 1

    # 4. Environment configuration
    results["checks"].append(
        {
            "name": "environment",
            "status": "ok",
            "message": "Environment configuration",
            "details": {
                "JETDRIVE_MCAST_GROUP": JETDRIVE_MCAST_GROUP,
                "JETDRIVE_PORT": JETDRIVE_PORT,
                "JETDRIVE_IFACE": JETDRIVE_IFACE,
            },
        }
    )

    if errors > 0:
        results["overall_status"] = "error"
        results["error_count"] = errors

    return jsonify(results)


@hardware_bp.route("/hardware/discover", methods=["GET"])
def discover_providers():
    """Discover JetDrive providers on the network."""
    timeout = float(request.args.get("timeout", 3.0))

    try:
        project_root = get_project_root()
        sys.path.insert(0, str(project_root))

        from api.services.jetdrive.jetdrive_client import JetDriveConfig
        from api.services.jetdrive.jetdrive_client import (
            discover_providers as async_discover,
        )

        config = JetDriveConfig(
            multicast_group=JETDRIVE_MCAST_GROUP,
            port=JETDRIVE_PORT,
            iface=JETDRIVE_IFACE,
        )

        providers = asyncio.run(async_discover(config, timeout=timeout))

        provider_list: list[dict[str, Any]] = []
        for p in providers:
            channels = []
            for chan_id, chan in p.channels.items():
                channels.append({"id": chan_id, "name": chan.name, "unit": chan.unit})

            provider_list.append(
                {
                    "provider_id": p.provider_id,
                    "provider_id_hex": f"0x{p.provider_id:04X}",
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": channels,
                    "channel_count": len(channels),
                }
            )

        return jsonify(
            {
                "success": True,
                "timeout": timeout,
                "providers_found": len(provider_list),
                "providers": provider_list,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "providers_found": 0,
                    "providers": [],
                }
            ),
            500,
        )


@hardware_bp.route("/hardware/discover/multi", methods=["GET"])
def discover_providers_multi():
    """Discover JetDrive providers on multiple multicast addresses."""
    timeout = float(request.args.get("timeout", 3.0))

    multicast_groups = [
        "224.0.2.10",
        "239.255.60.60",
    ]

    results: dict[str, Any] = {}

    try:
        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
            discover_providers as _discover_providers,
        )

        for mcast_group in multicast_groups:
            try:
                config = JetDriveConfig(
                    multicast_group=mcast_group,
                    port=JETDRIVE_PORT,
                    iface=JETDRIVE_IFACE,
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    providers = loop.run_until_complete(
                        _discover_providers(config, timeout=timeout)
                    )
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

                provider_list: list[dict[str, Any]] = []
                for p in providers:
                    channels = []
                    for chan_id, chan in p.channels.items():
                        channels.append(
                            {"id": chan_id, "name": chan.name, "unit": chan.unit}
                        )

                    provider_list.append(
                        {
                            "provider_id": p.provider_id,
                            "provider_id_hex": f"0x{p.provider_id:04X}",
                            "name": p.name,
                            "host": p.host,
                            "port": p.port,
                            "channels": channels,
                            "channel_count": len(channels),
                        }
                    )

                results[mcast_group] = {
                    "success": True,
                    "providers_found": len(provider_list),
                    "providers": provider_list,
                    "error": None,
                }

            except Exception as e:
                results[mcast_group] = {
                    "success": False,
                    "providers_found": 0,
                    "providers": [],
                    "error": str(e),
                }
                logger.error(f"Discovery error for {mcast_group}: {e}", exc_info=True)

        best_address = None
        best_count = 0
        for mcast_group, result in results.items():
            if result["success"] and result["providers_found"] > best_count:
                best_count = result["providers_found"]
                best_address = mcast_group

        return jsonify(
            {
                "success": True,
                "timeout": timeout,
                "results": results,
                "recommendation": {
                    "best_address": best_address,
                    "providers_found": best_count,
                    "message": (
                        f"Use multicast address: {best_address}"
                        if best_address
                        else "No providers found on either address. Check Power Core settings and network connection."
                    ),
                },
            }
        )

    except Exception as e:
        return (
            jsonify({"success": False, "error": str(e), "results": results}),
            500,
        )


# ---------------------------------------------------------------------------
# Connection Monitor
# ---------------------------------------------------------------------------


def _monitor_loop():
    """Background thread for connection monitoring."""
    project_root = get_project_root()
    sys.path.insert(0, str(project_root))

    from api.services.jetdrive.jetdrive_client import JetDriveConfig
    from api.services.jetdrive.jetdrive_client import (
        discover_providers as async_discover,
    )

    config = JetDriveConfig(
        multicast_group=JETDRIVE_MCAST_GROUP,
        port=JETDRIVE_PORT,
        iface=JETDRIVE_IFACE,
    )

    while True:
        with _monitor_lock:
            if not _monitor_state["running"]:
                break

        try:
            providers = asyncio.run(async_discover(config, timeout=2.0))

            provider_list: list[dict[str, Any]] = []
            for p in providers:
                provider_list.append(
                    {
                        "provider_id": p.provider_id,
                        "name": p.name,
                        "host": p.host,
                        "channel_count": len(p.channels),
                    }
                )

            with _monitor_lock:
                _monitor_state["last_check"] = datetime.now().isoformat()
                _monitor_state["providers"] = provider_list
                _monitor_state["history"].append(
                    {
                        "timestamp": _monitor_state["last_check"],
                        "connected": len(provider_list) > 0,
                        "provider_count": len(provider_list),
                    }
                )
                if len(_monitor_state["history"]) > 60:
                    _monitor_state["history"] = _monitor_state["history"][-60:]

        except Exception:
            with _monitor_lock:
                _monitor_state["last_check"] = datetime.now().isoformat()
                _monitor_state["providers"] = []
                _monitor_state["history"].append(
                    {
                        "timestamp": _monitor_state["last_check"],
                        "connected": False,
                        "provider_count": 0,
                        "error": True,
                    }
                )

        time.sleep(3.0)


@hardware_bp.route("/hardware/monitor/start", methods=["POST"])
def start_monitor():
    """Start the connection monitor."""
    with _monitor_lock:
        if _monitor_state["running"]:
            return jsonify({"status": "already_running"})
        _monitor_state["running"] = True
        _monitor_state["history"] = []

    thread = threading.Thread(target=_monitor_loop, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@hardware_bp.route("/hardware/monitor/stop", methods=["POST"])
def stop_monitor():
    """Stop the connection monitor."""
    with _monitor_lock:
        _monitor_state["running"] = False
    return jsonify({"status": "stopped"})


@hardware_bp.route("/hardware/monitor/status", methods=["GET"])
def get_monitor_status():
    """Get current monitor status."""
    with _monitor_lock:
        return jsonify(
            {
                "running": _monitor_state["running"],
                "last_check": _monitor_state["last_check"],
                "providers": _monitor_state["providers"],
                "connected": len(_monitor_state["providers"]) > 0,
                "history": _monitor_state["history"][-20:],
            }
        )


# ---------------------------------------------------------------------------
# Live Data Streaming
# ---------------------------------------------------------------------------


def _live_capture_loop(requested_provider_id: int | None = None):
    """Background thread to capture live channel data continuously."""
    global _live_data

    from api.services.jetdrive.jetdrive_client import (
        JetDriveConfig,
        JetDriveSample,
        discover_providers as _discover_providers,
        subscribe,
    )
    from api.services.jetdrive.jetdrive_live_queue import (
        get_live_queue_manager,
        reset_live_queue_manager,
    )
    from api.services.jetdrive.jetdrive_validation import get_validator

    config = JetDriveConfig.from_env()
    validator = get_validator()

    reset_live_queue_manager()
    queue_mgr = get_live_queue_manager()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        logger.info("Discovering JetDrive providers (waiting for ChannelInfo)...")
        providers = loop.run_until_complete(_discover_providers(config, timeout=10.0))
        if not providers:
            logger.warning(
                "No JetDrive providers found. Check network connection and multicast settings."
            )
            with _live_data_lock:
                _live_data["channels"] = {}
                _live_data["last_update_ts"] = time.time()
                _live_data["error"] = "No providers found"
                _live_data["provider_id"] = None
                _live_data["provider_name"] = None
                _live_data["provider_host"] = None
            return

        from api.services.jetdrive.jetdrive_client import merge_all_providers

        if requested_provider_id is not None:
            provider = None
            for p in providers:
                if p.provider_id == requested_provider_id:
                    provider = p
                    break
            if provider is None:
                logger.warning(
                    f"Requested provider 0x{requested_provider_id:04X} not found. Available: {[hex(p.provider_id) for p in providers]}"
                )
                with _live_data_lock:
                    _live_data["error"] = (
                        f"Provider 0x{requested_provider_id:04X} not found"
                    )
                return
        else:
            provider = merge_all_providers(providers)
            logger.info(
                f"Merged {len(providers)} providers: {[hex(p.provider_id) for p in providers]}"
            )

        providers_by_id = {p.provider_id: p for p in providers}

        validator.set_active_provider(None)
        validator.reset(provider.provider_id)

        logger.info(
            f"Connected and pinned to provider: {provider.name} (ID: 0x{provider.provider_id:04X}, Host: {provider.host})"
        )

        with _live_data_lock:
            _live_data["provider_id"] = provider.provider_id
            _live_data["provider_name"] = provider.name
            _live_data["provider_host"] = provider.host

        queue_mgr.start_processing()

        channel_values: dict[str, dict[str, Any]] = {}
        canonical_sources: dict[str, tuple[int, int]] = {}

        def _unit_score_for_canonical(canonical: str, unit: int) -> int:
            try:
                u = int(unit)
            except Exception:
                u = -1

            if canonical in ("Digital RPM 1", "Digital RPM 2", "Engine RPM", "RPM"):
                return 100 if u == 8 else 0
            if canonical in ("Speed", "Speed 1"):
                return 100 if u == 2 else 0
            if canonical.startswith("Force"):
                return 100 if u == 3 else 0
            if canonical.startswith("Power") or canonical == "Horsepower":
                return 100 if u == 4 else 0
            if canonical.startswith("Torque"):
                return 100 if u == 5 else 0
            if canonical.startswith("Air/Fuel") or canonical in ("AFR", "AFR 1"):
                return 100 if u == 11 else 0
            if canonical.startswith("Lambda"):
                return 100 if u == 13 else 0
            if canonical in ("MAP kPa", "Pressure"):
                return 60 if u == 7 else 0
            return 0

        def _apply_deadband(name: str, unit: int, value: float) -> float:
            try:
                u = int(unit)
            except Exception:
                u = -1
            v = float(value)
            if (
                name in ("Digital RPM 1", "Digital RPM 2", "Engine RPM", "RPM")
                or u == 8
            ):
                return 0.0 if abs(v) < 25 else v
            if name in ("Speed", "Speed 1") or u == 2:
                return 0.0 if abs(v) < 0.5 else v
            if name.startswith("Force") or u == 3:
                return 0.0 if abs(v) < 2.0 else v
            if name.startswith("Torque") or u == 5:
                return 0.0 if abs(v) < 2.0 else v
            if name.startswith("Power") or name == "Horsepower" or u == 4:
                return 0.0 if abs(v) < 0.5 else v
            return v

        def _c_to_f(c: float) -> float:
            return (float(c) * 9.0 / 5.0) + 32.0

        def on_sample(s: JetDriveSample):
            validator.record_sample(s)
            queue_mgr.on_sample(s)

            prov = providers_by_id.get(s.provider_id)
            meta = (prov.channels or {}).get(s.channel_id) if prov else None
            raw_unit = int(getattr(meta, "unit", -1)) if meta else -1

            canonical_name = s.channel_name
            canonical_category = getattr(s, "category", "misc")
            canonical_units = getattr(s, "units", "")
            canonical_value = float(s.value)

            if raw_unit == 7 and canonical_name.strip().lower() == "pressure":
                has_atmo = any(
                    k in channel_values
                    for k in ("Humidity", "Temperature 1", "Temperature 2")
                )
                if not has_atmo:
                    canonical_name = "MAP kPa"
                    canonical_category = "engine"
                    canonical_units = "kPa"
                else:
                    canonical_units = "kPa"
                    canonical_category = "atmospheric"

            if raw_unit == 6 and (
                canonical_name.startswith("Internal Temp")
                or canonical_name.startswith("Temperature ")
            ):
                canonical_value = _c_to_f(canonical_value)
                canonical_units = "°F"

            canonical_value = _apply_deadband(canonical_name, raw_unit, canonical_value)

            channel_key = f"0x{s.provider_id:04X}:{s.channel_id}:{s.channel_name}"

            entry: dict[str, Any] = {
                "key": channel_key,
                "provider_id": s.provider_id,
                "id": s.channel_id,
                "name": canonical_name,
                "value": canonical_value,
                "timestamp": s.timestamp_ms,
                "updated_at_ts": time.time(),
                "category": canonical_category,
                "units": canonical_units,
            }

            ATMO_PROBE_CHANNELS = {35, 36, 37, 38}
            ATMO_CANONICAL_NAMES = {
                "Pressure",
                "Temperature 1",
                "Temperature 2",
                "Humidity",
            }

            current = canonical_sources.get(canonical_name)
            candidate = (s.provider_id, s.channel_id)

            if current is None:
                canonical_sources[canonical_name] = candidate
            elif candidate != current:
                cur_provider_id, cur_chan_id = current

                if canonical_name in ATMO_CANONICAL_NAMES:
                    candidate_is_probe = s.channel_id in ATMO_PROBE_CHANNELS
                    current_is_probe = cur_chan_id in ATMO_PROBE_CHANNELS
                    if candidate_is_probe and not current_is_probe:
                        canonical_sources[canonical_name] = candidate
                else:
                    cur_prov = providers_by_id.get(cur_provider_id)
                    cur_meta = (
                        (cur_prov.channels or {}).get(cur_chan_id) if cur_prov else None
                    )
                    cur_unit = int(getattr(cur_meta, "unit", -1)) if cur_meta else -1
                    if _unit_score_for_canonical(
                        canonical_name, raw_unit
                    ) > _unit_score_for_canonical(canonical_name, cur_unit):
                        canonical_sources[canonical_name] = candidate

            if canonical_sources.get(canonical_name) == candidate:
                channel_values[canonical_name] = entry

            chan_alias = f"chan_{s.channel_id}"
            channel_values.setdefault(chan_alias, entry)

            now_ts = time.time()
            with _live_data_lock:
                live_channels = _live_data.get("channels")
                if not isinstance(live_channels, dict):
                    live_channels = {}
                    _live_data["channels"] = live_channels
                live_channels[canonical_name] = entry
                if chan_alias not in live_channels:
                    live_channels[chan_alias] = entry
                _live_data["last_update_ts"] = now_ts
                if "error" in _live_data:
                    del _live_data["error"]

        stop_event = asyncio.Event()

        async def check_stop_periodically():
            while True:
                await asyncio.sleep(0.5)
                with _live_data_lock:
                    if not _live_data.get("capturing", False):
                        stop_event.set()
                        break

        check_task = loop.create_task(check_stop_periodically())

        logger.info("Starting continuous data capture...")
        logger.info(f"Provider channels: {list(provider.channels.keys())}")

        sample_count = [0]
        last_sample_time = [None]
        stats_dict: dict[str, Any] = {
            "total_frames": 0,
            "dropped_frames": 0,
            "non_provider_frames": 0,
        }

        def on_sample_with_stats(s: JetDriveSample):
            sample_count[0] += 1
            last_sample_time[0] = datetime.now()
            if sample_count[0] % 500 == 0:
                logger.info(
                    f"Received {sample_count[0]} samples from provider 0x{s.provider_id:04X}, latest: {s.channel_name}={s.value}"
                )
            on_sample(s)
            validator.record_frame_stats(s.provider_id, total=1)

        async def subscribe_with_stats():
            try:
                stats = await subscribe(
                    provider,
                    [],
                    on_sample_with_stats,
                    config=config,
                    stop_event=stop_event,
                    recv_timeout=2.0,
                    debug=True,
                    return_stats=True,
                )
                if stats:
                    stats_dict.update(stats)
                return stats
            except Exception as e:
                logger.error(f"Subscribe error: {e}", exc_info=True)
                raise

        try:
            logger.info(
                f"Subscribing to provider {provider.name} (ID: 0x{provider.provider_id:04X})"
            )
            logger.info(f"Available channels: {list(provider.channels.keys())}")

            stats = loop.run_until_complete(subscribe_with_stats())

            logger.info(f"Capture ended. Statistics: {stats_dict}")
            logger.info(f"Total samples received: {sample_count[0]}")

            if stats_dict.get("total_frames", 0) == 0:
                logger.warning("No frames received during capture period. Check:")
                logger.warning("  1. DynoWare RT-150 is powered on and connected")
                logger.warning("  2. JetDrive is enabled in Power Core")
                logger.warning("  3. Network connection is active")
                logger.warning("  4. Firewall allows UDP port 22344")
                with _live_data_lock:
                    if not _live_data.get("error"):
                        _live_data["error"] = (
                            "No data frames received. Check dyno connection and JetDrive settings."
                        )
            elif stats_dict.get("non_provider_frames", 0) > 0:
                logger.warning(
                    f"Received {stats_dict['non_provider_frames']} frames from other providers"
                )

            if sample_count[0] == 0 and stats_dict.get("total_frames", 0) > 0:
                logger.warning(
                    "Frames received but no valid samples parsed. Provider ID may not match."
                )
                with _live_data_lock:
                    if not _live_data.get("error"):
                        _live_data["error"] = (
                            f"Received frames but no samples. Provider ID: 0x{provider.provider_id:04X}"
                        )
            elif sample_count[0] > 0:
                logger.info(
                    f"Successfully received {sample_count[0]} samples from provider"
                )

        except Exception as e:
            logger.error(f"Error during data capture: {e}", exc_info=True)
            with _live_data_lock:
                _live_data["error"] = f"Capture error: {str(e)}"
        finally:
            queue_mgr.force_flush()
            queue_mgr.stop_processing()
            check_task.cancel()
            try:
                loop.run_until_complete(check_task)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Live capture loop error: {e}", exc_info=True)
        with _live_data_lock:
            _live_data["channels"] = {}
            _live_data["last_update_ts"] = time.time()
            _live_data["error"] = str(e)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                try:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:
                    pass
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
        logger.info("Live capture loop ended")


@hardware_bp.route("/hardware/live/start", methods=["POST"])
def start_live_capture():
    """Start live data capture."""
    global _live_data

    provider_id_param = request.args.get("provider_id")
    requested_provider_id = None
    if provider_id_param:
        try:
            if provider_id_param.lower().startswith("0x"):
                requested_provider_id = int(provider_id_param, 16)
            else:
                requested_provider_id = int(provider_id_param)
        except ValueError:
            return (
                jsonify(
                    {
                        "status": "error",
                        "error": f"Invalid provider_id format: {provider_id_param}",
                    }
                ),
                400,
            )

    with _live_data_lock:
        if _live_data["capturing"]:
            return jsonify(
                {
                    "status": "already_capturing",
                    "provider_id": _live_data.get("provider_id"),
                    "provider_name": _live_data.get("provider_name"),
                }
            )
        _live_data["capturing"] = True
        _live_data["channels"] = {}
        _live_data["last_update_ts"] = None
        _live_data["provider_id"] = None
        _live_data["provider_name"] = None
        _live_data["provider_host"] = None

    thread = threading.Thread(
        target=_live_capture_loop, args=(requested_provider_id,), daemon=True
    )
    thread.start()

    return jsonify(
        {"status": "started", "requested_provider_id": requested_provider_id}
    )


@hardware_bp.route("/hardware/live/stop", methods=["POST"])
def stop_live_capture():
    """Stop live data capture and release the pinned provider."""
    global _live_data

    from api.services.jetdrive.jetdrive_validation import get_validator

    with _live_data_lock:
        _live_data["capturing"] = False
        provider_id = _live_data.get("provider_id")

    validator = get_validator()
    validator.set_active_provider(None)

    return jsonify({"status": "stopped", "released_provider_id": provider_id})


@hardware_bp.route("/hardware/live/data", methods=["GET"])
def get_live_data():
    """Get current live channel data (polling-friendly JSON)."""
    return jsonify(_build_live_data_payload())


def _build_live_data_payload() -> dict[str, Any]:
    """Shared payload builder for polling + SSE."""
    if _is_simulator_active():
        from api.services.simulation.dyno_simulator import get_simulator

        sim = get_simulator()
        channels = sim.get_channels()
        state = sim.get_state().value
        return {
            "capturing": True,
            "simulated": True,
            "sim_state": state,
            "last_update_ts": time.time(),
            "last_update": datetime.now().isoformat(),
            "channels": channels,
            "channel_count": len(channels),
        }

    def _get_value(channels_dict: dict[str, Any], keys: list[str]) -> float | None:
        for k in keys:
            v = channels_dict.get(k)
            if isinstance(v, dict) and "value" in v:
                try:
                    return float(v.get("value"))
                except Exception:
                    continue
        return None

    with _live_data_lock:
        channels: dict[str, Any] = dict(_live_data.get("channels", {}) or {})
        capturing = _live_data.get("capturing", False)
        error = _live_data.get("error")
        last_update_ts = _live_data.get("last_update_ts")
        provider_id = _live_data.get("provider_id")
        provider_name = _live_data.get("provider_name")
        provider_host = _live_data.get("provider_host")

    is_stale = False
    if last_update_ts:
        try:
            age_seconds = float(time.time() - float(last_update_ts))
            if age_seconds > 10:
                is_stale = True
                if not error:
                    error = f"Data is stale (last update {age_seconds:.1f}s ago)"
        except Exception:
            pass

    try:
        from api.config import get_config

        rpm = _get_value(
            channels, ["Digital RPM 1", "Engine RPM", "RPM", "chan_39", "chan_9"]
        )
        force = _get_value(
            channels,
            ["Force Drum 1", "Force", "Force 1", "chan_36", "chan_32", "chan_34"],
        )

        if rpm is not None and force is not None and rpm > 0:
            cfg = get_config().dyno
            force_mag = abs(float(force))
            hp = cfg.calculate_hp_from_force(force_mag, rpm)
            tq = cfg.calculate_torque_from_force(force_mag)
            channels.setdefault("Horsepower", {"value": hp})
            channels.setdefault("Torque", {"value": tq})
    except Exception:
        pass

    for _ch_name, ch_data in channels.items():
        if isinstance(ch_data, dict) and "value" in ch_data:
            val = ch_data["value"]
            if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                ch_data["value"] = None

    last_update_iso = None
    if last_update_ts:
        try:
            last_update_iso = datetime.fromtimestamp(float(last_update_ts)).isoformat()
        except Exception:
            last_update_iso = None

    response: dict[str, Any] = {
        "capturing": capturing,
        "simulated": False,
        "last_update_ts": last_update_ts,
        "last_update": last_update_iso,
        "channels": channels,
        "channel_count": len(channels),
        "is_stale": is_stale,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "provider_host": provider_host,
    }

    if error:
        response["error"] = error

    return response


@hardware_bp.route("/hardware/live/stream", methods=["GET"])
def stream_live_data():
    """Server-Sent Events (SSE) stream for live channel data."""

    def _event_stream():
        last_sent_key: tuple[Any, ...] | None = None
        last_keepalive = time.time()
        while True:
            payload = _build_live_data_payload()
            key = (
                payload.get("simulated", False),
                payload.get("capturing", False),
                payload.get("sim_state"),
                payload.get("last_update_ts"),
            )
            if key != last_sent_key:
                last_sent_key = key
                yield f"data: {json.dumps(payload)}\n\n"
                last_keepalive = time.time()
            else:
                now = time.time()
                if now - last_keepalive > 10.0:
                    yield ": keepalive\n\n"
                    last_keepalive = now
            time.sleep(0.25)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(
        stream_with_context(_event_stream()),
        mimetype="text/event-stream",
        headers=headers,
    )


@hardware_bp.route("/hardware/live/debug", methods=["GET"])
def get_live_debug():
    """Get debug information about live capture status."""
    from api.services.jetdrive.jetdrive_client import (
        JetDriveConfig,
        discover_providers as _discover_providers,
    )

    with _live_data_lock:
        capturing = _live_data.get("capturing", False)
        channels = dict(_live_data.get("channels", {}) or {})
        last_update_ts = _live_data.get("last_update_ts")
        error = _live_data.get("error")

    config = JetDriveConfig.from_env()
    providers: list[Any] = []
    discovery_error = None

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            providers = loop.run_until_complete(_discover_providers(config, timeout=5.0))
        finally:
            try:
                loop.close()
            except Exception:
                pass
    except Exception as e:
        discovery_error = str(e)
        logger.error(f"Provider discovery error: {e}", exc_info=True)

    socket_test: dict[str, Any] = {"success": False, "error": None}
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.bind((config.iface, config.port))
        mreq = socket.inet_aton(config.multicast_group) + socket.inet_aton(
            config.iface or "0.0.0.0"
        )
        test_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        test_sock.close()
        socket_test = {"success": True, "error": None}
    except Exception as e:
        socket_test = {"success": False, "error": str(e)}
        logger.error(f"Socket test error: {e}", exc_info=True)

    data_age = None
    if last_update_ts:
        try:
            data_age = float(time.time() - float(last_update_ts))
        except Exception:
            pass

    last_update_iso = None
    if last_update_ts:
        try:
            last_update_iso = datetime.fromtimestamp(float(last_update_ts)).isoformat()
        except Exception:
            last_update_iso = None

    interfaces: list[dict[str, str]] = []
    try:
        import socket as sock_module

        hostname = sock_module.gethostname()
        local_ip = sock_module.gethostbyname(hostname)
        interfaces.append({"name": "default", "ip": local_ip})
    except Exception:
        pass

    return jsonify(
        {
            "capturing": capturing,
            "channels_received": len(channels),
            "last_update_ts": last_update_ts,
            "last_update": last_update_iso,
            "data_age_seconds": data_age,
            "error": error,
            "provider_count": len(providers),
            "providers": [
                {
                    "id": f"0x{p.provider_id:04X}",
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": len(p.channels),
                }
                for p in providers
            ],
            "discovery_error": discovery_error,
            "socket_test": socket_test,
            "config": {
                "multicast_group": config.multicast_group,
                "port": config.port,
                "iface": config.iface,
            },
            "troubleshooting": {
                "check_multicast_group": f"Verify DynoWare RT-150 is broadcasting to {config.multicast_group}:{config.port}",
                "check_network": "Ensure both devices are on the same network subnet",
                "check_firewall": "Windows Firewall must allow UDP port 22344 inbound",
                "check_jetdrive": "Verify JetDrive is enabled in Power Core software",
                "check_power": "Ensure DynoWare RT-150 is powered on and connected",
                "try_interface": "Try setting JETDRIVE_IFACE to your computer's IP address (not 0.0.0.0)",
            },
        }
    )


@hardware_bp.route("/hardware/live/health", methods=["GET"])
def get_live_health():
    """Get comprehensive data health status for ingestion monitoring."""
    from api.services.jetdrive.jetdrive_validation import get_validator

    provider_id_param = request.args.get("provider_id")
    filter_provider_id = None
    if provider_id_param:
        try:
            if provider_id_param.lower().startswith("0x"):
                filter_provider_id = int(provider_id_param, 16)
            else:
                filter_provider_id = int(provider_id_param)
        except ValueError:
            pass

    with _live_data_lock:
        capturing = _live_data.get("capturing", False)
        pinned_provider_id = _live_data.get("provider_id")
        pinned_provider_name = _live_data.get("provider_name")
        pinned_provider_host = _live_data.get("provider_host")

    validator = get_validator()
    validator_health = validator.get_all_health(provider_id=filter_provider_id)

    if not capturing:
        validator_health["overall_health"] = "unknown"
        validator_health["health_reason"] = "Live capture not active"

    validator_health["pinned_provider"] = {
        "provider_id": pinned_provider_id,
        "provider_name": pinned_provider_name,
        "provider_host": pinned_provider_host,
    }
    validator_health["capturing"] = capturing

    return jsonify(validator_health)


@hardware_bp.route("/hardware/live/health/summary", methods=["GET"])
def get_live_health_summary():
    """Get quick channel summary for lightweight polling."""
    from api.services.jetdrive.jetdrive_validation import get_validator

    provider_id_param = request.args.get("provider_id")
    filter_provider_id = None
    if provider_id_param:
        try:
            if provider_id_param.lower().startswith("0x"):
                filter_provider_id = int(provider_id_param, 16)
            else:
                filter_provider_id = int(provider_id_param)
        except ValueError:
            pass

    with _live_data_lock:
        pinned_provider_id = _live_data.get("provider_id")

    validator = get_validator()
    summary = validator.get_channel_summary(provider_id=filter_provider_id)
    summary["pinned_provider_id"] = pinned_provider_id

    return jsonify(summary)


# ---------------------------------------------------------------------------
# Hardware validation (RT-150 network + config parameters)
# ---------------------------------------------------------------------------


def _load_rt150_config() -> dict[str, Any]:
    """Load RT-150 reference configuration JSON from config folder."""
    cfg_path = get_project_root() / "config" / "dynoware_rt150.json"
    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load RT-150 config at {cfg_path}: {exc}"
        ) from exc


@hardware_bp.route("/hardware/validate", methods=["GET"])
def validate_hardware():
    """Validate RT-150 network reachability and config parameters."""
    warnings: list[str] = []

    try:
        rt150 = _load_rt150_config()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    try:
        from api.config import get_config

        env_cfg = get_config().dyno
    except Exception:
        logger.error("Failed to read env config in /hardware/validate", exc_info=True)
        return jsonify({"ok": False, "error": "Failed to read environment config"}), 500

    ref_ip = (rt150.get("network") or {}).get("ip_address")
    ref_port = (rt150.get("network") or {}).get("jetdrive_port")

    if ref_ip and env_cfg.ip_address and str(ref_ip) != str(env_cfg.ip_address):
        warnings.append(f"IP mismatch: reference {ref_ip} vs env {env_cfg.ip_address}")
    if (
        ref_port
        and env_cfg.jetdrive_port
        and int(ref_port) != int(env_cfg.jetdrive_port)
    ):
        warnings.append(
            f"Port mismatch: reference {ref_port} vs env {env_cfg.jetdrive_port}"
        )

    providers_info: list[dict[str, Any]] = []
    matched_provider = False
    try:
        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
            discover_providers as _discover_providers,
        )

        cfg = JetDriveConfig.from_env()
        if isinstance(ref_port, int):
            cfg.port = ref_port

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(_discover_providers(cfg, timeout=1.5))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        for p in providers:
            hostsame = bool(ref_ip) and str(p.host) == str(ref_ip)
            if hostsame:
                matched_provider = True
            providers_info.append(
                {
                    "provider_id": p.provider_id,
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "channels": len(p.channels or {}),
                    "matches_expected_ip": hostsame,
                }
            )
    except Exception:
        logger.warning("Discovery error in /hardware/validate", exc_info=True)
        warnings.append("Discovery error")

    result = {
        "ok": True,
        "reference": {
            "ip_address": ref_ip,
            "jetdrive_port": ref_port,
            "drum1": (rt150.get("drums") or {}).get("drum1"),
        },
        "environment": {
            "ip_address": env_cfg.ip_address,
            "jetdrive_port": env_cfg.jetdrive_port,
            "drum1": {
                "serial": env_cfg.drum1_serial,
                "mass_slugs": env_cfg.drum1_mass_slugs,
                "circumference_ft": env_cfg.drum1_circumference_ft,
                "tabs": env_cfg.drum1_tabs,
            },
        },
        "network": {
            "providers_found": len(providers_info),
            "matched_expected_ip": matched_provider,
            "providers": providers_info,
        },
        "warnings": warnings,
    }
    return jsonify(result)


@hardware_bp.route("/hardware/heartbeat", methods=["GET"])
def hardware_heartbeat():
    """Lightweight discovery-based heartbeat to confirm UDP responsiveness."""
    try:
        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
            discover_providers as _discover_providers,
        )

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(_discover_providers(cfg, timeout=1.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        return jsonify(
            {
                "ok": True,
                "providers": [
                    {
                        "id": p.provider_id,
                        "host": p.host,
                        "name": p.name,
                        "port": p.port,
                    }
                    for p in providers
                ],
                "count": len(providers),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@hardware_bp.route("/hardware/connect", methods=["POST"])
def connect_hardware():
    """Attempt to discover JetDrive providers and mark connection state."""
    try:
        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
            discover_providers as _discover_providers,
        )

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(_discover_providers(cfg, timeout=2.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

        return jsonify(
            {
                "success": True,
                "connected": len(providers) > 0,
                "providers": [
                    {
                        "id": p.provider_id,
                        "host": p.host,
                        "name": p.name,
                        "port": p.port,
                    }
                    for p in providers
                ],
                "count": len(providers),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@hardware_bp.route("/hardware/start", methods=["POST"])
def start_hardware_stream():
    """Alias for /hardware/live/start to simplify clients."""
    try:
        return start_live_capture()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@hardware_bp.route("/hardware/stop", methods=["POST"])
def stop_hardware_stream():
    """Alias for /hardware/live/stop to simplify clients."""
    try:
        return stop_live_capture()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@hardware_bp.route("/hardware/status", methods=["GET"])
def hardware_status():
    """Composite status of live capture and a quick discovery snapshot."""
    try:
        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
            discover_providers as _discover_providers,
        )

        cfg = JetDriveConfig.from_env()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            providers = loop.run_until_complete(_discover_providers(cfg, timeout=1.0))
        finally:
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass
    except Exception:
        providers = []

    with _live_data_lock:
        capturing = bool(_live_data.get("capturing"))
        last_update = _live_data.get("last_update")
        channel_count = len(_live_data.get("channels", {}))

    return jsonify(
        {
            "connected": len(providers) > 0,
            "providers": [
                {"id": p.provider_id, "host": p.host, "name": p.name, "port": p.port}
                for p in providers
            ],
            "live": {
                "capturing": capturing,
                "last_update": last_update,
                "channel_count": channel_count,
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@hardware_bp.route("/hardware/channels/discover", methods=["GET"])
def discover_channels():
    """Discover all available channels with their current values."""
    try:
        if _is_simulator_active():
            from api.services.simulation.dyno_simulator import get_simulator

            sim = get_simulator()
            channels_data = sim.get_channels()
        else:
            with _live_data_lock:
                channels_data = _live_data.get("channels", {})

        if not channels_data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No channel data available. Start live capture first.",
                        "channel_count": 0,
                        "channels": [],
                    }
                ),
                404,
            )

        channels: list[dict[str, Any]] = []
        for name, ch in channels_data.items():
            channel = (
                ch if isinstance(ch, dict) else {"value": ch, "id": 0, "name": name}
            )

            sample_values: list[Any] = []
            value_range: dict[str, Any] = {"min": None, "max": None}

            name_lower = name.lower()
            value = channel.get("value", 0)

            suggested_config: dict[str, Any] = {
                "label": name.replace("chan_", "Channel ").replace("_", " "),
                "units": "",
                "min": 0,
                "max": 100,
                "decimals": 2,
                "color": "#888",
            }

            keyword_matched = False

            if "rpm" in name_lower or "speed" in name_lower:
                suggested_config = {
                    "label": "RPM",
                    "units": "rpm",
                    "min": 0,
                    "max": 8000,
                    "decimals": 0,
                    "color": "#4ade80",
                }
                keyword_matched = True
            elif "afr" in name_lower or "air/fuel" in name_lower or "a/f" in name_lower:
                suggested_config = {
                    "label": "AFR",
                    "units": ":1",
                    "min": 10,
                    "max": 18,
                    "decimals": 2,
                    "color": "#f472b6",
                }
                keyword_matched = True
            elif "lambda" in name_lower:
                suggested_config = {
                    "label": "Lambda",
                    "units": "λ",
                    "min": 0.5,
                    "max": 2.0,
                    "decimals": 2,
                    "color": "#f472b6",
                }
                keyword_matched = True
            elif "force" in name_lower or "load" in name_lower:
                suggested_config = {
                    "label": "Force",
                    "units": "lbs",
                    "min": 0,
                    "max": 500,
                    "decimals": 1,
                    "color": "#4ade80",
                }
                keyword_matched = True
            elif "map" in name_lower or "manifold" in name_lower:
                suggested_config = {
                    "label": "MAP",
                    "units": "kPa",
                    "min": 0,
                    "max": 105,
                    "decimals": 1,
                    "color": "#06b6d4",
                }
                keyword_matched = True
            elif (
                "temp" in name_lower
                or "iat" in name_lower
                or "ect" in name_lower
                or "coolant" in name_lower
            ):
                suggested_config = {
                    "label": "Temperature",
                    "units": "°C",
                    "min": 0,
                    "max": 150,
                    "decimals": 1,
                    "color": "#f59e0b",
                }
                keyword_matched = True
            elif "tps" in name_lower or "throttle" in name_lower:
                suggested_config = {
                    "label": "Throttle",
                    "units": "%",
                    "min": 0,
                    "max": 100,
                    "decimals": 1,
                    "color": "#8b5cf6",
                }
                keyword_matched = True
            elif "volt" in name_lower or "battery" in name_lower:
                suggested_config = {
                    "label": "Voltage",
                    "units": "V",
                    "min": 0,
                    "max": 16,
                    "decimals": 2,
                    "color": "#eab308",
                }
                keyword_matched = True
            elif (
                "hp" in name_lower
                or "horsepower" in name_lower
                or "power" in name_lower
            ):
                suggested_config = {
                    "label": "Horsepower",
                    "units": "HP",
                    "min": 0,
                    "max": 500,
                    "decimals": 1,
                    "color": "#ef4444",
                }
                keyword_matched = True
            elif "torque" in name_lower:
                suggested_config = {
                    "label": "Torque",
                    "units": "ft-lb",
                    "min": 0,
                    "max": 200,
                    "decimals": 1,
                    "color": "#22c55e",
                }
                keyword_matched = True

            if not keyword_matched:
                if value > 500 and value < 15000:
                    suggested_config = {
                        "label": "RPM",
                        "units": "rpm",
                        "min": 0,
                        "max": 8000,
                        "decimals": 0,
                        "color": "#4ade80",
                    }
                elif value >= 9 and value <= 20:
                    suggested_config = {
                        "label": "AFR",
                        "units": ":1",
                        "min": 10,
                        "max": 18,
                        "decimals": 2,
                        "color": "#f472b6",
                    }
                elif value > 0.5 and value < 2.0:
                    suggested_config = {
                        "label": "Lambda",
                        "units": "λ",
                        "min": 0.5,
                        "max": 2.0,
                        "decimals": 2,
                        "color": "#f472b6",
                    }
                elif value > 50 and value < 250:
                    suggested_config = {
                        "label": "Temperature",
                        "units": "°C",
                        "min": 0,
                        "max": 150,
                        "decimals": 1,
                        "color": "#f59e0b",
                    }

            channels.append(
                {
                    "id": channel.get("id", 0),
                    "name": name,
                    "value": channel.get("value", 0),
                    "sample_values": sample_values,
                    "value_range": value_range,
                    "suggested_config": suggested_config,
                }
            )

        return jsonify(
            {
                "success": True,
                "channel_count": len(channels),
                "channels": channels,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error discovering channels: {e}", exc_info=True)
        return (
            jsonify(
                {"success": False, "error": str(e), "channel_count": 0, "channels": []}
            ),
            500,
        )


@hardware_bp.route("/hardware/health", methods=["GET"])
def check_hardware_health():
    """Check hardware connection health and latency."""
    try:
        start_time = time.time()

        if _is_simulator_active():
            from api.services.simulation.dyno_simulator import get_simulator

            sim = get_simulator()
            channels = sim.get_channels()
            latency_ms = (time.time() - start_time) * 1000

            return jsonify(
                {
                    "healthy": True,
                    "connected": True,
                    "simulated": True,
                    "latency_ms": latency_ms,
                    "channel_count": len(channels),
                }
            )

        with _live_data_lock:
            capturing = _live_data["capturing"]
            channel_count = len(_live_data["channels"])
            latency_ms = (time.time() - start_time) * 1000

        return jsonify(
            {
                "healthy": True,
                "connected": True,
                "simulated": False,
                "capturing": capturing,
                "latency_ms": latency_ms,
                "channel_count": channel_count,
            }
        )

    except Exception as e:
        logger.exception("Health check failed")
        return (
            jsonify({"healthy": False, "connected": False, "error": str(e)}),
            503,
        )
