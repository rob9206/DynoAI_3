from __future__ import annotations

import json
import socket
import time
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, stream_with_context

from api.services.yourdyno import (
    YourDynoSample,
    get_yourdyno_live_queue_manager,
    reset_yourdyno_live_queue_manager,
)
from api.services.yourdyno.yourdyno_client import YourDynoClientConfig

from ._shared import (
    _live_data,
    _live_data_event,
    _live_data_lock,
    _sample_ring,
    clear_live_buffers,
    get_client,
    mark_status,
)

live_bp = Blueprint("yourdyno_live", __name__)


def _sample_to_channels(sample: YourDynoSample) -> dict[str, dict[str, Any]]:
    channels: dict[str, dict[str, Any]] = {}
    ts = sample.timestamp_ms

    def put(name: str, value: Any, units: str = "") -> None:
        if value is None:
            return
        channels[name] = {
            "name": name,
            "value": value,
            "units": units,
            "timestamp": ts,
            "updated_at_ts": time.time(),
        }

    put("Engine RPM", sample.engine_rpm, "rpm")
    put("Roller RPM", sample.roller_rpm, "rpm")
    put("Horsepower", sample.horsepower, "HP")
    put("Torque", sample.torque_ftlb, "ft-lb")
    put("Wheel Horsepower", sample.horsepower_wheel, "HP")
    put("Wheel Torque", sample.torque_wheel_ftlb, "ft-lb")
    put("AFR", sample.afr, ":1")
    put("AFR Front", sample.afr_front, ":1")
    put("AFR Rear", sample.afr_rear, ":1")
    put("MAP", sample.map_kpa, "kPa")
    put("TPS", sample.tps, "%")
    put("IAT", sample.iat_f, "F")
    put("ECT", sample.ect_f, "F")
    put("Force", sample.force_lbs, "lbs")
    put("Acceleration", sample.acceleration, "g")
    put("Speed", sample.speed_mph, "mph")
    put("Ambient Temp", sample.ambient_temp_f, "F")
    put("Ambient Pressure", sample.ambient_pressure_inhg, "inHg")
    put("Ambient Humidity", sample.ambient_humidity, "%")
    return channels


def _build_live_payload() -> dict[str, Any]:
    with _live_data_lock:
        channels = dict(_live_data.get("channels", {}) or {})
        payload = {
            "capturing": bool(_live_data.get("capturing")),
            "connected": bool(_live_data.get("connected")),
            "status": _live_data.get("status", "idle"),
            "error": _live_data.get("error"),
            "last_update_ts": _live_data.get("last_update_ts"),
            "last_update": _live_data.get("last_update"),
            "channels": channels,
            "channel_count": len(channels),
        }
    return payload


