"""
Ingest one MasterTune calibration using copied TSV table exports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
API_SERVICES_DIR = ROOT_DIR / "api" / "services"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(API_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(API_SERVICES_DIR))

from dynoai_v3.calibration_library import CalibrationLibrary  # noqa: E402
from external_scrapers.mastertune_parser import (  # noqa: E402  # type: ignore[import-not-found]
    ParsedGrid,
    header_to_hardware_config,
    lambda_grid_to_afr_targets,
    parse_mt_header,
    parse_tsv_grid_file,
    resample_grid_to_bins,
)


def _get_default_library_dir() -> Path:
    try:
        from api.config import get_config  # noqa: WPS433 (runtime import for CLI)

        return Path(get_config().storage.calibration_library_folder)
    except Exception:
        return ROOT_DIR / "data" / "calibration_library"


def _bins_match(left: Sequence[float], right: Sequence[float], tol: float = 1e-6) -> bool:
    if len(left) != len(right):
        return False
    return all(abs(a - b) <= tol for a, b in zip(left, right))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest MasterTune TSV tables into CalibrationLibrary"
    )
    parser.add_argument("--mt-file", required=True, help="Path to .MT9/.MT8/.MT7 file")
    parser.add_argument("--ve-front-tsv", required=True, help="Path to VE MAP Front TSV")
    parser.add_argument("--ve-rear-tsv", help="Path to VE MAP Rear TSV")
    parser.add_argument("--lambda-tsv", required=True, help="Path to Lambda TSV")
    parser.add_argument("--stoich", type=float, default=14.68, help="Stoich AFR (default 14.68)")
    parser.add_argument(
        "--library-dir",
        default=str(_get_default_library_dir()),
        help="Calibration library directory",
    )
    parser.add_argument("--notes", default="", help="Optional notes to store")
    parser.add_argument(
        "--representative-rpm",
        type=float,
        default=2500.0,
        help="RPM row used to derive AFR targets from lambda",
    )
    parser.add_argument(
        "--no-interpolate-lambda",
        action="store_true",
        help="Disable lambda MAP-bin interpolation onto VE MAP bins",
    )
    parser.add_argument("--operator", default="dispatch", help="Operator identity for provenance")
    parser.add_argument(
        "--source-kind",
        default="mastertune_tsv",
        help="Logical source kind tag (default: mastertune_tsv)",
    )
    parser.add_argument("--queue-path", default="", help="Queue JSON path (optional provenance)")
    parser.add_argument(
        "--queue-item-index",
        type=int,
        default=-1,
        help="Queue item index (optional provenance)",
    )
    parser.add_argument("--queue-status", default="", help="Queue status (optional provenance)")
    parser.add_argument(
        "--queue-retries",
        type=int,
        default=0,
        help="Queue retry count (optional provenance)",
    )
    parser.add_argument(
        "--quality-status",
        default="pending_audit",
        help="Quality status tag for this ingest (default: pending_audit)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    mt_file = Path(args.mt_file)
    header = parse_mt_header(mt_file)
    if header is None:
        raise ValueError(f"Could not parse MasterTune header from {mt_file}")

    folder_name = mt_file.parent.name
    config = header_to_hardware_config(header, folder_name)

    front_grid = parse_tsv_grid_file(Path(args.ve_front_tsv))
    rear_grid: Optional[ParsedGrid] = None
    rear_resampled = False
    if args.ve_rear_tsv:
        rear_grid = parse_tsv_grid_file(Path(args.ve_rear_tsv))
        if not _bins_match(front_grid.row_bins, rear_grid.row_bins) or not _bins_match(
            front_grid.col_bins, rear_grid.col_bins
        ):
            rear_grid = resample_grid_to_bins(
                rear_grid,
                target_row_bins=front_grid.row_bins,
                target_col_bins=front_grid.col_bins,
            )
            rear_resampled = True

    lambda_grid = parse_tsv_grid_file(Path(args.lambda_tsv))
    afr_targets = lambda_grid_to_afr_targets(
        lambda_grid,
        target_map_bins=front_grid.col_bins,
        representative_rpm=float(args.representative_rpm),
        stoich=float(args.stoich),
        interpolate_map=not bool(args.no_interpolate_lambda),
    )

    library = CalibrationLibrary(Path(args.library_dir))
    resolved_mt = mt_file.resolve()
    source_name = f"mastertune:{resolved_mt.as_posix()}"
    queue_metadata: Dict[str, Any] = {}
    if args.queue_path:
        queue_metadata["path"] = args.queue_path
    if args.queue_item_index >= 0:
        queue_metadata["item_index"] = int(args.queue_item_index)
    if args.queue_status:
        queue_metadata["status"] = args.queue_status
    queue_metadata["retries"] = int(args.queue_retries)
    provenance = {
        "quality_status": str(args.quality_status),
        "import_mode": "tsv",
    }
    note_text = args.notes or f"Imported from TSV using {mt_file.name}"
    calibration_id = library.ingest_from_parsed(
        config=config,
        ve_front=front_grid.values,
        ve_rear=rear_grid.values if rear_grid is not None else None,
        afr_targets=afr_targets,
        rpm_bins=front_grid.row_bins,
        map_bins=front_grid.col_bins,
        source_name=source_name,
        notes=note_text,
        operator=args.operator,
        source_path=str(resolved_mt),
        source_kind=args.source_kind,
        queue_metadata=queue_metadata or None,
        provenance=provenance,
    )
    entry = library.get_entry(calibration_id)

    print("MasterTune TSV ingest complete")
    print(f"- calibration_id: {calibration_id}")
    print(f"- source: {source_name}")
    print(f"- source_identity: {entry.metadata.get('source_identity', '')}")
    print(f"- library_dir: {Path(args.library_dir).resolve()}")
    print(f"- engine_family: {config.engine_family}")
    print(f"- displacement_ci: {config.displacement_ci}")
    print(f"- ve_shape: {len(front_grid.row_bins)}x{len(front_grid.col_bins)}")
    print(f"- afr_bins: {len(afr_targets)}")
    print(f"- ingest_count: {entry.metadata.get('ingest_count', 1)}")
    if rear_resampled:
        print("- rear_grid: resampled to match front VE bins")


if __name__ == "__main__":
    main()
