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

from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template_string,
    request,
    stream_with_context,
)

from ._shared import (
    JETDRIVE_IFACE,
    JETDRIVE_MCAST_GROUP,
    JETDRIVE_PORT,
    _is_simulator_active,
    _live_data,
    _live_data_event,
    _live_data_lock,
    _monitor_lock,
    _monitor_state,
    _sample_ring,
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

        from api.services.jetdrive.jetdrive_client import (
            JetDriveConfig,
        )
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
        )
        from api.services.jetdrive.jetdrive_client import (
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

    from api.services.jetdrive.jetdrive_client import (
        JetDriveConfig,
    )
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
    )
    from api.services.jetdrive.jetdrive_client import (
        discover_providers as _discover_providers,
    )
    from api.services.jetdrive.jetdrive_client import (
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
        AFR_CANONICAL_NAMES = {"AFR Front", "AFR Rear", "AFR"}
        _knock_front: float | None = None
        _knock_rear: float | None = None

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

        from api.services.jetdrive.wideband_rescale import (
            canonicalize_wideband_sample,
        )

        def on_sample(s: JetDriveSample):
            nonlocal _knock_front, _knock_rear
            validator.record_sample(s)

            prov = providers_by_id.get(s.provider_id)
            meta = (prov.channels or {}).get(s.channel_id) if prov else None
            raw_unit = int(getattr(meta, "unit", -1)) if meta else -1
            raw_name_lower = str(s.channel_name or "").strip().lower()

            canonical_name = s.channel_name
            canonical_category = getattr(s, "category", "misc")
            canonical_units = getattr(s, "units", "")
            canonical_value = float(s.value)
            is_lc_canonical_afr = False

            queue_sample = s
            wideband = canonicalize_wideband_sample(canonical_name, canonical_value)
            if wideband is not None:
                canonical_name = wideband.canonical_name
                canonical_value = wideband.afr
                canonical_units = wideband.units
                canonical_category = wideband.category
                is_lc_canonical_afr = canonical_name in AFR_CANONICAL_NAMES
                queue_sample = JetDriveSample(
                    provider_id=s.provider_id,
                    channel_id=s.channel_id,
                    channel_name=canonical_name,
                    timestamp_ms=s.timestamp_ms,
                    value=canonical_value,
                    category=canonical_category,
                    units=canonical_units,
                )

            # Queue processing should receive canonicalized AFR values so the
            # 50 ms aggregation path and live CSV never ingest raw LC-2 volts.
            queue_mgr.on_sample(queue_sample)

            if raw_unit == 7:
                if "manifold" in raw_name_lower:
                    canonical_name = "MAP kPa"
                    canonical_category = "engine"
                    canonical_units = "kPa"
                elif canonical_name.strip().lower() == "pressure":
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

            if "throttle position" in raw_name_lower and "sensor" not in raw_name_lower:
                canonical_name = "TPS"
                canonical_category = "engine"
                canonical_units = "%"

            if raw_unit == 6:
                if "intake air temperature" in raw_name_lower:
                    canonical_name = "IAT"
                    canonical_category = "engine"
                    canonical_value = _c_to_f(canonical_value)
                    canonical_units = "°F"
                elif "engine temperature" in raw_name_lower:
                    canonical_name = "ECT"
                    canonical_category = "engine"
                    canonical_value = _c_to_f(canonical_value)
                    canonical_units = "°F"
                elif canonical_name.startswith("Internal Temp") or canonical_name.startswith(
                    "Temperature "
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
                "source_name": s.channel_name,
                "value": canonical_value,
                "timestamp": s.timestamp_ms,
                "updated_at_ts": time.time(),
                "category": canonical_category,
                "units": canonical_units,
            }

            allow_canonical_slot = not (
                canonical_name in AFR_CANONICAL_NAMES and not is_lc_canonical_afr
            )

            knock_entry: dict[str, Any] | None = None
            if "front spark knock retard" in raw_name_lower:
                _knock_front = canonical_value
            elif "rear spark knock retard" in raw_name_lower:
                _knock_rear = canonical_value
            if "spark knock retard" in raw_name_lower:
                knock_values = [v for v in (_knock_front, _knock_rear) if v is not None]
                if knock_values:
                    knock_sources: list[str] = []
                    if _knock_front is not None:
                        knock_sources.append("Front Spark Knock Retard")
                    if _knock_rear is not None:
                        knock_sources.append("Rear Spark Knock Retard")
                    knock_entry = {
                        "key": f"computed:Knock:{s.provider_id}",
                        "provider_id": s.provider_id,
                        "id": None,
                        "name": "Knock",
                        "source_name": ", ".join(knock_sources),
                        "value": float(max(knock_values)),
                        "timestamp": s.timestamp_ms,
                        "updated_at_ts": time.time(),
                        "category": "engine",
                        "units": "deg",
                        "computed": True,
                    }

            ATMO_PROBE_CHANNELS = {35, 36, 37, 38}
            ATMO_CANONICAL_NAMES = {
                "Pressure",
                "Temperature 1",
                "Temperature 2",
                "Humidity",
            }

            current = canonical_sources.get(canonical_name) if allow_canonical_slot else None
            candidate = (s.provider_id, s.channel_id)

            if allow_canonical_slot and current is None:
                canonical_sources[canonical_name] = candidate
            elif allow_canonical_slot and candidate != current:
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

            if allow_canonical_slot and canonical_sources.get(canonical_name) == candidate:
                channel_values[canonical_name] = entry

            chan_alias = f"chan_{s.channel_id}"
            channel_values.setdefault(chan_alias, entry)

            now_ts = time.time()
            with _live_data_lock:
                live_channels = _live_data.get("channels")
                if not isinstance(live_channels, dict):
                    live_channels = {}
                    _live_data["channels"] = live_channels
                if allow_canonical_slot:
                    live_channels[canonical_name] = entry
                if chan_alias not in live_channels:
                    live_channels[chan_alias] = entry
                if knock_entry is not None:
                    channel_values["Knock"] = knock_entry
                    live_channels["Knock"] = knock_entry
                _live_data["last_update_ts"] = now_ts
                if "error" in _live_data:
                    del _live_data["error"]
                # Append to ring buffer for drain endpoint (per-channel granularity)
                _sample_ring.append(entry)
                if knock_entry is not None:
                    _sample_ring.append(knock_entry)
            # Wake SSE listeners immediately instead of waiting for their sleep cycle
            _live_data_event.set()

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
        # Always clear the capturing flag on exit so the frontend can retry
        # starting capture. Without this, a failed discovery (no providers,
        # transient multicast issue, etc.) leaves `capturing=True` stuck and
        # every subsequent /hardware/live/start returns "already_capturing",
        # which silently prevents live data from ever reaching the UI
        # (e.g. VE heatmap cells stay empty on Command Center).
        with _live_data_lock:
            _live_data["capturing"] = False
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
        # Clear sample ring to prevent stale samples from previous session
        _sample_ring.clear()

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
    include_all = _is_truthy_query_param(request.args.get("include_all"))
    return jsonify(_build_live_data_payload(include_all=include_all))


@hardware_bp.route("/hardware/live/drain", methods=["GET"])
def drain_live_samples():
    """
    Drain all accumulated samples from the ring buffer since the last drain.

    This endpoint returns every processed sample (not just the latest value)
    accumulated since the last call, enabling VE cell hit accumulation without
    loss. The ring buffer is cleared after reading.

    Returns:
        JSON with:
        - samples: List of sample dicts (each has name, value, timestamp, etc.)
        - count: Number of samples returned
        - capturing: Current capture status
        - last_update_ts: Timestamp of last sample received
    """
    with _live_data_lock:
        # Copy all samples from the ring and clear it atomically
        samples = list(_sample_ring)
        _sample_ring.clear()
        capturing = _live_data.get("capturing", False)
        last_update_ts = _live_data.get("last_update_ts")

    return jsonify(
        {
            "samples": samples,
            "count": len(samples),
            "capturing": capturing,
            "last_update_ts": last_update_ts,
        }
    )


def _matches_requested_live_channel(name: str, category: str = "", units: str = "") -> bool:
    """Pass-through allowlist for the Command Center live display."""
    raw = str(name or "").strip().lower()
    normalized = (
        raw.replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("(", " ")
        .replace(")", " ")
    )
    padded = f" {normalized} "
    category = str(category or "").strip().lower()
    units = str(units or "").strip().lower()

    # VE is only shown if the hardware/source actually publishes it. Do not
    # derive VE from AFR/RPM/MAP in live channel plumbing.
    if (
        raw == "ve"
        or " volumetric efficiency " in padded
        or " volume efficiency " in padded
        or " vol eff " in padded
        or " ve " in padded
    ):
        return True

    if " rpm " in padded or " engine speed " in padded:
        return True

    if (
        category == "afr"
        and units not in {"v", "volt", "volts"}
    ) or any(
        token in raw
        for token in ("afr", "air/fuel", "air fuel", "a/f", "wideband", "wbo2")
    ):
        return True

    if " lambda " in padded or raw.startswith("lambda"):
        return True

    if (
        units in {"hp", "bhp"}
        or " horsepower " in padded
        or " hp " in padded
        or " bhp " in padded
        or (category == "dyno" and " power " in padded)
    ):
        return True

    if " map " in padded or " manifold absolute pressure " in padded:
        return True

    if " tps " in padded or " throttle position " in padded:
        return True

    if " iat " in padded or " intake air temperature " in padded:
        return True

    if " ect " in padded or " engine temperature " in padded:
        return True

    if " knock " in padded:
        return True

    return False


def _filter_live_display_channels(channels: dict[str, Any]) -> dict[str, Any]:
    """Restrict public live payloads to key tuning channels only."""
    filtered: dict[str, Any] = {}
    seen_names: set[str] = set()

    for key, ch_data in channels.items():
        if isinstance(key, str) and key.startswith("chan_"):
            continue

        if isinstance(ch_data, dict):
            name = str(ch_data.get("name") or key)
            category = str(ch_data.get("category") or "")
            units = str(ch_data.get("units") or "")
        else:
            name = str(key)
            category = ""
            units = ""

        if not _matches_requested_live_channel(name, category, units):
            continue

        # Keep one public entry per display name; provider-scoped/raw aliases
        # remain in _live_data and discovery/debug endpoints for diagnostics.
        dedupe_key = name.strip().lower()
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)
        filtered[key] = ch_data

    return filtered


