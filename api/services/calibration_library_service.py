"""
Calibration library service layer.

Provides a thin, thread-safe facade around dynoai_v3.calibration_library so
Flask routes remain slim and transport-focused.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from werkzeug.datastructures import FileStorage

from api.config import get_config
from api.errors import ValidationError
from dynoai_v3.calibration_library import CalibrationLibrary
from dynoai_v3.grid_config import GridConfig
from dynoai_v3.template_library import HardwareConfig

_library_lock = threading.Lock()
_library: Optional[CalibrationLibrary] = None
_library_dir: Optional[Path] = None


def _get_library() -> CalibrationLibrary:
    global _library, _library_dir

    cfg = get_config()
    requested_dir = Path(
        getattr(cfg.storage, "calibration_library_folder", "data/calibration_library")
    )

    with _library_lock:
        if _library is None or _library_dir != requested_dir:
            _library = CalibrationLibrary(requested_dir)
            _library_dir = requested_dir
        return _library


def _to_hardware_config(config_dict: Dict[str, Any]) -> HardwareConfig:
    if not isinstance(config_dict, dict):
        raise ValidationError("config must be an object")

    if not config_dict.get("engine_family"):
        raise ValidationError("config.engine_family is required")

    if not config_dict.get("displacement_ci"):
        raise ValidationError("config.displacement_ci is required")

    return HardwareConfig.from_dict(config_dict)


def ingest_calibration(
    file: FileStorage,
    config_dict: Dict[str, Any],
    operator: str = "unknown",
    notes: str = "",
) -> Dict[str, Any]:
    config = _to_hardware_config(config_dict)
    library = _get_library()

    suffix = Path(file.filename or "upload.pvv").suffix or ".pvv"
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
        file.save(str(temp_path))

        calibration_id = library.ingest(
            pvv_path=temp_path,
            config=config,
            operator=operator,
            notes=notes,
        )
        entry = library.get_entry(calibration_id)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    return {
        "calibration_id": calibration_id,
        "engine_family": entry.config.engine_family,
        "displacement_ci": entry.config.displacement_ci,
        "source_pvv": entry.metadata.get("source_file_name", Path(entry.source_pvv).name),
        "source_identity": str(entry.metadata.get("source_identity", "")),
        "grid": {
            "rpm_bins": entry.rpm_bins,
            "map_bins": entry.map_bins,
            "rows": len(entry.rpm_bins),
            "cols": len(entry.map_bins),
        },
        "has_rear": entry.ve_rear is not None,
        "afr_targets_count": len(entry.afr_targets),
        "ingest_count": int(entry.metadata.get("ingest_count", 1)),
    }


def list_calibrations(
    engine_family: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    library = _get_library()
    return library.list_entries(
        engine_family=engine_family,
        limit=limit,
        offset=offset,
    )


def get_calibration(calibration_id: str) -> Dict[str, Any]:
    library = _get_library()
    entry = library.get_entry(calibration_id)
    return entry.to_dict()


def delete_calibration(calibration_id: str) -> bool:
    library = _get_library()
    return library.delete(calibration_id)


def blend_calibration(
    config_dict: Dict[str, Any],
    top_n: int = 5,
    min_similarity: float = 0.0,
) -> Dict[str, Any]:
    config = _to_hardware_config(config_dict)
    library = _get_library()

    if min_similarity < 0.0 or min_similarity > 1.0:
        raise ValidationError("min_similarity must be between 0 and 1")

    matches = library.find_matches(config, top_n=top_n, min_similarity=min_similarity)
    if not matches:
        raise ValidationError(
            (
                f"No matching calibrations found for engine_family={config.engine_family} "
                f"with min_similarity={min_similarity:.2f}"
            )
        )

    grid = GridConfig.resolve(
        engine_family=config.engine_family,
        pvv_rpm_bins=config.rpm_bins,
        pvv_map_bins=config.map_bins,
    )
    blended = library.blend(matches, grid.rpm_bins, grid.map_bins)

    return {
        "engine_family": config.engine_family,
        "match_count": len(matches),
        "min_similarity": min_similarity,
        "matches": [
            {
                "calibration_id": match.calibration_id,
                "similarity_score": match.similarity_score,
                "source_file_name": match.entry.metadata.get("source_file_name", ""),
                "operator": match.entry.metadata.get("operator", "unknown"),
                "source_identity": str(match.entry.metadata.get("source_identity", "")),
            }
            for match in matches
        ],
        **blended.to_dict(),
    }


def get_stats() -> Dict[str, Any]:
    library = _get_library()
    return library.stats()
