"""
Backfill calibration library index records with quality/provenance fields.

Reads each stored calibration entry JSON and updates the corresponding
index record with missing fields (has_rear, afr_targets_count, rows, cols,
source_identity, source_kind, etc.).

Usage::

    python scripts/backfill_calibration_index.py
    python scripts/backfill_calibration_index.py --library-dir data/calibration_library --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _source_identity(entry_data: Dict[str, Any]) -> str:
    payload = {
        "ve_front": entry_data.get("ve_front", []),
        "ve_rear": entry_data.get("ve_rear"),
        "afr_targets": entry_data.get("afr_targets", {}),
        "rpm_bins": entry_data.get("rpm_bins", []),
        "map_bins": entry_data.get("map_bins", []),
        "config": entry_data.get("config", {}),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest[:24]


def backfill(library_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    index_path = library_dir / "index.json"
    if not index_path.exists():
        return {"error": "index.json not found", "library_dir": str(library_dir)}

    with open(index_path, "r", encoding="utf-8") as f:
        index: List[Dict[str, Any]] = json.load(f)

    updated = 0
    errors = 0
    already_complete = 0

    for record in index:
        needs_update = (
            record.get("has_rear") is None
            or record.get("afr_targets_count") is None
            or record.get("rows") is None
            or record.get("cols") is None
            or record.get("source_identity") is None
        )
        if not needs_update:
            already_complete += 1
            continue

        entry_rel_path = record.get("path", "")
        entry_path = library_dir / entry_rel_path
        if not entry_path.exists():
            errors += 1
            continue

        try:
            with open(entry_path, "r", encoding="utf-8") as f:
                entry_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            errors += 1
            continue

        ve_rear = entry_data.get("ve_rear")
        afr_targets = entry_data.get("afr_targets", {})
        rpm_bins = entry_data.get("rpm_bins", [])
        map_bins = entry_data.get("map_bins", [])
        metadata = entry_data.get("metadata", {})

        if record.get("has_rear") is None:
            record["has_rear"] = ve_rear is not None and len(ve_rear) > 0
        if record.get("afr_targets_count") is None:
            record["afr_targets_count"] = len(afr_targets)
        if record.get("rows") is None:
            record["rows"] = len(rpm_bins)
        if record.get("cols") is None:
            record["cols"] = len(map_bins)
        if record.get("source_identity") is None:
            record["source_identity"] = _source_identity(entry_data)
        if record.get("source_kind") is None:
            record["source_kind"] = metadata.get("source_kind", "pvv_import")
        if record.get("first_ingested_at") is None:
            record["first_ingested_at"] = float(
                metadata.get("first_ingested_at", metadata.get("ingested_at", time.time()))
            )
        if record.get("ingest_count") is None:
            record["ingest_count"] = int(metadata.get("ingest_count", 1))

        updated += 1

    if not dry_run and updated > 0:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    return {
        "library_dir": str(library_dir),
        "total_records": len(index),
        "updated": updated,
        "already_complete": already_complete,
        "errors": errors,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill calibration library index with quality fields")
    parser.add_argument(
        "--library-dir",
        default=str(ROOT_DIR / "data" / "calibration_library"),
        help="Path to calibration library directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing changes")
    args = parser.parse_args()

    result = backfill(Path(args.library_dir), dry_run=args.dry_run)
    mode = "DRY RUN" if result.get("dry_run") else "APPLIED"
    print(f"\n[{mode}] Backfill result")
    for k, v in result.items():
        if k != "dry_run":
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
