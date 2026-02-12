"""
JetDrive Auto-Tune – Shared state, helpers, and configuration.

Imported by every sub-blueprint so that module-level singletons
(workflow, live data, simulator flags, network constants, etc.) live
in one canonical place.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import struct
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.services.autotune_workflow import AutoTuneWorkflow

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TuneLab-style analysis configuration
# ---------------------------------------------------------------------------
TUNELAB_CONFIG: dict[str, Any] = {
    "enable_filtering": os.environ.get("DYNOAI_ENABLE_FILTERING", "true").lower()
    == "true",
    "lowpass_rc_ms": float(os.environ.get("DYNOAI_LOWPASS_RC_MS", "500.0")),
    "afr_min": float(os.environ.get("DYNOAI_AFR_MIN", "10.0")),
    "afr_max": float(os.environ.get("DYNOAI_AFR_MAX", "19.0")),
    "exclude_time_ms": float(os.environ.get("DYNOAI_EXCLUDE_TIME_MS", "50.0")),
    "enable_statistical_filter": os.environ.get(
        "DYNOAI_ENABLE_STATISTICAL_FILTER", "true"
    ).lower()
    == "true",
    "sigma_threshold": float(os.environ.get("DYNOAI_SIGMA_THRESHOLD", "2.0")),
    "use_weighted_binning": os.environ.get(
        "DYNOAI_USE_WEIGHTED_BINNING", "true"
    ).lower()
    == "true",
}

# ---------------------------------------------------------------------------
# Autotune workflow singleton
# ---------------------------------------------------------------------------
_workflow: "AutoTuneWorkflow | None" = None


def _get_autotune_types():
    try:
        from api.services.autotune_workflow import AutoTuneWorkflow, DataSource
        from dynoai.core.weighted_binning import LogarithmicWeighting
    except Exception as exc:
        logger.error("Autotune dependencies unavailable: %s", exc, exc_info=True)
        raise RuntimeError(
            "Autotune workflow unavailable. Verify analysis dependencies are installed."
        ) from exc
    return AutoTuneWorkflow, DataSource, LogarithmicWeighting


def get_workflow() -> "AutoTuneWorkflow":
    """Get or create the unified workflow instance with TuneLab features."""
    global _workflow
    if _workflow is None:
        AutoTuneWorkflow, _, LogarithmicWeighting = _get_autotune_types()
        _workflow = AutoTuneWorkflow(
            enable_filtering=TUNELAB_CONFIG["enable_filtering"],
            lowpass_rc_ms=TUNELAB_CONFIG["lowpass_rc_ms"],
            afr_min=TUNELAB_CONFIG["afr_min"],
            afr_max=TUNELAB_CONFIG["afr_max"],
            exclude_time_ms=TUNELAB_CONFIG["exclude_time_ms"],
            enable_statistical_filter=TUNELAB_CONFIG["enable_statistical_filter"],
            sigma_threshold=TUNELAB_CONFIG["sigma_threshold"],
            use_weighted_binning=TUNELAB_CONFIG["use_weighted_binning"],
            weighting_strategy=LogarithmicWeighting(),
        )
        logger.info(
            f"AutoTuneWorkflow initialized with TuneLab features: "
            f"filtering={TUNELAB_CONFIG['enable_filtering']}, "
            f"weighted_binning={TUNELAB_CONFIG['use_weighted_binning']}"
        )
    return _workflow


def reset_workflow() -> None:
    """Reset the workflow instance (e.g., after config change)."""
    global _workflow
    _workflow = None


# ---------------------------------------------------------------------------
# Project root & path helpers
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Get project root directory."""
    # 0) Standalone mode - use user data directory
    if os.environ.get("DYNOAI_STANDALONE") or hasattr(sys, "_MEIPASS"):
        data_dir = Path.home() / "DynoAI"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    # 1) Explicit env override
    env_root = os.getenv("DYNOAI_PROJECT_ROOT") or os.getenv("DYNOAI_ROOT")
    if env_root:
        try:
            p = Path(env_root).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass

    # 2) CWD heuristic
    try:
        cwd = Path.cwd().resolve()
        if (cwd / "api").is_dir():
            return cwd
    except Exception:
        pass

    # 3) Fallback: derive from this file location
    #    ``api/routes/jetdrive/_shared.py`` → 4 parents up
    return Path(__file__).resolve().parent.parent.parent.parent


def sanitize_run_id(run_id: str) -> str:
    """
    Sanitize run_id to prevent path traversal attacks.
    Only allow alphanumeric, underscore, and hyphen characters.
    """
    if not run_id:
        raise ValueError("run_id cannot be empty")
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", run_id)
    sanitized = sanitized.lstrip(".-")
    if not sanitized:
        raise ValueError("Invalid run_id after sanitization")
    return sanitized