def _yourdyno_sample_to_drain_entries(sample_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert one YourDyno sample dict (from sample.to_dict()) into JetDrive-style
    per-channel drain entries so the frontend VE heatmap and drain parser get
    name/value/timestamp and can accumulate VE cell hits.
    """
    ts = sample_dict.get("timestamp_ms")
    if ts is None:
        return []
    entries: list[dict[str, Any]] = []
    # Channel name and optional alias so frontend lookups (e.g. "MAP kPa", "Engine RPM") work
    channel_specs: list[tuple[str, str, str, list[str] | None]] = [
        ("engine_rpm", "Engine RPM", "rpm", None),
        ("roller_rpm", "Roller RPM", "rpm", None),
        ("horsepower", "Horsepower", "HP", None),
        ("torque_ftlb", "Torque", "ft-lb", None),
        ("horsepower_wheel", "Wheel Horsepower", "HP", None),
        ("torque_wheel_ftlb", "Wheel Torque", "ft-lb", None),
        ("afr", "AFR", ":1", None),
        ("afr_front", "AFR Front", ":1", None),
        ("afr_rear", "AFR Rear", ":1", None),
        ("map_kpa", "MAP", "kPa", ["MAP kPa"]),
        ("tps", "TPS", "%", None),
        ("iat_f", "IAT", "F", None),
        ("ect_f", "ECT", "F", None),
        ("force_lbs", "Force", "lbs", None),
        ("acceleration", "Acceleration", "g", None),
        ("speed_mph", "Speed", "mph", None),
        ("ambient_temp_f", "Ambient Temp", "F", None),
        ("ambient_pressure_inhg", "Ambient Pressure", "inHg", None),
        ("ambient_humidity", "Ambient Humidity", "%", None),
    ]
    for key, name, units, aliases in channel_specs:
        val = sample_dict.get(key)
        if val is None or not isinstance(val, (int, float)):
            continue
        value = float(val)
        entry = {"name": name, "value": value, "timestamp": ts, "units": units}
        entries.append(entry)
        if aliases:
            for alias in aliases:
                entries.append({"name": alias, "value": value, "timestamp": ts, "units": units})
    return entries


@live_bp.route("/discover", methods=["GET"])
def discover_bridge():
    """Check whether DynoAIBridge TCP server is reachable."""
    cfg = YourDynoClientConfig.from_env()
    reachable = False
    error = None
    latency_ms = None

    start = time.time()
    try:
        sock = socket.create_connection(
            (cfg.host, cfg.port),
            timeout=min(cfg.connect_timeout_sec, 1.5),
        )
        sock.close()
        reachable = True
        latency_ms = round((time.time() - start) * 1000.0, 2)
    except Exception as exc:
        error = str(exc)

    return jsonify(
        {
            "success": True,
            "bridge_reachable": reachable,
            "host": cfg.host,
            "port": cfg.port,
            "latency_ms": latency_ms,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
    )


@live_bp.route("/live/start", methods=["POST"])
def start_live_capture():
    with _live_data_lock:
        if _live_data.get("capturing"):
            return jsonify(
                {
                    "status": "already_capturing",
                    "connected": bool(_live_data.get("connected")),
                }
            )
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

    def on_status(status: dict[str, Any]) -> None:
        status_type = str(status.get("type", "unknown"))
        if status_type == "connected":
            mark_status("connected", connected=True)
        elif status_type == "hello":
            mark_status("hello", connected=True)
        elif status_type == "error":
            mark_status(
                "error", connected=False, error=str(status.get("message", "error"))
            )

    client = get_client()
    client.start(on_sample=on_sample, on_status=on_status)

    return jsonify({"status": "started"})


@live_bp.route("/live/stop", methods=["POST"])
def stop_live_capture():
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

    return jsonify({"status": "stopped"})


@live_bp.route("/live/data", methods=["GET"])
def get_live_data():
    return jsonify(_build_live_payload())


@live_bp.route("/live/drain", methods=["GET"])
def drain_live_samples():
    with _live_data_lock:
        raw_samples = list(_sample_ring)
        _sample_ring.clear()
        capturing = bool(_live_data.get("capturing"))
        last_update_ts = _live_data.get("last_update_ts")
    # Expand YourDyno sample dicts into JetDrive-style per-channel entries
    # so the frontend drain parser (name/value/timestamp) and VE heatmap get data.
    samples: list[dict[str, Any]] = []
    for s in raw_samples:
        if isinstance(s, dict) and ("engine_rpm" in s or "timestamp_ms" in s):
            samples.extend(_yourdyno_sample_to_drain_entries(s))
        elif isinstance(s, dict) and "name" in s and "value" in s and "timestamp" in s:
            # Already per-channel (e.g. from a future code path)
            samples.append(s)
    return jsonify(
        {
            "samples": samples,
            "count": len(samples),
            "capturing": capturing,
            "last_update_ts": last_update_ts,
        }
    )


@live_bp.route("/live/stream", methods=["GET"])
def stream_live_data():
    """SSE stream for latest YourDyno channel snapshot."""

    def _event_stream():
        last_sent_key: tuple[Any, ...] | None = None
        last_keepalive = time.time()

        while True:
            _live_data_event.wait(timeout=0.05)
            _live_data_event.clear()

            payload = _build_live_payload()
            key = (
                payload.get("capturing"),
                payload.get("connected"),
                payload.get("status"),
                payload.get("last_update_ts"),
                payload.get("channel_count"),
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


# ---------------------------------------------------------------------------
# JetDrive-compatible aliases
# ---------------------------------------------------------------------------


@live_bp.route("/hardware/monitor/status", methods=["GET"])
def monitor_status_alias():
    """
    Compatibility endpoint for useJetDriveLive.
    """
    with _live_data_lock:
        connected = bool(_live_data.get("connected"))
        channel_count = len(_live_data.get("channels", {}) or {})
        status = _live_data.get("status", "idle")

    provider_name = "DynoAIBridge" if connected else "YourDyno Bridge"
    providers = (
        [
            {
                "provider_id": 1,
                "name": provider_name,
                "host": YourDynoClientConfig.from_env().host,
                "channel_count": channel_count,
                "status": status,
            }
        ]
        if connected
        else []
    )

    return jsonify(
        {
            "running": bool(_live_data.get("capturing")),
            "connected": connected,
            "providers": providers,
            "history": [],
            "last_check": datetime.now().isoformat(),
        }
    )


@live_bp.route("/hardware/monitor/start", methods=["POST"])
def monitor_start_alias():
    return jsonify({"status": "started"})


@live_bp.route("/hardware/monitor/stop", methods=["POST"])
def monitor_stop_alias():
    return jsonify({"status": "stopped"})


@live_bp.route("/hardware/live/start", methods=["POST"])
def live_start_alias():
    return start_live_capture()


@live_bp.route("/hardware/live/stop", methods=["POST"])
def live_stop_alias():
    return stop_live_capture()


@live_bp.route("/hardware/live/data", methods=["GET"])
def live_data_alias():
    return get_live_data()


@live_bp.route("/hardware/live/drain", methods=["GET"])
def live_drain_alias():
    return drain_live_samples()


@live_bp.route("/hardware/live/stream", methods=["GET"])
def live_stream_alias():
    return stream_live_data()


@live_bp.route("/queue/reset", methods=["POST"])
def reset_queue_alias():
    reset_yourdyno_live_queue_manager()
    clear_live_buffers()
    return jsonify({"status": "reset"})
