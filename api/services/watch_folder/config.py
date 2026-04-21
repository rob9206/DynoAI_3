"""Configuration loading for Power Core watch-folder service."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from api.services.powercore_integration import find_powercore_data_dirs

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/watch_folder.yaml")


def _parse_env_folders() -> list[Path]:
    raw = os.environ.get("DYNOAI_WATCH_FOLDERS", "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    return [Path(p) for p in parts]


def _parse_yaml_folders(config_path: Path) -> list[Path]:
    if not config_path.exists():
        logger.info("watch-folder: no watch_folder.yaml; using defaults")
        return []

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("watch-folder: failed to parse %s (%s)", config_path, exc)
        return []

    folders = data.get("folders", [])
    if not isinstance(folders, list):
        logger.warning("watch-folder: config 'folders' must be a list")
        return []

    result: list[Path] = []
    for item in folders:
        if isinstance(item, str) and item.strip():
            result.append(Path(item.strip()))
    return result


def load_watch_folders(config_path: Path | None = None) -> list[Path]:
    """Load watch folder list from defaults + env + optional yaml."""
    path = config_path or DEFAULT_CONFIG_PATH
    combined = list(find_powercore_data_dirs())
    combined.extend(_parse_env_folders())
    combined.extend(_parse_yaml_folders(path))

    deduped: list[Path] = []
    seen: set[str] = set()
    for folder in combined:
        resolved = folder.expanduser().resolve(strict=False)
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists() and resolved.is_dir():
            deduped.append(resolved)
    return deduped
