"""
Hot-folder watcher for DynoAI workspace.

When a vehicle has `watch_folder` set in its profile, this service will
monitor that disk folder and auto-ingest new files into the vehicle's
active tuning session. Files are run through the content sniffer and
routed to base_tune / patches / pulls.

Design notes:
- The watcher is OPT-IN per vehicle (nothing happens unless profile has
  a `watch_folder` path).
- Each watched vehicle must already have at least one tuning session --
  newly arriving files are routed to the active iteration of the most
  recently updated session.
- We debounce by mtime: a file is only ingested once per (path, mtime),
  tracked in memory.
- Failures never bubble out: they're logged. The watcher is a
  best-effort convenience, not the primary ingest path.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except Exception:  # pragma: no cover -- watchdog is optional at import time
    _WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    Observer = None  # type: ignore[assignment]
    FileCreatedEvent = None  # type: ignore[assignment]
    FileModifiedEvent = None  # type: ignore[assignment]

from api.services.ingest.sniffer import classify_upload
from api.services.tuning_workspace import (
    TuningSession,
    TuningWorkspace,
    Vehicle,
    WorkspaceError,
    get_workspace,
)

logger = logging.getLogger(__name__)


SUPPORTED_SUFFIXES = {".wp8", ".pvv", ".pvm", ".txt", ".csv", ".pti"}


@dataclass
class WatchEvent:
    vehicle_id: str
    session_id: str
    iteration_id: Optional[str]
    file_path: str
    file_type: str
    slot: str
    ok: bool
    detail: dict[str, Any]


class WorkspaceWatcher:
    """Thread-safe manager for per-vehicle hot folders."""

    def __init__(
        self,
        workspace: Optional[TuningWorkspace] = None,
        debounce_seconds: float = 1.5,
    ) -> None:
        self._workspace = workspace or get_workspace()
        self._observer: Optional[Any] = None
        self._watches: dict[str, Any] = {}
        self._ingested: set[tuple[str, float]] = set()
        self._lock = threading.RLock()
        self._debounce = debounce_seconds
        self._recent_events: list[WatchEvent] = []
        self._max_history = 200

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return _WATCHDOG_AVAILABLE

    def start(self) -> bool:
        """Start watching all vehicles that have a watch_folder configured."""
        if not _WATCHDOG_AVAILABLE:
            logger.warning("watchdog not installed; hot folder watcher disabled")
            return False
        with self._lock:
            if self._observer is not None:
                return True
            self._observer = Observer()
            self._observer.start()
            for vehicle in self._workspace.list_vehicles():
                if vehicle.watch_folder:
                    self._schedule(vehicle)
            return True

    def stop(self) -> None:
        with self._lock:
            if self._observer is not None:
                try:
                    self._observer.stop()
                    self._observer.join(timeout=5.0)
                except Exception:
                    pass
            self._observer = None
            self._watches.clear()

    def rescan(self) -> int:
        """Re-read profiles and add watches for any new vehicles. Returns count scheduled."""
        if not _WATCHDOG_AVAILABLE:
            return 0
        with self._lock:
            if self._observer is None:
                self.start()
            added = 0
            for vehicle in self._workspace.list_vehicles():
                if vehicle.watch_folder and vehicle.id not in self._watches:
                    if self._schedule(vehicle):
                        added += 1
            return added

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            events = self._recent_events[-limit:]
        return [
            {
                "vehicle_id": e.vehicle_id,
                "session_id": e.session_id,
                "iteration_id": e.iteration_id,
                "file_path": e.file_path,
                "file_type": e.file_type,
                "slot": e.slot,
                "ok": e.ok,
                "detail": e.detail,
            }
            for e in events
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule(self, vehicle: Vehicle) -> bool:
        if not vehicle.watch_folder:
            return False
        folder = Path(vehicle.watch_folder).expanduser()
        if not folder.is_dir():
            logger.warning(
                "watch_folder missing for vehicle %s: %s", vehicle.id, folder
            )
            return False

        handler = _VehicleFolderHandler(self, vehicle.id)
        try:
            watch = self._observer.schedule(handler, str(folder), recursive=True)
        except Exception as exc:
            logger.exception(
                "failed to schedule watch for %s (%s): %s", vehicle.id, folder, exc
            )
            return False
        self._watches[vehicle.id] = watch
        logger.info("watching %s for vehicle %s", folder, vehicle.id)
        return True

    def _handle_file(self, vehicle_id: str, path: Path) -> None:
        """Called by handler when a filesystem event arrives."""
        if not path.is_file():
            return
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        key = (str(path), mtime)
        with self._lock:
            if key in self._ingested:
                return
            self._ingested.add(key)

        time.sleep(self._debounce)

        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.warning("could not read %s: %s", path, exc)
            return

        try:
            classification = classify_upload(data, path.name)
        except Exception as exc:
            logger.exception("sniffer failed for %s", path)
            return

        session = self._active_session_for(vehicle_id)
        if session is None:
            self._record(
                WatchEvent(
                    vehicle_id=vehicle_id,
                    session_id="-",
                    iteration_id=None,
                    file_path=str(path),
                    file_type=classification.get("file_type", "unknown"),
                    slot="rejected",
                    ok=False,
                    detail={"reason": "no active session for vehicle"},
                )
            )
            return

        try:
            iteration = self._workspace.get_active_iteration(vehicle_id, session.id)
        except WorkspaceError as exc:
            self._record(
                WatchEvent(
                    vehicle_id=vehicle_id,
                    session_id=session.id,
                    iteration_id=None,
                    file_path=str(path),
                    file_type=classification.get("file_type", "unknown"),
                    slot="rejected",
                    ok=False,
                    detail={"reason": str(exc)},
                )
            )
            return

        slot = classification.get("routed_to", "pulls")
        ok = True
        try:
            if slot == "base_tune":
                self._workspace.set_base_tune(vehicle_id, session.id, data)
            elif slot == "patches":
                self._workspace.add_patch(
                    vehicle_id, session.id, iteration.id, path.name, data
                )
            elif slot == "pulls":
                self._workspace.add_pull(
                    vehicle_id, session.id, iteration.id, path.name, data
                )
            else:
                ok = False
        except Exception as exc:
            logger.exception("routing failed for %s", path)
            ok = False
            slot = "rejected"

        self._record(
            WatchEvent(
                vehicle_id=vehicle_id,
                session_id=session.id,
                iteration_id=iteration.id,
                file_path=str(path),
                file_type=classification.get("file_type", "unknown"),
                slot=slot,
                ok=ok,
                detail=classification.get("detail", {}),
            )
        )

    def _active_session_for(self, vehicle_id: str) -> Optional[TuningSession]:
        sessions = self._workspace.list_sessions(vehicle_id)
        if not sessions:
            return None
        active = [s for s in sessions if s.status == "active"]
        pool = active or sessions
        return max(pool, key=lambda s: s.updated_at)

    def _record(self, event: WatchEvent) -> None:
        with self._lock:
            self._recent_events.append(event)
            if len(self._recent_events) > self._max_history:
                self._recent_events = self._recent_events[-self._max_history :]


class _VehicleFolderHandler(FileSystemEventHandler):  # type: ignore[misc]
    def __init__(self, watcher: WorkspaceWatcher, vehicle_id: str) -> None:
        super().__init__()
        self._watcher = watcher
        self._vehicle_id = vehicle_id

    def on_created(self, event):  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        try:
            threading.Thread(
                target=self._watcher._handle_file,
                args=(self._vehicle_id, Path(event.src_path)),
                daemon=True,
            ).start()
        except Exception:
            logger.exception("on_created dispatch failed")

    def on_modified(self, event):  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        try:
            threading.Thread(
                target=self._watcher._handle_file,
                args=(self._vehicle_id, Path(event.src_path)),
                daemon=True,
            ).start()
        except Exception:
            logger.exception("on_modified dispatch failed")


# -----------------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------------


_watcher: Optional[WorkspaceWatcher] = None
_watcher_lock = threading.Lock()


def get_watcher() -> WorkspaceWatcher:
    global _watcher
    with _watcher_lock:
        if _watcher is None:
            _watcher = WorkspaceWatcher()
        return _watcher


def reset_watcher() -> None:
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            _watcher.stop()
        _watcher = None
