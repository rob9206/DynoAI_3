"""Service lifecycle helpers for watch-folder integration."""

from __future__ import annotations

import atexit
import logging
import os
import threading
from typing import Any

from api.services.watch_folder.broadcaster import WatchFolderBroadcaster
from api.services.watch_folder.service import WatcherService

logger = logging.getLogger(__name__)

_SERVICE: WatcherService | None = None
_LOCK = threading.Lock()
_ATEXIT_REGISTERED = False


def _is_enabled() -> bool:
    raw = os.environ.get("DYNOAI_WATCH_FOLDER_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _is_werkzeug_parent_process(app: Any) -> bool:
    if not getattr(app, "debug", False):
        return False
    return os.environ.get("WERKZEUG_RUN_MAIN") != "true"


def get_service() -> WatcherService:
    """Get global watch-folder service singleton."""
    global _SERVICE
    with _LOCK:
        if _SERVICE is None:
            _SERVICE = WatcherService(
                broadcaster=WatchFolderBroadcaster(max_recent=200)
            )
        return _SERVICE


def get_broadcaster() -> WatchFolderBroadcaster:
    """Get singleton broadcaster instance."""
    return get_service().broadcaster


def start_watcher(startup_mode: str = "runtime") -> bool:
    """Start watch-folder service singleton."""
    global _ATEXIT_REGISTERED
    service = get_service()
    started = service.start(startup_mode=startup_mode)
    with _LOCK:
        if started and not _ATEXIT_REGISTERED:
            atexit.register(stop_watcher)
            _ATEXIT_REGISTERED = True
    return started


def maybe_start_watcher(app: Any) -> bool:
    """Conditionally start watcher with guardrails."""
    if not _is_enabled():
        logger.info("watch-folder disabled via DYNOAI_WATCH_FOLDER_ENABLED")
        return False

    if _is_werkzeug_parent_process(app):
        logger.info("watch-folder skip in Werkzeug reloader parent process")
        return False

    logger.warning(
        "watch-folder is scoped to single-process or one-worker deployments for F4"
    )
    return start_watcher(startup_mode="app_start")


def stop_watcher() -> None:
    """Stop singleton watcher service."""
    global _SERVICE
    with _LOCK:
        service = _SERVICE
    if service is not None:
        service.stop()