def _is_truthy_query_param(value: str | None) -> bool:
    """Parse common truthy query-param values."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _computed_live_channel_entry(
    name: str,
    value: float,
    units: str,
    last_update_ts: float | None,
) -> dict[str, Any]:
    try:
        timestamp_ts = float(last_update_ts) if last_update_ts else time.time()
    except Exception:
        timestamp_ts = time.time()

    return {
        "key": f"computed:{name}",
        "provider_id": None,
        "id": None,
        "name": name,
        "value": float(value),
        "timestamp": int(timestamp_ts * 1000),
        "updated_at_ts": time.time(),
        "category": "dyno",
        "units": units,
        "computed": True,
    }


def _build_live_data_payload(include_all: bool = False) -> dict[str, Any]:
    """Shared payload builder for polling + SSE."""
    if _is_simulator_active():
        from api.services.simulation.dyno_simulator import get_simulator

        sim = get_simulator()
        channels = sim.get_channels()
        if not include_all:
            channels = _filter_live_display_channels(channels)
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
            channels.setdefault(
                "Horsepower",
                _computed_live_channel_entry("Horsepower", hp, "HP", last_update_ts),
            )
            channels.setdefault(
                "Torque",
                _computed_live_channel_entry("Torque", tq, "ft-lb", last_update_ts),
            )
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

    if not include_all:
        channels = _filter_live_display_channels(channels)

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
    """Server-Sent Events (SSE) stream for live channel data.

    Uses a threading.Event to push data as soon as it arrives from the
    UDP receive loop, instead of sleeping a fixed 250 ms.  This reduces
    SSE latency from ~250 ms (4 Hz) to near-instant (~20 Hz, matching
    the 50 ms aggregation window).

    The stream pushes two event types:
    - ``data`` (default): The latest channel snapshot for gauge displays.
    - ``samples``: Batch of all accumulated samples since last push, for
      VE hit accumulation and other consumers that need every sample.
    """

    include_all = _is_truthy_query_param(request.args.get("include_all"))

    def _event_stream():
        last_sent_key: tuple[Any, ...] | None = None
        last_keepalive = time.time()
        while True:
            # Block until new data arrives or 50 ms elapses (whichever first).
            # The event is set() by on_sample in _live_capture_loop whenever
            # _live_data is updated.
            _live_data_event.wait(timeout=0.05)
            _live_data_event.clear()

            payload = _build_live_data_payload(include_all=include_all)
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


@hardware_bp.route("/hardware/diag", methods=["GET"])
def live_diag_page():
    """Minimal browser-based diagnostic page for live JetDrive channels."""
    return render_template_string(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JetDrive Live Diagnostic</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f172a;
      --panel: #111827;
      --panel-border: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --ok: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, Segoe UI, Arial, sans-serif;
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 12px;
    }
    .header-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
    }
    .meta {
      color: var(--muted);
      font-size: 0.9rem;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn {
      border: 1px solid #374151;
      background: #1f2937;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 10px;
      cursor: pointer;
      font-size: 0.9rem;
    }
    .btn:hover { background: #293548; }
    .status-chip {
      display: inline-block;
      border-radius: 999px;
      padding: 2px 10px;
      font-size: 0.8rem;
      border: 1px solid #374151;
    }
    .status-ok { color: #4ade80; border-color: #166534; }
    .status-warn { color: #facc15; border-color: #a16207; }
    .status-bad { color: #f87171; border-color: #991b1b; }
    .tiles {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
    }
    .tile {
      border: 1px solid #374151;
      border-radius: 8px;
      padding: 10px;
      min-height: 88px;
    }
    .tile-name {
      color: var(--muted);
      font-size: 0.82rem;
      margin-bottom: 4px;
    }
    .tile-value {
      font-size: 1.45rem;
      font-weight: 700;
      line-height: 1.2;
    }
    .tile-meta {
      font-size: 0.78rem;
      color: var(--muted);
      margin-top: 6px;
    }
    .fresh-ok { border-color: #166534; }
    .fresh-warn { border-color: #a16207; }
    .fresh-bad { border-color: #991b1b; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    th, td {
      border-bottom: 1px solid #1f2937;
      padding: 7px 6px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      color: var(--muted);
      font-weight: 600;
      background: rgba(31, 41, 55, 0.35);
    }
    tr.fresh-ok { background: rgba(22, 163, 74, 0.08); }
    tr.fresh-warn { background: rgba(217, 119, 6, 0.1); }
    tr.fresh-bad { background: rgba(220, 38, 38, 0.1); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .footer-note {
      color: var(--muted);
      font-size: 0.8rem;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="header-row">
        <div>
          <h2 style="margin: 0 0 6px 0;">JetDrive Live Diagnostic</h2>
          <div class="meta" id="meta"></div>
        </div>
        <div>
          <button class="btn" id="startBtn" style="display:none;">Start Capture</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin: 0 0 10px 0;">Canonical Signals</h3>
      <div class="tiles" id="tiles"></div>
    </div>

    <div class="panel">
      <h3 style="margin: 0 0 10px 0;">All Channels</h3>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>ID</th>
            <th>Category</th>
            <th>Units</th>
            <th>Value</th>
            <th>Age (s)</th>
          </tr>
        </thead>
        <tbody id="allRows"></tbody>
      </table>
    </div>

    <div class="footer-note mono">
      Reading: SSE /api/jetdrive/hardware/live/stream?include_all=1 | Snapshot: /api/jetdrive/hardware/channels/discover
    </div>
  </div>

  <script>
    const API_BASE = "/api/jetdrive";
    const LIVE_URL = API_BASE + "/hardware/live/data?include_all=1";
    const STREAM_URL = API_BASE + "/hardware/live/stream?include_all=1";
    const DISCOVER_URL = API_BASE + "/hardware/channels/discover";
    const START_URL = API_BASE + "/hardware/live/start";
    const MAPPING_URL = API_BASE + "/mapping";

    const CANONICAL_SPECS = [
      { key: "rpm", label: "RPM", hints: ["engine rpm", "rpm", "engine speed"] },
      { key: "afr_front", label: "AFR Front", hints: ["afr front", "wbo2 afr front", "front afr"] },
      { key: "afr_rear", label: "AFR Rear", hints: ["afr rear", "wbo2 afr rear", "rear afr"] },
      { key: "afr_combined", label: "AFR Combined", hints: ["afr combined", "air/fuel", "air fuel", "a/f"] },
      { key: "map_kpa", label: "MAP", hints: ["map", "manifold absolute pressure", "manifold"] },
      { key: "tps", label: "TPS", hints: ["throttle position", "tps", "throttle"] },
      { key: "torque", label: "Torque", hints: ["torque"] },
      { key: "power", label: "Power (HP)", hints: ["power", "horsepower", " hp "] },
      { key: "ect", label: "ECT", hints: ["ect", "coolant"] },
      { key: "iat", label: "IAT", hints: ["iat", "intake air"] }
    ];

    let activeMapping = {};
    let mappingLoaded = false;
    let currentPayload = null;
    let sse = null;

    const metaEl = document.getElementById("meta");
    const tilesEl = document.getElementById("tiles");
    const allRowsEl = document.getElementById("allRows");
    const startBtn = document.getElementById("startBtn");

    function asNumber(value) {
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    }

    function channelAgeSeconds(channel, payloadTs) {
      const now = Date.now() / 1000;
      const ts = asNumber(channel?.updated_at_ts) ?? asNumber(payloadTs);
      if (ts === null) return null;
      return Math.max(0, now - ts);
    }

    function freshnessClass(age) {
      if (age === null) return "fresh-bad";
      if (age > 2.0) return "fresh-bad";
      if (age > 0.5) return "fresh-warn";
      return "fresh-ok";
    }

    function formatValue(key, value) {
      const n = asNumber(value);
      if (n === null) return "n/a";
      if (key === "rpm") return String(Math.round(n));
      if (key.startsWith("afr")) return n.toFixed(2);
      if (key === "map_kpa" || key === "tps") return n.toFixed(1);
      if (key === "power" || key === "torque") return n.toFixed(1);
      if (key === "ect" || key === "iat") return n.toFixed(1);
      return n.toFixed(3);
    }

    function formatAge(age) {
      if (age === null) return "n/a";
      return age.toFixed(2);
    }

    function normalizeChannels(channelsObj) {
      const entries = Object.entries(channelsObj || {});
      return entries.map(([key, value]) => {
        if (value && typeof value === "object" && !Array.isArray(value)) {
          return {
            key,
            id: value.id ?? null,
            name: String(value.name ?? key),
            value: value.value,
            category: value.category ?? "",
            units: value.units ?? "",
            updated_at_ts: value.updated_at_ts ?? null
          };
        }
        return {
          key,
          id: null,
          name: String(key),
          value,
          category: "",
          units: "",
          updated_at_ts: null
        };
      });
    }

    function nameMatches(channelName, needle) {
      const hay = " " + String(channelName || "").toLowerCase().replace(/[_\\-()/]/g, " ") + " ";
      const lit = String(needle || "").toLowerCase();
      return hay.includes(" " + lit + " ") || hay.includes(lit);
    }

    function selectByHints(spec, channels, payloadTs) {
      const candidates = channels.filter((ch) => {
        const lower = String(ch.name || "").toLowerCase();
        if (spec.key === "afr_combined") {
          return lower.includes("afr") && !lower.includes("front") && !lower.includes("rear");
        }
        if (spec.key === "power") {
          return lower.includes("power") || lower.includes("horsepower") || lower.includes(" hp ");
        }
        return spec.hints.some((hint) => nameMatches(ch.name, hint));
      });
      if (!candidates.length) return null;
      candidates.sort((a, b) => {
        const ageA = channelAgeSeconds(a, payloadTs);
        const ageB = channelAgeSeconds(b, payloadTs);
        if (ageA === null && ageB === null) return 0;
        if (ageA === null) return 1;
        if (ageB === null) return -1;
        return ageA - ageB;
      });
      return candidates[0];
    }

    function resolveCanonical(spec, channels, payloadTs) {
      const mappedName = activeMapping[spec.key];
      if (mappedName) {
        const mapped = channels.find((ch) => String(ch.name || "").toLowerCase() === String(mappedName).toLowerCase());
        if (mapped) return mapped;
      }
      return selectByHints(spec, channels, payloadTs);
    }

    function renderMeta(payload) {
      const age = channelAgeSeconds({ updated_at_ts: payload.last_update_ts }, payload.last_update_ts);
      const freshness = freshnessClass(age);
      const freshnessLabel = freshness === "fresh-ok" ? "Fresh" : (freshness === "fresh-warn" ? "Aging" : "Stale");
      const captureLabel = payload.capturing ? "capturing" : "stopped";
      const captureClass = payload.capturing ? "status-ok" : "status-bad";
      const freshClass = freshness === "fresh-ok" ? "status-ok" : (freshness === "fresh-warn" ? "status-warn" : "status-bad");
      const provider = payload.provider_name || "Unknown provider";
      const host = payload.provider_host || "n/a";
      metaEl.innerHTML = ""
        + "<span><strong>Provider:</strong> " + provider + "</span>"
        + "<span><strong>Host:</strong> " + host + "</span>"
        + "<span><strong>Channels:</strong> " + (payload.channel_count ?? 0) + "</span>"
        + "<span class='status-chip " + captureClass + "'>" + captureLabel + "</span>"
        + "<span class='status-chip " + freshClass + "'>" + freshnessLabel + " (" + formatAge(age) + "s)</span>";
      startBtn.style.display = payload.capturing ? "none" : "inline-block";
    }

    function renderCanonicalTiles(payload, channels) {
      const cards = [];
      for (const spec of CANONICAL_SPECS) {
        const ch = resolveCanonical(spec, channels, payload.last_update_ts);
        const age = ch ? channelAgeSeconds(ch, payload.last_update_ts) : null;
        const freshness = freshnessClass(age);
        const value = ch ? formatValue(spec.key, ch.value) : "n/a";
        const units = ch?.units ? String(ch.units) : "";
        const source = ch ? String(ch.name || "unknown") : "unmapped";
        cards.push(
          "<div class='tile " + freshness + "'>"
            + "<div class='tile-name'>" + spec.label + "</div>"
            + "<div class='tile-value mono'>" + value + (units ? " " + units : "") + "</div>"
            + "<div class='tile-meta'>source: " + source + "</div>"
            + "<div class='tile-meta'>age: " + formatAge(age) + "s</div>"
          + "</div>"
        );
      }
      tilesEl.innerHTML = cards.join("");
    }

    function renderAllRows(payload, channels) {
      const rows = [...channels];
      rows.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" }));
      const html = rows.map((ch) => {
        const age = channelAgeSeconds(ch, payload.last_update_ts);
        const rowClass = freshnessClass(age);
        const rawValue = ch.value;
        const value = Number.isFinite(Number(rawValue))
          ? Number(rawValue).toFixed(4)
          : String(rawValue ?? "n/a");
        return "<tr class='" + rowClass + "'>"
          + "<td>" + String(ch.name || "") + "</td>"
          + "<td class='mono'>" + String(ch.id ?? "n/a") + "</td>"
          + "<td>" + String(ch.category ?? "") + "</td>"
          + "<td>" + String(ch.units ?? "") + "</td>"
          + "<td class='mono'>" + value + "</td>"
          + "<td class='mono'>" + formatAge(age) + "</td>"
          + "</tr>";
      }).join("");
      allRowsEl.innerHTML = html || "<tr><td colspan='6'>No channels available.</td></tr>";
    }

    async function refreshMappingIfNeeded(payload) {
      if (mappingLoaded) return;
      const providerId = Number(payload?.provider_id);
      const providerHost = String(payload?.provider_host || "");
      if (!Number.isFinite(providerId) || !providerHost) {
        return;
      }
      try {
        const res = await fetch(MAPPING_URL, { cache: "no-store" });
        if (!res.ok) {
          mappingLoaded = true;
          return;
        }
        const body = await res.json();
        const mappings = Array.isArray(body.mappings) ? body.mappings : [];
        const matched = mappings.find((m) => {
          const pidMatch = Number(m.provider_id) === providerId;
          const hostMatch = String(m.host || "") === providerHost;
          return pidMatch && hostMatch;
        });
        if (matched?.channels && typeof matched.channels === "object") {
          const next = {};
          for (const [canonical, entry] of Object.entries(matched.channels)) {
            if (entry && entry.enabled && entry.source_name) {
              next[canonical] = String(entry.source_name);
            }
          }
          activeMapping = next;
        }
      } catch (_err) {
        activeMapping = {};
      } finally {
        mappingLoaded = true;
      }
    }

    function updateFromPayload(payload) {
      currentPayload = payload;
      const channels = normalizeChannels(payload.channels);
      renderMeta(payload);
      renderCanonicalTiles(payload, channels);
      renderAllRows(payload, channels);
    }

    async function loadSnapshotFromDiscover() {
      try {
        const res = await fetch(DISCOVER_URL, { cache: "no-store" });
        if (!res.ok) return;
        const body = await res.json();
        if (!body.success || !Array.isArray(body.channels)) return;
        const fallbackPayload = {
          capturing: false,
          provider_id: null,
          provider_name: null,
          provider_host: null,
          channel_count: body.channel_count || body.channels.length || 0,
          last_update_ts: null,
          channels: Object.fromEntries(
            body.channels.map((ch) => [
              String(ch.name || "unknown"),
              {
                id: ch.id ?? null,
                name: ch.name ?? "unknown",
                value: ch.value,
                category: "",
                units: ch.suggested_config?.units ?? "",
                updated_at_ts: null
              }
            ])
          )
        };
        updateFromPayload(fallbackPayload);
      } catch (_err) {
        // no-op fallback
      }
    }

    async function loadInitialData() {
      await loadSnapshotFromDiscover();
      try {
        const res = await fetch(LIVE_URL, { cache: "no-store" });
        if (!res.ok) return;
        const payload = await res.json();
        await refreshMappingIfNeeded(payload);
        updateFromPayload(payload);
      } catch (_err) {
        // no-op
      }
    }

    function connectStream() {
      if (sse) {
        sse.close();
      }
      sse = new EventSource(STREAM_URL);
      sse.onmessage = async (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (!mappingLoaded) {
            await refreshMappingIfNeeded(payload);
          }
          updateFromPayload(payload);
        } catch (_err) {
          // malformed event ignored
        }
      };
      sse.onerror = () => {
        if (sse && sse.readyState === EventSource.CLOSED) {
          setTimeout(connectStream, 1500);
        }
      };
    }

    startBtn.addEventListener("click", async () => {
      startBtn.disabled = true;
      try {
        await fetch(START_URL, { method: "POST" });
      } catch (_err) {
        // no-op
      } finally {
        startBtn.disabled = false;
      }
    });

    loadInitialData().then(connectStream);
  </script>
</body>
</html>
        """
    )


