#!/usr/bin/env python3
"""
Seed the v3 calibration library from a known PVV tune export.

Example:
    python scripts/seed_calibration_library.py --pvv "C:/Users/me/Downloads/tune.pvv"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dynoai_v3.calibration_library import CalibrationLibrary
from dynoai_v3.template_library import HardwareConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a PVV file as a calibration-library entry.",
    )
    parser.add_argument(
        "--pvv",
        required=True,
        help="Path to PVV file to ingest",
    )
    parser.add_argument(
        "--storage-dir",
        default="data/calibration_library",
        help="Calibration library storage directory (default: data/calibration_library)",
    )
    parser.add_argument(
        "--operator",
        default="seed-script",
        help="Operator name stored in metadata",
    )
    parser.add_argument(
        "--notes",
        default="TC110 seed import (high-flow intake + Bassani 2-1).",
        help="Metadata notes for this calibration",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    pvv_path = Path(args.pvv).expanduser().resolve()
    if not pvv_path.exists():
        print(f"[!] PVV file not found: {pvv_path}")
        return 1

    storage_dir = Path(args.storage_dir).expanduser().resolve()
    library = CalibrationLibrary(storage_dir)

    # Seed configuration for the user's 110ci Twin Cam Stage-1 style build.
    config = HardwareConfig(
        engine_family="tc_110",
        displacement_ci=110,
        cam_spec="stock",
        exhaust_type="2into1",
        exhaust_brand="bassani",
        air_cleaner="high_flow",
        tune_platform="pv",
    )

    calibration_id = library.ingest(
        pvv_path=pvv_path,
        config=config,
        operator=args.operator,
        notes=args.notes,
    )
    entry = library.get_entry(calibration_id)

    print("[+] Calibration library seed complete")
    print(f"    id: {calibration_id}")
    print(f"    engine_family: {entry.config.engine_family}")
    print(f"    source: {entry.metadata.get('source_file_name', pvv_path.name)}")
    print(f"    grid: {len(entry.rpm_bins)} x {len(entry.map_bins)}")
    print(f"    library_total_for_family: {library.count(entry.config.engine_family)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