def safe_path_in_runs(run_id: str, filename: str) -> Path:
    """
    Create a safe path within the runs directory.
    Validates that the resulting path is within the runs directory.
    """
    project_root = get_project_root()
    runs_dir = project_root / "runs"
    safe_run_id = sanitize_run_id(run_id)
    target_path = (runs_dir / safe_run_id / filename).resolve()
    try:
        target_path.relative_to(runs_dir.resolve())
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {run_id}")
    return target_path


def validate_csv_path(csv_path: str) -> Path:
    """
    Ensure the provided CSV path exists and is constrained to trusted directories.
    """
    project_root = get_project_root()
    allowed_dirs = [project_root / "uploads", project_root / "runs"]
    path = Path(csv_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise ValueError("CSV path not found")
    if not resolved.is_file():
        raise ValueError("CSV path must be a file")
    for allowed in allowed_dirs:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue
    raise ValueError("CSV path must be under uploads/ or runs/")


# ---------------------------------------------------------------------------
# Network / JetDrive constants
# ---------------------------------------------------------------------------

JETDRIVE_MCAST_GROUP = os.getenv("JETDRIVE_MCAST_GROUP", "224.0.2.10")
JETDRIVE_PORT = int(os.getenv("JETDRIVE_PORT", "22344"))
JETDRIVE_IFACE = os.getenv("JETDRIVE_IFACE", "0.0.0.0")


def get_network_interfaces() -> list[dict[str, Any]]:
    """Get available network interfaces."""
    interfaces: list[dict[str, Any]] = []
    try:
        import netifaces

        for iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get("addr", "")
                    if ip:
                        interfaces.append(
                            {
                                "name": iface_name,
                                "ip": ip,
                                "is_loopback": ip.startswith("127."),
                            }
                        )
    except ImportError:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            interfaces.append(
                {"name": "default", "ip": ip, "is_loopback": ip.startswith("127.")}
            )
        except socket.error:
            pass
        interfaces.append({"name": "loopback", "ip": "127.0.0.1", "is_loopback": True})
    return interfaces


def test_multicast_support(interface_ip: str = "0.0.0.0") -> tuple[bool, str]:
    """Test if multicast is supported."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(JETDRIVE_MCAST_GROUP),
            socket.inet_aton(interface_ip),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.close()
        return True, "Multicast join successful"
    except OSError as e:
        return False, f"Multicast error: {e}"
    except Exception as e:
        return False, f"Unknown error: {e}"


def test_port_available(port: int) -> tuple[bool, str]:
    """Test if port is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.close()
        return True, f"Port {port} is available"
    except OSError as e:
        return False, f"Port {port} unavailable: {e}"


# ---------------------------------------------------------------------------
# Live data shared state
# ---------------------------------------------------------------------------

_live_data: dict[str, Any] = {
    "channels": {},
    "last_update_ts": None,
    "last_update": None,
    "capturing": False,
    "provider_id": None,
    "provider_name": None,
    "provider_host": None,
}
_live_data_lock = threading.Lock()

# Event signaled whenever _live_data is updated with new sample data.
# SSE stream waits on this instead of sleeping, enabling near-instant push.
_live_data_event = threading.Event()

# Ring buffer that accumulates all processed sample entries (not just latest value).
# Allows the /live/drain endpoint to return every sample received since last drain,
# enabling VE cell hit accumulation without loss. Uses _live_data_lock for synchronization.
# maxlen=2000 gives ~1-2 seconds of buffer at typical rates (1000-2000 samples/sec).

_sample_ring: deque[dict[str, Any]] = deque(maxlen=2000)

# ---------------------------------------------------------------------------
# Simulator state
# ---------------------------------------------------------------------------

_sim_active: bool = False
_sim_lock = threading.Lock()


def _is_simulator_active() -> bool:
    """Thread-safe check for simulator activity."""
    try:
        env_override = os.getenv("DYNOAI_SIMULATOR_FALLBACK", "").strip().lower()
        if env_override in {"1", "true", "yes", "on"}:
            return True
    except Exception:
        pass
    with _sim_lock:
        return _sim_active


def _set_simulator_active(state: bool) -> None:
    """Thread-safe update for simulator activity flag."""
    global _sim_active
    with _sim_lock:
        _sim_active = state


# ---------------------------------------------------------------------------
# Monitor state (hardware module)
# ---------------------------------------------------------------------------

_monitor_state: dict[str, Any] = {
    "running": False,
    "last_check": None,
    "providers": [],
    "history": [],
}
_monitor_lock = threading.Lock()