@hardware_bp.route("/hardware/live/debug", methods=["GET"])
def get_live_debug():
    """Get debug information about live capture status."""
    from api.services.jetdrive.jetdrive_client import (
        JetDriveConfig,
    )
    from api.services.jetdrive.jetdrive_client import (
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
            providers = loop.run_until_complete(
                _discover_providers(config, timeout=5.0)
            )
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
        )
        from api.services.jetdrive.jetdrive_client import (
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
        )
        from api.services.jetdrive.jetdrive_client import (
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
        )
        from api.services.jetdrive.jetdrive_client import (
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
        )
        from api.services.jetdrive.jetdrive_client import (
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


@hardware_bp.route("/hardware/metrics", methods=["GET"])
def pipeline_metrics():
    """Return observability metrics for the entire JetDrive data pipeline.

    Surfaces:
    - UDP packets received / dropped (from sequence-gap tracking in the
      subscribe loop)
    - Aggregation window count / queue depth / queue drops
    - SSE client count (approximate)
    - Sample ring buffer depth and capacity
    - Live capture queue manager statistics
    """
    from api.services.jetdrive.jetdrive_live_queue import get_live_queue_manager
    from api.services.jetdrive.jetdrive_validation import get_validator

    with _live_data_lock:
        capturing = _live_data.get("capturing", False)
        last_update_ts = _live_data.get("last_update_ts")
        ring_depth = len(_sample_ring)
        ring_capacity = _sample_ring.maxlen or 0

    # Queue manager stats (aggregation windows, enqueue rate, drops, etc.)
    queue_mgr = get_live_queue_manager()
    queue_stats = queue_mgr.get_stats()

    # Validator tracks frame-level stats including seq gaps
    validator = get_validator()
    validator_health = validator.get_all_health()

    data_age_seconds: float | None = None
    if last_update_ts:
        try:
            data_age_seconds = round(time.time() - float(last_update_ts), 2)
        except Exception:
            pass

    return jsonify(
        {
            "capturing": capturing,
            "data_age_seconds": data_age_seconds,
            "sample_ring": {
                "depth": ring_depth,
                "capacity": ring_capacity,
                "utilization_pct": (
                    round(ring_depth / ring_capacity * 100, 1) if ring_capacity else 0
                ),
            },
            "queue": queue_stats,
            "validator": validator_health,
        }
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
