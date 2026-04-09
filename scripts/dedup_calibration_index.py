"""
Deduplicate calibration library index by source_identity.

Keeps only one entry per unique source_identity (the most recently
ingested), removes the others from the index and deletes their JSON files.

Usage::

    python scripts/dedup_calibration_index.py --dry-run
    python scripts/dedup_calibration_index.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent


def dedup(library_dir: Path, dry_run: bool = True) -> Dict[str, Any]:
    index_path = library_dir / "index.json"
    if not index_path.exists():
        return {"error": "index.json not found"}

    with open(index_path, "r", encoding="utf-8") as f:
        index: List[Dict[str, Any]] = json.load(f)

    by_si: Dict[str, List[Dict[str, Any]]] = {}
    no_si: List[Dict[str, Any]] = []
    for record in index:
        si = (record.get("source_identity") or "").strip()
        if not si:
            no_si.append(record)
            continue
        by_si.setdefault(si, []).append(record)

    keep: List[Dict[str, Any]] = list(no_si)
    removed: List[Dict[str, Any]] = []

    for si, records in by_si.items():
        records.sort(key=lambda r: float(r.get("ingested_at", 0)), reverse=True)
        winner = records[0]
        winner["ingest_count"] = max(int(winner.get("ingest_count", 1)), len(records))
        keep.append(winner)
        for loser in records[1:]:
            removed.append(loser)

    removed_files: List[str] = []
    if not dry_run:
        for r in removed:
            entry_path = library_dir / r.get("path", "")
            if entry_path.exists():
                entry_path.unlink()
                removed_files.append(str(entry_path))

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(keep, f, indent=2)

    return {
        "library_dir": str(library_dir),
        "original_count": len(index),
        "kept": len(keep),
        "removed": len(removed),
        "no_source_identity": len(no_si),
        "dry_run": dry_run,
        "removed_files_count": len(removed_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate calibration library index by source_identity")
    parser.add_argument(
        "--library-dir",
        default=str(ROOT_DIR / "data" / "calibration_library"),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    result = dedup(Path(args.library_dir), dry_run=args.dry_run)
    label = "DRY RUN" if result.get("dry_run") else "APPLIED"
    print(f"\n[{label}] Dedup result")
    for k, v in result.items():
        if k != "dry_run":
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
