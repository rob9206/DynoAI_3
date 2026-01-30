"""
Secure File Index Service.

Maps server-generated file IDs to real file paths, preventing clients
from directly specifying file paths. This eliminates path traversal
vulnerabilities while keeping the API contract clean.

Features:
- TTL-based expiry (default 1 hour)
- Type-tagged entries (log, tune, wp8)
- Thread-safe operations
- In-memory storage (simple, local-only)
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class FileType(str, Enum):
    """Supported file types for indexing."""

    LOG = "log"
    TUNE = "tune"
    WP8 = "wp8"


@dataclass
class IndexedFile:
    """An indexed file entry."""

    file_id: str
    path: Path
    file_type: FileType
    name: str
    size_kb: float
    mtime: float
    created_at: float
    expires_at: float

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > self.expires_at

    def to_api_response(self) -> dict:
        """Convert to API response format (no raw path exposed)."""
        return {
            "id": self.file_id,
            "name": self.name,
            "size_kb": round(self.size_kb, 1),
            "mtime": self.mtime,
            "type": self.file_type.value,
        }


class FileIndex:
    """
    Thread-safe file index mapping IDs to paths.

    Usage:
        index = FileIndex()

        # Register files during discovery
        file_id = index.register(path, FileType.LOG)

        # Later, resolve file_id back to path (validates type)
        path = index.resolve(file_id, expected_type=FileType.LOG)
    """

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._index: dict[str, IndexedFile] = {}
        self._path_to_id: dict[str, str] = {}  # For deduplication
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def register(self, path: Path, file_type: FileType) -> str:
        """
        Register a file and get its ID.

        If the file is already registered and not expired, returns the existing ID.

        Args:
            path: Absolute path to the file
            file_type: Type classification (log, tune, wp8)

        Returns:
            Server-generated file ID

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is not a file
        """
        path = path.resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        path_key = str(path)
        now = time.time()

        with self._lock:
            self._maybe_cleanup()

            # Check for existing non-expired entry
            if path_key in self._path_to_id:
                existing_id = self._path_to_id[path_key]
                if existing_id in self._index:
                    entry = self._index[existing_id]
                    if not entry.is_expired():
                        # Refresh TTL on re-registration
                        entry.expires_at = now + self._ttl
                        return entry.file_id

            # Generate new ID
            file_id = self._generate_id(path)

            # Get file metadata
            stat = path.stat()

            entry = IndexedFile(
                file_id=file_id,
                path=path,
                file_type=file_type,
                name=path.name,
                size_kb=stat.st_size / 1024,
                mtime=stat.st_mtime,
                created_at=now,
                expires_at=now + self._ttl,
            )

            self._index[file_id] = entry
            self._path_to_id[path_key] = file_id

            return file_id

    def resolve(
        self,
        file_id: str,
        expected_type: Optional[FileType] = None,
    ) -> Path:
        """
        Resolve a file ID back to its path.

        Args:
            file_id: The server-issued file ID
            expected_type: If provided, validate the file type matches

        Returns:
            The resolved file path

        Raises:
            KeyError: If file_id not found or expired
            ValueError: If file type doesn't match expected_type
            FileNotFoundError: If the underlying file no longer exists
        """
        with self._lock:
            self._maybe_cleanup()

            if file_id not in self._index:
                raise KeyError(f"File ID not found or expired: {file_id}")

            entry = self._index[file_id]

            if entry.is_expired():
                # Clean up expired entry
                self._remove_entry(file_id)
                raise KeyError(f"File ID expired: {file_id}")

            if expected_type and entry.file_type != expected_type:
                raise ValueError(
                    f"File type mismatch: expected {expected_type.value}, "
                    f"got {entry.file_type.value}"
                )

            # Verify file still exists
            if not entry.path.exists():
                self._remove_entry(file_id)
                raise FileNotFoundError(f"File no longer exists: {entry.name}")

            return entry.path

    def get_entry(self, file_id: str) -> Optional[IndexedFile]:
        """Get the full entry for a file ID (if valid)."""
        with self._lock:
            if file_id not in self._index:
                return None
            entry = self._index[file_id]
            if entry.is_expired():
                self._remove_entry(file_id)
                return None
            return entry

    def list_by_type(self, file_type: FileType) -> list[IndexedFile]:
        """List all non-expired entries of a given type."""
        with self._lock:
            self._maybe_cleanup()
            return [
                entry
                for entry in self._index.values()
                if entry.file_type == file_type and not entry.is_expired()
            ]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._index.clear()
            self._path_to_id.clear()

    def _generate_id(self, path: Path) -> str:
        """Generate a unique, non-guessable file ID."""
        # Use random component + hash of path for uniqueness
        random_part = secrets.token_hex(8)
        path_hash = hashlib.sha256(str(path).encode()).hexdigest()[:8]
        return f"{random_part}{path_hash}"

    def _remove_entry(self, file_id: str) -> None:
        """Remove an entry from the index."""
        if file_id in self._index:
            entry = self._index[file_id]
            path_key = str(entry.path)
            del self._index[file_id]
            if self._path_to_id.get(path_key) == file_id:
                del self._path_to_id[path_key]

    def _maybe_cleanup(self) -> None:
        """Periodically clean up expired entries."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired = [
            file_id for file_id, entry in self._index.items() if entry.is_expired()
        ]
        for file_id in expired:
            self._remove_entry(file_id)


# =============================================================================
# Global Singleton
# =============================================================================

_file_index: Optional[FileIndex] = None
_index_lock = threading.Lock()


def get_file_index() -> FileIndex:
    """Get or create the global FileIndex instance."""
    global _file_index
    with _index_lock:
        if _file_index is None:
            _file_index = FileIndex()
        return _file_index


def reset_file_index() -> None:
    """Reset the global FileIndex (useful for testing)."""
    global _file_index
    with _index_lock:
        if _file_index:
            _file_index.clear()
        _file_index = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "FileIndex",
    "FileType",
    "IndexedFile",
    "get_file_index",
    "reset_file_index",
]
