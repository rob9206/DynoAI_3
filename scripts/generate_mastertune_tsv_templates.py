"""
Generate TSV template files for MasterTune table ingestion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
API_SERVICES_DIR = ROOT_DIR / "api" / "services"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(API_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(API_SERVICES_DIR))

from external_scrapers.mastertune_parser import parse_mt_header  # noqa: E402  # type: ignore[import-not-found]
from dynoai.core.io_contracts import safe_path  # noqa: E402

DEFAULT_RPM_BINS: List[float] = [
    750,
    1000,
    1125,
    1250,
    1500,
    1750,
    2000,
    2250,
    2500,
    2750,
    3000,
    3250,
    3500,
    3750,
    4000,
    4500,
    5000,
    5500,
    6000,
    6500,
    7000,
]

DEFAULT_MAP_BINS: List[float] = [15, 20, 26, 30, 40, 50, 60, 70, 80, 85, 90, 95, 100]


def _fmt_num(value: float) -> str:
    value_f = float(value)
    if value_f.is_integer():
        return str(int(value_f))
    return f"{value_f:.3f}".rstrip("0").rstrip(".")


def _write_grid(
    path: Path,
    *,
    row_label: str,
    row_bins: Sequence[float],
    col_bins: Sequence[float],
    fill_value: float,
) -> None:
    header = [row_label] + [_fmt_num(v) for v in col_bins]
    lines = ["\t".join(header)]
    for row_bin in row_bins:
        values = [_fmt_num(fill_value) for _ in col_bins]
        lines.append("\t".join([_fmt_num(row_bin), *values]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(
    path: Path,
    *,
    mt_file: Path,
    generated_files: Iterable[Path],
) -> None:
    lines = [
        "# MasterTune TSV Template Pack",
        "",
        f"- Source MT file: `{mt_file}`",
        "",
        "## Usage",
        "",
        "1. Open the matching table in MasterTune.",
        "2. Select full table grid (include row/column bins) and copy.",
        "3. Paste into the corresponding `.tsv` file, replacing template values.",
        "4. Run `scripts/ingest_mastertune_tsv.py` with the filled files.",
        "",
        "## Generated Files",
        "",
    ]
    for file_path in generated_files:
        lines.append(f"- `{file_path.name}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate TSV templates for MasterTune table ingest workflow"
    )
    parser.add_argument("--mt-file", required=True, help="Path to source .MT9/.MT8/.MT7 file")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for generated templates (default: alongside MT file in ./tsv_templates/<mt-stem>)",
    )
    parser.add_argument(
        "--lambda-fill",
        type=float,
        default=1.0,
        help="Default lambda value to prefill lambda template (default: 1.0)",
    )
    parser.add_argument(
        "--ve-fill",
        type=float,
        default=0.0,
        help="Default VE value to prefill VE templates (default: 0.0)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    mt_file = safe_path(args.mt_file, allow_parent_dir=True)
    header = parse_mt_header(mt_file)
    if header is None:
        raise ValueError(f"Could not parse MasterTune header from {mt_file}")

    if args.output_dir:
        output_dir = safe_path(args.output_dir, allow_parent_dir=True)
    else:
        output_dir = mt_file.parent / "tsv_templates" / mt_file.stem
        output_dir = safe_path(str(output_dir), allow_parent_dir=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    ve_front_path = output_dir / "ve_front_map.tsv"
    ve_rear_path = output_dir / "ve_rear_map.tsv"
    lambda_path = output_dir / "lambda_map.tsv"

    _write_grid(
        ve_front_path,
        row_label="RPM",
        row_bins=DEFAULT_RPM_BINS,
        col_bins=DEFAULT_MAP_BINS,
        fill_value=float(args.ve_fill),
    )
    _write_grid(
        ve_rear_path,
        row_label="RPM",
        row_bins=DEFAULT_RPM_BINS,
        col_bins=DEFAULT_MAP_BINS,
        fill_value=float(args.ve_fill),
    )
    _write_grid(
        lambda_path,
        row_label="RPM",
        row_bins=DEFAULT_RPM_BINS,
        col_bins=DEFAULT_MAP_BINS,
        fill_value=float(args.lambda_fill),
    )

    readme_path = output_dir / "README.md"
    _write_readme(
        readme_path,
        mt_file=mt_file,
        generated_files=[ve_front_path, ve_rear_path, lambda_path],
    )

    print("MasterTune TSV templates generated")
    print(f"- Source: {mt_file}")
    print(f"- Output dir: {output_dir}")
    print(f"- Header file name: {header.file_name}")
    print(f"- Application: {header.application}")
    print(f"- Files: {ve_front_path.name}, {ve_rear_path.name}, {lambda_path.name}")


if __name__ == "__main__":
    main()

