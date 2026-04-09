"""Build a metadata catalog from MasterTune files and library corpus health."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, cast

ROOT_DIR = Path(__file__).resolve().parent.parent
API_SERVICES_DIR = ROOT_DIR / "api" / "services"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(API_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(API_SERVICES_DIR))

from external_scrapers.mastertune_parser import (  # noqa: E402  # type: ignore[import-not-found]
    header_to_hardware_config,
    parse_mt_header,
)

DEFAULT_CAL_DIR = Path(r"C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations")
DEFAULT_LIBRARY_DIR = ROOT_DIR / "data" / "calibration_library"
DEFAULT_OUTPUT = ROOT_DIR / "data" / "mastertune_catalog" / "index.json"
VALID_EXTENSIONS = {".mt7", ".mt8", ".mt9"}


def _scan_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VALID_EXTENSIONS:
            continue
        files.append(path)
    return sorted(files)


def _summarize_library(library_dir: Path) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "library_dir": str(library_dir),
        "index_exists": False,
        "total_entries": 0,
        "by_engine_family": {},
        "missing_rear_count": 0,
        "missing_afr_targets_count": 0,
        "bad_shape_count": 0,
        "duplicate_source_identity_count": 0,
        "duplicate_candidates": [],
    }
    index_path = library_dir / "index.json"
    if not index_path.exists():
        return summary

    summary["index_exists"] = True
    try:
        records = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        summary["read_error"] = f"Failed to read {index_path}"
        return summary
    if not isinstance(records, list):
        summary["read_error"] = "Index JSON is not a list"
        return summary

    by_family: Counter[str] = Counter()
    source_identity_counter: Counter[str] = Counter()
    missing_rear_count = 0
    missing_afr_targets_count = 0
    bad_shape_count = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        family = str(record.get("engine_family", "unknown"))
        by_family[family] += 1

        if not bool(record.get("has_rear", False)):
            missing_rear_count += 1
        if int(record.get("afr_targets_count", 0)) <= 0:
            missing_afr_targets_count += 1
        rows = int(record.get("rows", 0))
        cols = int(record.get("cols", 0))
        if rows <= 0 or cols <= 0:
            bad_shape_count += 1

        source_identity = str(record.get("source_identity", "")).strip()
        if source_identity:
            source_identity_counter[source_identity] += 1

    duplicate_candidates = [
        {"source_identity": identity, "count": count}
        for identity, count in sorted(
            source_identity_counter.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )
        if count > 1
    ]

    summary.update(
        {
            "total_entries": len(records),
            "by_engine_family": dict(by_family),
            "missing_rear_count": missing_rear_count,
            "missing_afr_targets_count": missing_afr_targets_count,
            "bad_shape_count": bad_shape_count,
            "duplicate_source_identity_count": len(duplicate_candidates),
            "duplicate_candidates": duplicate_candidates[:25],
        }
    )
    return summary


def index_mastertune_calibrations(
    calibration_dir: Path,
    output_path: Path,
    library_dir: Path,
) -> Dict[str, Any]:
    calibration_dir = Path(calibration_dir)
    if not calibration_dir.exists():
        raise FileNotFoundError(f"Calibration directory not found: {calibration_dir}")

    files = _scan_files(calibration_dir)
    entries: List[Dict[str, Any]] = []
    parse_failures = 0

    by_engine: Counter[str] = Counter()
    by_displacement: Counter[str] = Counter()
    modified_dates: List[str] = []

    for file_path in files:
        header = parse_mt_header(file_path)
        if header is None:
            parse_failures += 1
            continue

        folder_name = file_path.parent.name
        hardware = header_to_hardware_config(header, folder_name)
        by_engine[hardware.engine_family] += 1
        by_displacement[str(hardware.displacement_ci)] += 1
        if header.modified_date:
            modified_dates.append(header.modified_date)

        entries.append(
            {
                "path": str(file_path),
                "relative_path": str(file_path.relative_to(calibration_dir)),
                "folder": folder_name,
                "header": header.to_dict(),
                "hardware_config": hardware.to_dict(),
            }
        )

    payload: Dict[str, Any] = {
        "calibration_dir": str(calibration_dir),
        "total_files_seen": len(files),
        "parsed_entries": len(entries),
        "parse_failures": parse_failures,
        "by_engine_family": dict(by_engine),
        "by_displacement_ci": dict(by_displacement),
        "modified_date_min": min(modified_dates) if modified_dates else "",
        "modified_date_max": max(modified_dates) if modified_dates else "",
        "library_summary": _summarize_library(Path(library_dir)),
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index MasterTune files and summarize calibration-library corpus health"
    )
    parser.add_argument(
        "--calibration-dir",
        default=str(DEFAULT_CAL_DIR),
        help="Root folder containing .mt7/.mt8/.mt9 files",
    )
    parser.add_argument(
        "--library-dir",
        default=str(DEFAULT_LIBRARY_DIR),
        help="Calibration library directory to summarize",
    )
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    calibration_dir = Path(args.calibration_dir)
    library_dir = Path(args.library_dir)
    output_path = Path(args.output_path)
    payload = index_mastertune_calibrations(calibration_dir, output_path, library_dir)

    print("MasterTune catalog build complete")
    print(f"- Source dir: {payload['calibration_dir']}")
    print(f"- Total files: {payload['total_files_seen']}")
    print(f"- Parsed entries: {payload['parsed_entries']}")
    print(f"- Parse failures: {payload['parse_failures']}")
    print(f"- Output: {output_path}")
    print("- By engine family:")
    by_engine_family = cast(Dict[str, int], payload.get("by_engine_family", {}))
    for family, count in sorted(by_engine_family.items()):
        print(f"  - {family}: {count}")

    lib = cast(Dict[str, Any], payload.get("library_summary", {}))
    print("- Library summary:")
    print(f"  - Entries: {lib.get('total_entries', 0)}")
    print(f"  - Missing rear VE: {lib.get('missing_rear_count', 0)}")
    print(f"  - Missing AFR targets: {lib.get('missing_afr_targets_count', 0)}")
    print(f"  - Bad shape records: {lib.get('bad_shape_count', 0)}")
    print(
        "  - Duplicate source identities: "
        f"{lib.get('duplicate_source_identity_count', 0)}"
    )


if __name__ == "__main__":
    main()

