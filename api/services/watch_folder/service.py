"""Background watch-folder service for Power Core artifacts."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from api.services.parsers.file_index import FileType, get_file_index
from api.services.parsers.wp8_parser import parse_wp8_file
from api.services.powercore_integration import parse_powervision_log
from api.services.watch_folder.broadcaster import WatchFolderBroadcaster
from api.services.watch_folder.config import load_watch_folders

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  # pragma: no cover - depends on optional runtime dependency
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]

MONITORED_EXTENSIONS = {".csv", ".wp8", ".pvv", ".pvm"}
EXT_TO_FILE_TYPE = {
    ".csv": FileType.LOG,
    ".wp8": FileType.WP8,
    ".pvv": FileType.TUNE,
    ".pvm": FileType.TUNE,
}
DEDUP_SECONDS = 5.0
STABILITY_DELAY_SECONDS = 0.5

FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000


def _ensure_watch_logger() -> logging.Logger:
    logger = logging.getLogger("api.watch_folder")
    logger.setLevel(logging.INFO)
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "watch_folder.log"
    has_handler = any(
        isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == log_path.resolve()
        for h in logger.handlers
    )
    if not has_handler:
        handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


class _WatchEventHandler(FileSystemEventHandler):
    """Watchdog event adapter."""

    def __init__(self, service: "WatcherService"):
        self._service = service

    def on_created(self, event: Any) -> None:  # pragma: no cover - integration behavior
        self._service.handle_path(Path(event.src_path), source="watchdog")

    def on_modified(self, event: Any) -> None:  # pragma: no cover - integration behavior
        self._service.handle_path(Path(event.src_path), source="watchdog")


class WatcherService:
    """Coordinates filesystem watching, file registration, parsing, and SSE updates."""

    def __init__(
        self,
        broadcaster: WatchFolderBroadcaster | None = None,
    ):
        self._logger = _ensure_watch_logger()
        self._broadcaster = broadcaster or WatchFolderBroadcaster(max_recent=200)
        self._lock = threading.RLock()
        self._dedupe_lock = threading.Lock()
        self._last_seen: dict[str, float] = {}
        self._observer: Any = None
        self._folders: list[Path] = []
        self._running = False
        self._startup_mode = "not_started"
        self._disabled_reason: str | None = None

    def start(self, startup_mode: str = "runtime") -> bool:
        """Start watcher if watchdog and folders are available."""
        with self._lock:
            if self._running:
                return True

            self._folders = load_watch_folders()
            self._startup_mode = startup_mode

            if Observer is None:
                self._disabled_reason = "watchdog dependency unavailable"
                self._logger.warning(self._disabled_reason)
                return False

            if not self._folders:
                self._disabled_reason = "no watch folders found"
                self._logger.warning(self._disabled_reason)
                return False

            observer = Observer()
            handler = _WatchEventHandler(self)
            for folder in self._folders:
                observer.schedule(handler, str(folder), recursive=True)
            observer.start()

            self._observer = observer
            self._running = True
            self._disabled_reason = None
            self._logger.info(
                "watch-folder started mode=%s folders=%s",
                startup_mode,
                [str(p) for p in self._folders],
            )
            return True

    def stop(self) -> None:
        """Stop watcher threads."""
        with self._lock:
            observer = self._observer
            self._observer = None
            self._running = False
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)

    def handle_path(
        self,
        path: Path,
        source: str = "watchdog",
        dedupe: bool = True,
    ) -> dict[str, Any] | None:
        """Process one matching file path and return payload if emitted."""
        if not path.exists() or not path.is_file():
            return None

        ext = path.suffix.lower()
        if ext not in MONITORED_EXTENSIONS:
            return None

        resolved = path.resolve(strict=False)
        path_key = str(resolved).lower()

        if dedupe and self._is_duplicate(path_key):
            return None

        if self._is_placeholder_stub(resolved):
            self._logger.info("placeholder, skipping path=%s", resolved)
            return None

        if not self._is_stable(resolved):
            return None

        file_type = EXT_TO_FILE_TYPE[ext]
        parse_ok = True
        parse_detail = "ok"
        file_id: str | None = None

        try:
            file_id = get_file_index().register(resolved, file_type)
        except Exception as exc:
            parse_ok = False
            parse_detail = f"register_failed: {exc}"

        if parse_ok:
            try:
                if ext == ".csv":
                    parsed = parse_powervision_log(str(resolved))
                    signal_count = len(parsed.signals)
                    row_count = len(parsed.data)
                    if signal_count <= 0 or row_count <= 0:
                        parse_ok = False
                        parse_detail = (
                            "parse_failed: empty_or_incomplete_log "
                            f"signals={signal_count} rows={row_count}"
                        )
                    else:
                        parse_detail = f"signals={signal_count} rows={row_count}"
                elif ext == ".wp8":
                    parsed_wp8 = parse_wp8_file(str(resolved))
                    parse_detail = f"channels={len(parsed_wp8.channels)}"
                else:
                    parse_detail = "registered_only"
            except Exception as exc:
                parse_ok = False
                parse_detail = f"parse_failed: {exc}"

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "path": str(resolved),
            "file_type": file_type.value,
            "file_id": file_id,
            "parse_ok": parse_ok,
            "parse_detail": parse_detail,
        }
        self._logger.info("%s", json.dumps(payload, default=str))
        self._broadcaster.broadcast(payload)
        return payload

    def rescan(self, folder: Path, limit: int = 50) -> dict[str, Any]:
        """Rescan one configured folder (bounded)."""
        configured = {str(p.resolve(strict=False)).lower() for p in self._folders}
        target = folder.resolve(strict=False)
        if str(target).lower() not in configured:
            raise ValueError("folder is not configured for watch service")

        bounded_limit = max(1, min(limit, 200))
        all_matches: list[Path] = []
        for ext in MONITORED_EXTENSIONS:
            all_matches.extend(target.rglob(f"*{ext}"))
        all_matches = sorted(
            [p for p in all_matches if p.exists() and p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        selected = all_matches[:bounded_limit]

        processed = 0
        parse_failed = 0
        skipped = 0
        for file_path in selected:
            payload = self.handle_path(file_path, source="rescan", dedupe=False)
            if payload is None:
                skipped += 1
                continue
            processed += 1
            if not payload.get("parse_ok", False):
                parse_failed += 1

        return {
            "folder": str(target),
            "requested_limit": limit,
            "effective_limit": bounded_limit,
            "selected_files": len(selected),
            "processed": processed,
            "parse_failed": parse_failed,
            "skipped": skipped,
        }

    def status(self) -> dict[str, Any]:
        """Return service status."""
        broadcaster_status = self._broadcaster.status()
        return {
            "running": self._running,
            "startup_mode": self._startup_mode,
            "disabled_reason": self._disabled_reason,
            "folders": [str(p) for p in self._folders],
            **broadcaster_status,
        }

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent watch events."""
        return self._broadcaster.recent(limit=limit)

    def stream(self):
        """Yield SSE events for subscribers."""
        return self._broadcaster.subscribe()

    @property
    def folders(self) -> list[Path]:
        return list(self._folders)

    @property
    def broadcaster(self) -> WatchFolderBroadcaster:
        return self._broadcaster

    @staticmethod
    def _is_stable(path: Path) -> bool:
        try:
            first_size = path.stat().st_size
            time.sleep(STABILITY_DELAY_SECONDS)
            second_size = path.stat().st_size
            return first_size == second_size
        except OSError:
            return False

    @staticmethod
    def _is_placeholder_stub(path: Path) -> bool:
        if os.name != "nt":
            return False
        try:
            stat_info = path.stat()
        except OSError:
            return False
        attrs = getattr(stat_info, "st_file_attributes", 0)
        if attrs & FILE_ATTRIBUTE_RECALL_ON_OPEN:
            return True
        if attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS:
            return True
        if (attrs & FILE_ATTRIBUTE_REPARSE_POINT) and stat_info.st_size == 0:
            return True
        return False

    def _is_duplicate(self, path_key: str) -> bool:
        now = time.time()
        with self._dedupe_lock:
            last = self._last_seen.get(path_key)
            self._last_seen[path_key] = now
        return bool(last and (now - last) < DEDUP_SECONDS)

