"""
JetDrive Auto-Tune – Innovate Wideband AFR (DLG-1 / LC-2) Routes.

Sub-blueprint for:
- /innovate/ports
- /innovate/connect
- /innovate/disconnect
- /innovate/status
"""

from __future__ import annotations

import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request

from ._shared import logger

innovate_bp = Blueprint("jetdrive_innovate", __name__)

# ---------------------------------------------------------------------------
# Innovate state (module-private)
# ---------------------------------------------------------------------------

_innovate_lock = threading.Lock()
_innovate_client: Any | None = None
_innovate_port: str | None = None
_innovate_device_type: str | None = None
_innovate_last_error: str | None = None
_innovate_last_samples: dict[int, Any] = {}
_innovate_last_sample_at: float | None = None


def _innovate_parse_device_type(device_type: Any) -> str:
    """Normalize device_type input to one of: 'DLG-1', 'LC-2', 'AUTO'."""
    if not isinstance(device_type, str):
        return "AUTO"
    s = device_type.strip().upper().replace("_", "-")
    if s in {"DLG-1", "DLG1"}:
        return "DLG-1"
    if s in {"LC-2", "LC2"}:
        return "LC-2"
    return "AUTO"


def _innovate_on_sample(sample: Any) -> None:
    """Streaming callback from InnovateClient; caches latest samples."""
    global _innovate_last_samples, _innovate_last_sample_at
    try:
        ch = int(getattr(sample, "channel", 1))
    except Exception:
        ch = 1
    with _innovate_lock:
        _innovate_last_samples[ch] = sample
        _innovate_last_sample_at = time.time()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@innovate_bp.route("/innovate/ports", methods=["GET"])
def innovate_list_ports():
    """List available serial ports for Innovate devices."""
    try:
        from api.services.innovate_client import list_available_ports

        ports = list_available_ports() or []
        simplified: list[dict[str, str]] = []
        for p in ports:
            if not isinstance(p, dict):
                continue
            port = p.get("port")
            if not isinstance(port, str) or not port:
                continue
            desc = p.get("description") if isinstance(p.get("description"), str) else ""
            simplified.append({"port": port, "description": desc})

        return jsonify({"success": True, "ports": simplified})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "ports": []}), 500


@innovate_bp.route("/innovate/connect", methods=["POST"])
def innovate_connect():
    """Connect to an Innovate device (DLG-1/LC-2) and start background streaming."""
    global _innovate_client, _innovate_port, _innovate_device_type, _innovate_last_error
    global _innovate_last_samples, _innovate_last_sample_at

    body = request.get_json(silent=True) or {}
    port = body.get("port")
    if not isinstance(port, str) or not port.strip():
        return (
            jsonify({"success": False, "connected": False, "error": "Missing 'port'"}),
            400,
        )
    port = port.strip()

    dev_type_norm = _innovate_parse_device_type(body.get("device_type"))

    with _innovate_lock:
        _innovate_last_samples = {}
        _innovate_last_sample_at = None
        _innovate_last_error = None

    try:
        from api.services.innovate_client import InnovateClient, InnovateDeviceType

        dev_enum = InnovateDeviceType.AUTO
        if dev_type_norm == "DLG-1":
            dev_enum = InnovateDeviceType.DLG1
        elif dev_type_norm == "LC-2":
            dev_enum = InnovateDeviceType.LC2

        with _innovate_lock:
            old = _innovate_client
            _innovate_client = None
            _innovate_port = None
            _innovate_device_type = None
        if old is not None:
            try:
                old.disconnect()
            except Exception:
                pass

        client = InnovateClient(port=port, device_type=dev_enum)
        ok = client.connect()
        if not ok:
            detail = getattr(client, "last_error", None)
            msg = f"Failed to connect to {port}"
            if isinstance(detail, str) and detail.strip():
                msg = f"{msg}: {detail.strip()}"
            with _innovate_lock:
                _innovate_last_error = msg
            return (
                jsonify({"success": False, "connected": False, "error": msg}),
                200,
            )

        started = False
        try:
            started = bool(client.start_streaming(_innovate_on_sample))
        except Exception as exc:
            logger.warning("Innovate streaming start failed: %s", exc)

        with _innovate_lock:
            _innovate_client = client
            _innovate_port = port
            _innovate_device_type = dev_enum.value
            _innovate_last_error = None

        return jsonify(
            {
                "success": True,
                "connected": True,
                "port": port,
                "device_type": dev_enum.value,
                "streaming": started,
            }
        )

    except ImportError as exc:
        with _innovate_lock:
            _innovate_last_error = str(exc)
        return jsonify({"success": False, "connected": False, "error": str(exc)}), 500
    except Exception as exc:
        with _innovate_lock:
            _innovate_last_error = str(exc)
        return jsonify({"success": False, "connected": False, "error": str(exc)}), 500


@innovate_bp.route("/innovate/disconnect", methods=["POST"])
def innovate_disconnect():
    """Disconnect the active Innovate device (if any)."""
    global _innovate_client, _innovate_port, _innovate_device_type, _innovate_last_error
    global _innovate_last_samples, _innovate_last_sample_at

    with _innovate_lock:
        client = _innovate_client
        _innovate_client = None
        _innovate_port = None
        _innovate_device_type = None
        _innovate_last_samples = {}
        _innovate_last_sample_at = None
        _innovate_last_error = None

    if client is not None:
        try:
            client.disconnect()
        except Exception:
            pass

    return jsonify({"success": True})


@innovate_bp.route("/innovate/status", methods=["GET"])
def innovate_status():
    """Return connection + latest sample status for the Innovate device."""
    with _innovate_lock:
        client = _innovate_client
        port = _innovate_port
        device_type = _innovate_device_type
        last_error = _innovate_last_error
        samples = dict(_innovate_last_samples)
        last_sample_at = _innovate_last_sample_at

    connected = bool(client is not None and getattr(client, "connected", False))
    running = bool(client is not None and getattr(client, "running", False))

    now = time.time()
    streaming = bool(
        connected
        and running
        and last_sample_at is not None
        and (now - float(last_sample_at)) < 2.0
    )

    samples_out: dict[str, Any] = {}
    for ch, s in samples.items():
        try:
            afr = float(getattr(s, "afr", 0.0))
        except Exception:
            afr = 0.0
        try:
            lam = getattr(s, "lambda_value", None)
            lam = float(lam) if lam is not None else None
        except Exception:
            lam = None
        try:
            ts = float(getattr(s, "timestamp", 0.0))
        except Exception:
            ts = 0.0
        samples_out[f"channel_{ch}"] = {"afr": afr, "lambda": lam, "timestamp": ts}

    return jsonify(
        {
            "success": True,
            "connected": connected,
            "streaming": streaming,
            "has_samples": len(samples_out) > 0,
            "port": port,
            "device_type": device_type,
            "error": last_error,
            "samples": samples_out,
        }
    )
