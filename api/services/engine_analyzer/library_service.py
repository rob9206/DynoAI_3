"""
Engine Analyzer component library service.

Handles lazy indexing, caching, and component lookup for PTI files.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from api.errors import NotFoundError, ValidationError
from api.services.parsers.pti_parser import parse_pti_file, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


DEFAULT_LIB_DIR = Path("engineanalyzer")
DEFAULT_CACHE_FILENAME = ".ea_cache.json"


@dataclass
class LibraryStats:
    components: int
    skipped_files: int
    cache_loaded: bool
    scanned_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "components": self.components,
            "skipped_files": self.skipped_files,
            "cache_loaded": self.cache_loaded,
            "scanned_at": self.scanned_at,
        }


class EngineAnalyzerLibrary:
    def __init__(self, lib_dir: Path | None = None) -> None:
        self.lib_dir = (lib_dir or DEFAULT_LIB_DIR).resolve()
        self.cache_path = self.lib_dir / DEFAULT_CACHE_FILENAME
        self._loaded = False
        self._components: list[dict[str, Any]] = []
        self._component_index: dict[str, dict[str, Any]] = {}
        self._skipped_files: list[dict[str, Any]] = []
        self._cache_loaded = False
        self._scanned_at: str | None = None

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._try_load_cache():
            self._loaded = True
            return
        self._scan_library()
        self._loaded = True

    def list_components(
        self, component_type: str | None = None, search: str | None = None
    ) -> list[dict[str, Any]]:
        self.ensure_loaded()
        results = self._components
        if component_type:
            results = [
                item for item in results if item["type"] == component_type.lower()
            ]
        if search:
            search_lower = search.lower()
            results = [
                item
                for item in results
                if search_lower in item.get("name", "").lower()
            ]
        return results

    def get_component(self, component_type: str, name: str) -> dict[str, Any]:
        self.ensure_loaded()
        key = self._make_key(component_type, name)
        component = self._component_index.get(key)
        if not component:
            raise NotFoundError("Component", f"{component_type}:{name}")
        return component

    def get_stats(self) -> LibraryStats:
        self.ensure_loaded()
        return LibraryStats(
            components=len(self._components),
            skipped_files=len(self._skipped_files),
            cache_loaded=self._cache_loaded,
            scanned_at=self._scanned_at,
        )

    def get_skipped_files(self) -> list[dict[str, Any]]:
        self.ensure_loaded()
        return self._skipped_files

    def _scan_library(self) -> None:
        if not self.lib_dir.exists():
            logger.warning("Engine Analyzer library not found: %s", self.lib_dir)
            self._components = []
            self._component_index = {}
            self._skipped_files = []
            self._scanned_at = datetime.now(timezone.utc).isoformat()
            return

        self._components = []
        self._component_index = {}
        self._skipped_files = []

        for path in self._iter_pti_files(self.lib_dir):
            try:
                parsed = parse_pti_file(path)
                component = {
                    "id": self._make_key(parsed.component_type, parsed.spec.name),
                    "type": parsed.component_type,
                    "name": parsed.spec.name,
                    "path": str(path),
                    "spec": parsed.spec.to_dict(),
                }
                self._components.append(component)
                self._component_index[component["id"]] = component
            except ValidationError as exc:
                self._skipped_files.append(
                    {"path": str(path), "reason": str(exc)}
                )
                continue
            except Exception as exc:  # pragma: no cover - robust scanning
                self._skipped_files.append(
                    {"path": str(path), "reason": f"Unexpected error: {exc}"}
                )
                continue

        self._scanned_at = datetime.now(timezone.utc).isoformat()
        self._write_cache()

    def _try_load_cache(self) -> bool:
        if not self.cache_path.exists():
            return False
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            components = payload.get("components", [])
            self._components = components
            self._component_index = {
                item["id"]: item for item in components if "id" in item
            }
            self._skipped_files = payload.get("skipped_files", [])
            self._cache_loaded = True
            self._scanned_at = payload.get("scanned_at")
            return True
        except Exception as exc:
            logger.warning("Failed to load EA cache: %s", exc)
            return False

    def _write_cache(self) -> None:
        try:
            payload = {
                "version": 1,
                "lib_dir": str(self.lib_dir),
                "scanned_at": self._scanned_at,
                "components": self._components,
                "skipped_files": self._skipped_files,
            }
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception as exc:  # pragma: no cover - cache failure tolerated
            logger.warning("Failed to write EA cache: %s", exc)

    @staticmethod
    def _iter_pti_files(base_dir: Path) -> Iterable[Path]:
        for path in base_dir.rglob("*"):
            if path.is_dir():
                if path.name.startswith("."):
                    continue
                continue
            if path.suffix.upper() not in SUPPORTED_EXTENSIONS:
                continue
            if any(part.startswith(".") for part in path.parts):
                continue
            yield path

    @staticmethod
    def _make_key(component_type: str, name: str) -> str:
        return f"{component_type.lower()}:{name.strip().lower()}"


_library: EngineAnalyzerLibrary | None = None


def get_engine_analyzer_library() -> EngineAnalyzerLibrary:
    global _library
    if _library is None:
        env_path = os.environ.get("ENALYZER_LIB_DIR")
        if env_path:
            lib_dir = Path(env_path).resolve()
        else:
            # Default to engineanalyzer folder in project root
            # Try to find it relative to this file's location
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            lib_dir = project_root / "engineanalyzer"
            if not lib_dir.exists():
                # Fallback to current working directory
                lib_dir = Path.cwd() / "engineanalyzer"
        logger.info("Engine Analyzer library path: %s (exists: %s)", lib_dir, lib_dir.exists())
        _library = EngineAnalyzerLibrary(lib_dir=lib_dir)
    return _library
