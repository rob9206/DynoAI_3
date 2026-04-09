"""
DynoAI v3.0 — Calibration Library
==================================

Stores real-world reference calibrations imported from PVV files and blends
them into a hardware-matched seed map for new sessions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray

from .grid_utils import resample_ve_table
from .template_library import HardwareConfig, _compute_similarity

logger = logging.getLogger(__name__)

_FAMILY_ALIASES: Dict[str, str] = {
    "tc_88": "twin_cam",
    "tc_96": "twin_cam",
    "tc_103": "twin_cam",
    "tc_110": "twin_cam",
}

_VE_FRONT_TABLE_NAMES = (
    "VE (MAP based/Front Cyl)",
    "VE (MAP based/Front Cylinder)",
)
_VE_REAR_TABLE_NAMES = (
    "VE (MAP based/Rear Cyl)",
    "VE (MAP based/Rear Cylinder)",
)
_AFR_TABLE_NAMES = (
    "Air-Fuel Ratio",
    "AFR Target",
)


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Serialize payload deterministically for identity hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _source_identity(payload: Dict[str, Any]) -> str:
    """Compute stable source identity for idempotent ingest/upsert."""
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest[:24]


def _inhg_to_kpa(value: float) -> float:
    return round(float(value) * 3.38639, 1)


def _is_rpm_x1000(units: str) -> bool:
    normalized = (units or "").lower().replace(" ", "")
    return "rpmx1000" in normalized or "rpm*1000" in normalized


@dataclass
class CalibrationEntry:
    """
    Stored calibration record.
    """

    calibration_id: str
    config: HardwareConfig
    ve_front: List[List[float]]
    ve_rear: Optional[List[List[float]]]
    afr_targets: Dict[int, float]
    rpm_bins: List[float]
    map_bins: List[float]
    source_pvv: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calibration_id": self.calibration_id,
            "config": self.config.to_dict(),
            "ve_front": self.ve_front,
            "ve_rear": self.ve_rear,
            "afr_targets": {
                str(int(k)): float(v)
                for k, v in self.afr_targets.items()
            },
            "rpm_bins": [float(v) for v in self.rpm_bins],
            "map_bins": [float(v) for v in self.map_bins],
            "source_pvv": self.source_pvv,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationEntry":
        afr_targets_raw = data.get("afr_targets", {})
        afr_targets = {
            int(float(k)): float(v)
            for k, v in afr_targets_raw.items()
        }
        return cls(
            calibration_id=data["calibration_id"],
            config=HardwareConfig.from_dict(data["config"]),
            ve_front=data["ve_front"],
            ve_rear=data.get("ve_rear"),
            afr_targets=afr_targets,
            rpm_bins=[float(v) for v in data["rpm_bins"]],
            map_bins=[float(v) for v in data["map_bins"]],
            source_pvv=str(data.get("source_pvv", "")),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CalibrationMatch:
    """Similarity-scored calibration candidate."""

    calibration_id: str
    config: HardwareConfig
    similarity_score: float
    entry: CalibrationEntry


@dataclass
class BlendedCalibration:
    """Output of blending multiple matched calibrations."""

    ve_front: List[List[float]]
    ve_rear: Optional[List[List[float]]]
    afr_targets: Dict[int, float]
    rpm_bins: List[float]
    map_bins: List[float]
    confidence_map: List[List[int]]
    source_matches: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ve_front": self.ve_front,
            "ve_rear": self.ve_rear,
            "afr_targets": {
                str(int(k)): float(v)
                for k, v in self.afr_targets.items()
            },
            "rpm_bins": self.rpm_bins,
            "map_bins": self.map_bins,
            "confidence_map": self.confidence_map,
            "source_matches": self.source_matches,
        }


class CalibrationBlender:
    """Weighted interpolator for matched calibration entries."""

    @staticmethod
    def blend(
        matches: Sequence[CalibrationMatch],
        target_rpm_bins: Sequence[float],
        target_map_bins: Sequence[float],
    ) -> BlendedCalibration:
        if not matches:
            raise ValueError("No calibration matches provided for blend")

        dst_rpm = np.asarray(target_rpm_bins, dtype=np.float64)
        dst_map = np.asarray(target_map_bins, dtype=np.float64)
        if dst_rpm.size == 0 or dst_map.size == 0:
            raise ValueError("Target RPM/MAP bins must be non-empty")

        shape = (len(dst_rpm), len(dst_map))
        front_sum = np.zeros(shape, dtype=np.float64)
        front_weights = np.zeros(shape, dtype=np.float64)
        confidence = np.zeros(shape, dtype=np.int32)

        rear_sum = np.zeros(shape, dtype=np.float64)
        rear_weights = np.zeros(shape, dtype=np.float64)
        has_rear = False

        afr_sum = np.zeros(len(dst_map), dtype=np.float64)
        afr_weights = np.zeros(len(dst_map), dtype=np.float64)

        source_matches: List[Dict[str, Any]] = []

        for match in matches:
            weight = max(float(match.similarity_score), 0.0) ** 2
            if weight <= 0.0:
                continue

            entry = match.entry
            src_rpm = np.asarray(entry.rpm_bins, dtype=np.float64)
            src_map = np.asarray(entry.map_bins, dtype=np.float64)

            src_front = np.asarray(entry.ve_front, dtype=np.float64)
            if src_front.shape != (len(src_rpm), len(src_map)):
                logger.warning(
                    "Skipping malformed front VE table for calibration %s: shape=%s expected=(%d,%d)",
                    entry.calibration_id,
                    src_front.shape,
                    len(src_rpm),
                    len(src_map),
                )
                continue

            front_resampled = resample_ve_table(
                src_front, src_rpm, src_map, dst_rpm, dst_map
            )
            valid_front = np.isfinite(front_resampled)
            front_sum[valid_front] += front_resampled[valid_front] * weight
            front_weights[valid_front] += weight
            confidence[valid_front] += 1

            if entry.ve_rear:
                src_rear = np.asarray(entry.ve_rear, dtype=np.float64)
                if src_rear.shape == (len(src_rpm), len(src_map)):
                    rear_resampled = resample_ve_table(
                        src_rear, src_rpm, src_map, dst_rpm, dst_map
                    )
                    valid_rear = np.isfinite(rear_resampled)
                    rear_sum[valid_rear] += rear_resampled[valid_rear] * weight
                    rear_weights[valid_rear] += weight
                    has_rear = True

            afr_profile = CalibrationBlender._interpolate_afr_targets(
                entry.afr_targets,
                dst_map,
            )
            if afr_profile is not None:
                valid_afr = np.isfinite(afr_profile)
                afr_sum[valid_afr] += afr_profile[valid_afr] * weight
                afr_weights[valid_afr] += weight

            source_matches.append(
                {
                    "calibration_id": match.calibration_id,
                    "similarity_score": float(match.similarity_score),
                    "weight": float(weight),
                }
            )

        if not np.any(front_weights > 0):
            raise ValueError("Unable to blend: no valid calibration surfaces")

        ve_front = np.divide(
            front_sum,
            front_weights,
            out=np.zeros_like(front_sum),
            where=front_weights > 0,
        )

        ve_rear: Optional[List[List[float]]] = None
        if has_rear and np.any(rear_weights > 0):
            rear = np.divide(
                rear_sum,
                rear_weights,
                out=np.zeros_like(rear_sum),
                where=rear_weights > 0,
            )
            ve_rear = rear.tolist()

        afr_targets: Dict[int, float] = {}
        for idx, map_bin in enumerate(dst_map):
            if afr_weights[idx] <= 0:
                continue
            afr_targets[int(round(float(map_bin)))] = round(
                float(afr_sum[idx] / afr_weights[idx]), 3
            )

        return BlendedCalibration(
            ve_front=ve_front.tolist(),
            ve_rear=ve_rear,
            afr_targets=afr_targets,
            rpm_bins=[float(v) for v in dst_rpm.tolist()],
            map_bins=[float(v) for v in dst_map.tolist()],
            confidence_map=confidence.tolist(),
            source_matches=source_matches,
        )

    @staticmethod
    def _interpolate_afr_targets(
        afr_targets: Dict[int, float],
        target_map_bins: NDArray[np.float64],
    ) -> Optional[NDArray[np.float64]]:
        if not afr_targets:
            return None

        map_keys = sorted(float(k) for k in afr_targets.keys())
        afr_vals = [float(afr_targets[int(k)]) for k in map_keys]
        map_arr = np.asarray(map_keys, dtype=np.float64)
        val_arr = np.asarray(afr_vals, dtype=np.float64)
        return np.interp(target_map_bins, map_arr, val_arr, left=val_arr[0], right=val_arr[-1])


class CalibrationLibrary:
    """
    File-backed library of PVV-derived calibrations.
    """

    def __init__(self, storage_dir: Path):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"
        self._index: List[Dict[str, Any]] = self._load_index()

    def ingest(
        self,
        pvv_path: Path,
        config: HardwareConfig,
        operator: str = "unknown",
        notes: str = "",
    ) -> str:
        """
        Ingest a PVV file and store a normalized calibration entry.
        """
        source_path = Path(pvv_path)
        if not source_path.exists():
            raise FileNotFoundError(f"PVV file not found: {source_path}")

        tables, scalars, source_hint = self._parse_pvv_tables(source_path)

        ve_front_table = self._pick_table(
            tables, exact_names=_VE_FRONT_TABLE_NAMES, contains_terms=("ve", "front")
        )
        if ve_front_table is None:
            raise ValueError("PVV does not contain a MAP-based front VE table")

        rpm_bins, map_bins, ve_front = self._normalize_table(ve_front_table)

        ve_rear: Optional[List[List[float]]] = None
        ve_rear_table = self._pick_table(
            tables, exact_names=_VE_REAR_TABLE_NAMES, contains_terms=("ve", "rear")
        )
        if ve_rear_table is not None:
            rear_rpm, rear_map, rear_values = self._normalize_table(ve_rear_table)
            if rear_values.shape != (len(rpm_bins), len(map_bins)) or not np.allclose(
                rear_rpm, rpm_bins
            ) or not np.allclose(rear_map, map_bins):
                rear_values = resample_ve_table(
                    rear_values,
                    np.asarray(rear_rpm, dtype=np.float64),
                    np.asarray(rear_map, dtype=np.float64),
                    np.asarray(rpm_bins, dtype=np.float64),
                    np.asarray(map_bins, dtype=np.float64),
                )
            ve_rear = rear_values.tolist()

        afr_targets: Dict[int, float] = {}
        afr_table = self._pick_table(
            tables,
            exact_names=_AFR_TABLE_NAMES,
            contains_terms=("air", "fuel"),
        )
        if afr_table is not None:
            afr_rpm, afr_map, afr_values = self._normalize_table(afr_table)
            afr_targets = self._extract_afr_targets(afr_rpm, afr_map, afr_values)

        ingest_ts = time.time()
        source_identity = _source_identity(
            {
                "source_kind": "pvv",
                "source_path": str(source_path.resolve()).lower(),
                "config": config.to_dict(),
                "rpm_bins": [float(v) for v in rpm_bins],
                "map_bins": [float(v) for v in map_bins],
                "ve_front": np.asarray(ve_front, dtype=np.float64).round(4).tolist(),
                "ve_rear": (
                    np.asarray(ve_rear, dtype=np.float64).round(4).tolist()
                    if ve_rear is not None
                    else None
                ),
                "afr_targets": {
                    str(int(k)): round(float(v), 4)
                    for k, v in sorted(afr_targets.items())
                },
            }
        )
        existing = self._find_record_by_source_identity(source_identity)
        calibration_id = (
            str(existing["calibration_id"])
            if existing is not None
            else str(uuid.uuid4())[:12]
        )
        metadata: Dict[str, Any] = {
            "ingested_at": ingest_ts,
            "first_ingested_at": (
                float(existing.get("first_ingested_at", ingest_ts))
                if existing is not None
                else ingest_ts
            ),
            "last_ingested_at": ingest_ts,
            "ingest_count": (
                int(existing.get("ingest_count", 1)) + 1
                if existing is not None
                else 1
            ),
            "operator": operator or "unknown",
            "source_file_name": source_path.name,
            "source_name": source_path.name,
            "source_path": str(source_path.resolve()),
            "source_kind": "pvv",
            "source_identity": source_identity,
            "notes": notes,
            "quality": {
                "has_rear": ve_rear is not None,
                "afr_targets_count": len(afr_targets),
                "rows": len(rpm_bins),
                "cols": len(map_bins),
            },
        }
        if source_hint:
            metadata["source_hint"] = source_hint

        if "Engine Displacement" in scalars:
            metadata["source_displacement_ci"] = float(scalars["Engine Displacement"])

        pvv_calibration_id = self._extract_pvv_calibration_id(tables)
        if pvv_calibration_id:
            metadata["source_calibration_id"] = pvv_calibration_id

        entry = CalibrationEntry(
            calibration_id=calibration_id,
            config=config,
            ve_front=ve_front.tolist(),
            ve_rear=ve_rear,
            afr_targets=afr_targets,
            rpm_bins=rpm_bins,
            map_bins=map_bins,
            source_pvv=str(source_path),
            metadata=metadata,
        )

        rel_path = self._write_entry(entry)
        record = self._build_index_record(
            entry=entry,
            rel_path=rel_path,
            source_name=source_path.name,
            source_path=str(source_path.resolve()),
            source_identity=source_identity,
            source_kind="pvv",
            source_calibration_id=str(metadata.get("source_calibration_id", "") or ""),
        )
        if existing is None:
            self._index.append(record)
        else:
            self._replace_record(calibration_id, record)
        self._save_index()

        logger.info(
            "Calibration ingested: %s (%s, %s x %s)%s",
            calibration_id,
            config.engine_family,
            len(rpm_bins),
            len(map_bins),
            " [upsert]" if existing is not None else "",
        )
        return calibration_id

    def ingest_from_parsed(
        self,
        config: HardwareConfig,
        ve_front: List[List[float]],
        ve_rear: Optional[List[List[float]]],
        afr_targets: Dict[int, float],
        rpm_bins: List[float],
        map_bins: List[float],
        source_name: str = "mastertune",
        notes: str = "",
        operator: str = "parsed_import",
        source_path: str = "",
        source_kind: str = "mastertune_tsv",
        queue_metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ingest calibration data from pre-parsed tables.
        """
        if not rpm_bins or not map_bins:
            raise ValueError("RPM and MAP bins must be non-empty")

        expected_shape = (len(rpm_bins), len(map_bins))
        front_arr = np.asarray(ve_front, dtype=np.float64)
        if front_arr.shape != expected_shape:
            raise ValueError(
                f"Front VE shape {front_arr.shape} does not match expected {expected_shape}"
            )

        rear_values: Optional[List[List[float]]] = None
        if ve_rear is not None:
            rear_arr = np.asarray(ve_rear, dtype=np.float64)
            if rear_arr.shape != expected_shape:
                raise ValueError(
                    f"Rear VE shape {rear_arr.shape} does not match expected {expected_shape}"
                )
            rear_values = rear_arr.tolist()

        normalized_afr = {
            int(float(k)): float(v)
            for k, v in afr_targets.items()
        }

        ingest_ts = time.time()
        source_identity = _source_identity(
            {
                "source_kind": source_kind,
                "source_name": str(source_name),
                "source_path": str(source_path).lower().strip(),
                "config": config.to_dict(),
                "rpm_bins": [float(v) for v in rpm_bins],
                "map_bins": [float(v) for v in map_bins],
                "ve_front": front_arr.round(4).tolist(),
                "ve_rear": rear_values,
                "afr_targets": {
                    str(int(k)): round(float(v), 4)
                    for k, v in sorted(normalized_afr.items())
                },
            }
        )
        existing = self._find_record_by_source_identity(source_identity)
        calibration_id = (
            str(existing["calibration_id"])
            if existing is not None
            else str(uuid.uuid4())[:12]
        )
        metadata: Dict[str, Any] = {
            "ingested_at": ingest_ts,
            "first_ingested_at": (
                float(existing.get("first_ingested_at", ingest_ts))
                if existing is not None
                else ingest_ts
            ),
            "last_ingested_at": ingest_ts,
            "ingest_count": (
                int(existing.get("ingest_count", 1)) + 1
                if existing is not None
                else 1
            ),
            "operator": operator or "parsed_import",
            "source_name": source_name,
            "source_file_name": Path(source_name).name,
            "source_path": source_path,
            "source_kind": source_kind,
            "source_identity": source_identity,
            "notes": notes,
            "quality": {
                "has_rear": rear_values is not None,
                "afr_targets_count": len(normalized_afr),
                "rows": len(rpm_bins),
                "cols": len(map_bins),
            },
        }
        if queue_metadata:
            metadata["queue"] = dict(queue_metadata)
        if provenance:
            metadata["provenance"] = dict(provenance)

        entry = CalibrationEntry(
            calibration_id=calibration_id,
            config=config,
            ve_front=front_arr.tolist(),
            ve_rear=rear_values,
            afr_targets=normalized_afr,
            rpm_bins=[float(v) for v in rpm_bins],
            map_bins=[float(v) for v in map_bins],
            source_pvv=source_name,
            metadata=metadata,
        )

        rel_path = self._write_entry(entry)
        record = self._build_index_record(
            entry=entry,
            rel_path=rel_path,
            source_name=source_name,
            source_path=source_path,
            source_identity=source_identity,
            source_kind=source_kind,
            source_calibration_id=str(metadata.get("source_calibration_id", "") or ""),
        )
        if existing is None:
            self._index.append(record)
        else:
            self._replace_record(calibration_id, record)
        self._save_index()

        logger.info(
            "Parsed calibration ingested: %s (%s, %s x %s)%s",
            calibration_id,
            config.engine_family,
            len(rpm_bins),
            len(map_bins),
            " [upsert]" if existing is not None else "",
        )
        return calibration_id

    def get_entry(self, calibration_id: str) -> CalibrationEntry:
        record = self._find_record(calibration_id)
        if record is None:
            raise KeyError(f"Calibration {calibration_id} not found")

        entry_path = self._dir / record["path"]
        with open(entry_path, "r", encoding="utf-8") as handle:
            return CalibrationEntry.from_dict(json.load(handle))

    def list_entries(
        self,
        engine_family: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        records = self._index
        if engine_family:
            records = [r for r in records if r.get("engine_family") == engine_family]

        records = sorted(records, key=lambda r: float(r.get("ingested_at", 0.0)), reverse=True)
        total = len(records)
        if offset < 0:
            offset = 0
        if limit <= 0:
            sliced = records[offset:]
        else:
            sliced = records[offset: offset + limit]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entries": sliced,
        }

    def find_matches(
        self,
        query: HardwareConfig,
        top_n: int = 5,
        min_similarity: float = 0.0,
    ) -> List[CalibrationMatch]:
        query_family = query.engine_family
        allowed_families = {query_family, _FAMILY_ALIASES.get(query_family, query_family)}
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for record in self._index:
            if record.get("engine_family") not in allowed_families:
                continue
            stored_config = HardwareConfig.from_dict(record.get("config", {}))
            score = _compute_similarity(query, stored_config)
            if score < float(min_similarity):
                continue
            scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)

        matches: List[CalibrationMatch] = []
        for score, record in scored[: max(top_n, 0)]:
            entry = self.get_entry(str(record["calibration_id"]))
            matches.append(
                CalibrationMatch(
                    calibration_id=str(record["calibration_id"]),
                    config=HardwareConfig.from_dict(record["config"]),
                    similarity_score=float(score),
                    entry=entry,
                )
            )
        return matches

    def blend(
        self,
        matches: Sequence[CalibrationMatch],
        target_rpm_bins: Sequence[float],
        target_map_bins: Sequence[float],
    ) -> BlendedCalibration:
        return CalibrationBlender.blend(matches, target_rpm_bins, target_map_bins)

    def count(self, engine_family: Optional[str] = None) -> int:
        if engine_family is None:
            return len(self._index)
        return sum(1 for record in self._index if record.get("engine_family") == engine_family)

    def stats(self) -> Dict[str, Any]:
        by_family: Dict[str, int] = {}
        missing_rear_count = 0
        missing_afr_targets_count = 0
        bad_shape_count = 0
        source_identity_counts: Dict[str, int] = {}
        for record in self._index:
            family = str(record.get("engine_family", "unknown"))
            by_family[family] = by_family.get(family, 0) + 1
            has_rear_value = record.get("has_rear")
            if has_rear_value is None:
                try:
                    has_rear_value = self.get_entry(str(record.get("calibration_id", ""))).ve_rear is not None
                except Exception:
                    has_rear_value = False
            if not bool(has_rear_value):
                missing_rear_count += 1
            afr_targets_count_value = record.get("afr_targets_count")
            if afr_targets_count_value is None:
                try:
                    afr_targets_count_value = len(
                        self.get_entry(str(record.get("calibration_id", ""))).afr_targets
                    )
                except Exception:
                    afr_targets_count_value = 0
            if int(afr_targets_count_value) <= 0:
                missing_afr_targets_count += 1
            rows = int(record.get("rows", 0))
            cols = int(record.get("cols", 0))
            if rows <= 0 or cols <= 0:
                bad_shape_count += 1
            source_identity = str(record.get("source_identity", "")).strip()
            if source_identity:
                source_identity_counts[source_identity] = source_identity_counts.get(source_identity, 0) + 1
        duplicate_source_identities = sum(
            1 for count in source_identity_counts.values() if count > 1
        )
        return {
            "total_entries": len(self._index),
            "by_family": by_family,
            "missing_rear_count": missing_rear_count,
            "missing_afr_targets_count": missing_afr_targets_count,
            "bad_shape_count": bad_shape_count,
            "duplicate_source_identities": duplicate_source_identities,
        }

    def delete(self, calibration_id: str) -> bool:
        record = self._find_record(calibration_id)
        if record is None:
            return False

        entry_path = self._dir / record["path"]
        if entry_path.exists():
            entry_path.unlink()

        self._index = [r for r in self._index if str(r.get("calibration_id")) != calibration_id]
        self._save_index()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _find_record(self, calibration_id: str) -> Optional[Dict[str, Any]]:
        for record in self._index:
            if str(record.get("calibration_id")) == calibration_id:
                return record
        return None

    def _find_record_by_source_identity(self, source_identity: str) -> Optional[Dict[str, Any]]:
        if not source_identity:
            return None
        for record in self._index:
            if str(record.get("source_identity", "")) == source_identity:
                return record
        return None

    def _replace_record(self, calibration_id: str, replacement: Dict[str, Any]) -> None:
        replaced = False
        for idx, record in enumerate(self._index):
            if str(record.get("calibration_id")) == str(calibration_id):
                self._index[idx] = replacement
                replaced = True
                break
        if not replaced:
            self._index.append(replacement)

    def _build_index_record(
        self,
        entry: CalibrationEntry,
        rel_path: Path,
        source_name: str,
        source_path: str,
        source_identity: str,
        source_kind: str,
        source_calibration_id: str = "",
    ) -> Dict[str, Any]:
        quality = entry.metadata.get("quality", {}) if isinstance(entry.metadata, dict) else {}
        return {
            "calibration_id": entry.calibration_id,
            "engine_family": entry.config.engine_family,
            "displacement_ci": entry.config.displacement_ci,
            "config": entry.config.to_dict(),
            "path": rel_path.as_posix(),
            "source_file_name": Path(source_name).name,
            "source_name": source_name,
            "source_path": source_path,
            "source_kind": source_kind,
            "source_identity": source_identity,
            "ingested_at": float(entry.metadata.get("last_ingested_at", entry.metadata.get("ingested_at", time.time()))),
            "first_ingested_at": float(entry.metadata.get("first_ingested_at", entry.metadata.get("ingested_at", time.time()))),
            "ingest_count": int(entry.metadata.get("ingest_count", 1)),
            "source_calibration_id": source_calibration_id or None,
            "has_rear": bool(quality.get("has_rear", entry.ve_rear is not None)),
            "afr_targets_count": int(quality.get("afr_targets_count", len(entry.afr_targets))),
            "rows": int(quality.get("rows", len(entry.rpm_bins))),
            "cols": int(quality.get("cols", len(entry.map_bins))),
        }

    def _write_entry(self, entry: CalibrationEntry) -> Path:
        family_dir = self._dir / entry.config.engine_family
        family_dir.mkdir(parents=True, exist_ok=True)
        entry_path = family_dir / f"{entry.calibration_id}.json"
        with open(entry_path, "w", encoding="utf-8") as handle:
            json.dump(entry.to_dict(), handle, indent=2)
        return entry_path.relative_to(self._dir)

    def _load_index(self) -> List[Dict[str, Any]]:
        if not self._index_path.exists():
            return []
        try:
            with open(self._index_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, list):
                return loaded
            return []
        except (json.JSONDecodeError, OSError):
            logger.warning("Calibration library index is unreadable; starting empty.")
            return []

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as handle:
            json.dump(self._index, handle, indent=2)

    @staticmethod
    def _pick_table(
        tables: Dict[str, Dict[str, Any]],
        exact_names: Sequence[str],
        contains_terms: Sequence[str],
    ) -> Optional[Dict[str, Any]]:
        for name in exact_names:
            if name in tables:
                return tables[name]

        lower_lookup = {key.lower(): key for key in tables.keys()}
        for name in exact_names:
            mapped = lower_lookup.get(name.lower())
            if mapped:
                return tables[mapped]

        for key, table in tables.items():
            key_lower = key.lower()
            if all(term in key_lower for term in contains_terms):
                return table
        return None

    @staticmethod
    def _parse_pvv_tables(
        pvv_path: Path,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, float], str]:
        tree = ET.parse(pvv_path)
        root = tree.getroot()

        source_hint = ""
        try:
            with open(pvv_path, "r", encoding="utf-8", errors="ignore") as handle:
                first_chunk = handle.read(800)
            marker = "Source File Name"
            if marker in first_chunk:
                start = first_chunk.index('"', first_chunk.index(marker)) + 1
                end = first_chunk.index('"', start)
                source_hint = first_chunk[start:end]
        except OSError:
            source_hint = ""

        tables: Dict[str, Dict[str, Any]] = {}
        scalars: Dict[str, float] = {}

        for item in root.findall("Item"):
            name = item.get("name", "")
            columns_el = item.find("Columns")
            rows_el = item.find("Rows")
            if columns_el is None or rows_el is None:
                continue

            col_units = columns_el.get("units", "")
            row_units = rows_el.get("units", "")
            units = item.get("units", "")

            cols: List[float] = []
            for col in columns_el.findall("Col"):
                label = col.get("label")
                if label is None:
                    continue
                try:
                    cols.append(float(label))
                except ValueError:
                    continue

            row_labels: List[float] = []
            values: List[List[float]] = []
            for row in rows_el.findall("Row"):
                label = row.get("label")
                if label is None:
                    continue
                try:
                    row_value = float(label)
                except ValueError:
                    continue

                cells: List[float] = []
                for cell in row.findall("Cell"):
                    value = cell.get("value", "0")
                    try:
                        cells.append(float(value))
                    except ValueError:
                        cells.append(0.0)

                row_labels.append(row_value)
                values.append(cells)

            if not cols or not row_labels or not values:
                continue

            if len(cols) == 1 and len(row_labels) == 1:
                scalars[name] = values[0][0]
                continue

            tables[name] = {
                "name": name,
                "units": units,
                "col_units": col_units,
                "row_units": row_units,
                "cols": cols,
                "rows": row_labels,
                "values": values,
            }

        return tables, scalars, source_hint

    @staticmethod
    def _normalize_map_bins(cols: Sequence[float], units: str) -> List[float]:
        unit_lower = (units or "").lower()
        if "inhg" in unit_lower or ("kpa" not in unit_lower and max(cols, default=0.0) <= 35.0):
            return [_inhg_to_kpa(v) for v in cols]
        return [round(float(v), 1) for v in cols]

    @classmethod
    def _normalize_table(
        cls,
        table: Dict[str, Any],
    ) -> Tuple[List[float], List[float], NDArray[np.float64]]:
        raw_cols = [float(v) for v in table.get("cols", [])]
        raw_rows = [float(v) for v in table.get("rows", [])]
        raw_values = table.get("values", [])

        if not raw_cols or not raw_rows or not raw_values:
            raise ValueError(f"Table {table.get('name', '<unknown>')} is empty")

        row_count = min(len(raw_rows), len(raw_values))
        raw_rows = raw_rows[:row_count]
        raw_values = raw_values[:row_count]

        expected_cols = len(raw_cols)
        normalized_rows: List[float] = []
        normalized_values: List[List[float]] = []
        for row_label, row_cells in zip(raw_rows, raw_values):
            if not row_cells:
                continue
            values_row = [float(v) for v in row_cells[:expected_cols]]
            if len(values_row) < expected_cols:
                values_row.extend([values_row[-1]] * (expected_cols - len(values_row)))
            normalized_rows.append(row_label)
            normalized_values.append(values_row)

        if not normalized_rows:
            raise ValueError(f"Table {table.get('name', '<unknown>')} has no usable rows")

        if _is_rpm_x1000(str(table.get("row_units", ""))):
            normalized_rows = [value * 1000.0 for value in normalized_rows]
        else:
            normalized_rows = [float(round(value, 0)) for value in normalized_rows]

        normalized_cols = cls._normalize_map_bins(raw_cols, str(table.get("col_units", "")))

        # Dedupe map columns while preserving order.
        seen_cols = set()
        keep_col_indices: List[int] = []
        dedup_cols: List[float] = []
        for idx, col in enumerate(normalized_cols):
            key = round(float(col), 3)
            if key in seen_cols:
                continue
            seen_cols.add(key)
            keep_col_indices.append(idx)
            dedup_cols.append(float(col))

        col_filtered_values = [
            [row[idx] for idx in keep_col_indices] for row in normalized_values
        ]

        # Dedupe rows while preserving order.
        seen_rows = set()
        dedup_rows: List[float] = []
        dedup_values: List[List[float]] = []
        for row_label, row_values in zip(normalized_rows, col_filtered_values):
            key = int(round(row_label))
            if key in seen_rows:
                continue
            seen_rows.add(key)
            dedup_rows.append(float(key))
            dedup_values.append(row_values)

        row_order = np.argsort(np.asarray(dedup_rows, dtype=np.float64))
        sorted_rows = [dedup_rows[idx] for idx in row_order]
        sorted_values = [dedup_values[idx] for idx in row_order]

        col_order = np.argsort(np.asarray(dedup_cols, dtype=np.float64))
        sorted_cols = [float(dedup_cols[idx]) for idx in col_order]
        sorted_values = [[row[idx] for idx in col_order] for row in sorted_values]

        return sorted_rows, sorted_cols, np.asarray(sorted_values, dtype=np.float64)

    @staticmethod
    def _extract_afr_targets(
        afr_rpm_bins: Sequence[float],
        afr_map_bins: Sequence[float],
        afr_values: NDArray[np.float64],
        representative_rpm: float = 2500.0,
    ) -> Dict[int, float]:
        if afr_values.size == 0:
            return {}
        rpm_arr = np.asarray(afr_rpm_bins, dtype=np.float64)
        row_idx = int(np.argmin(np.abs(rpm_arr - representative_rpm)))
        row = afr_values[row_idx]

        targets: Dict[int, float] = {}
        for map_bin, value in zip(afr_map_bins, row):
            targets[int(round(float(map_bin)))] = round(float(value), 3)
        return targets

    @staticmethod
    def _extract_pvv_calibration_id(tables: Dict[str, Dict[str, Any]]) -> str:
        table = tables.get("Calibration ID")
        if not table:
            return ""
        values = table.get("values", [])
        if not values or not values[0]:
            return ""
        chars = []
        for value in values[0]:
            try:
                value_int = int(float(value))
            except (TypeError, ValueError):
                continue
            if 32 <= value_int < 127:
                chars.append(chr(value_int))
        return "".join(chars).strip()
