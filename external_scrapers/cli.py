from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List

from external_scrapers import get_stdout_logger
from external_scrapers.curve_ocr import annotate_meta_with_ocr
from external_scrapers.dyno_models import (
    META_FIELD_ORDER,
    DynoChartMeta,
    meta_from_row,
    meta_to_row,
)
from external_scrapers.dynojet_scraper import run_dynojet_scrape
from external_scrapers.fuelmoto_university_scraper import run_fuelmoto_scrape
from external_scrapers.winpep_synthesizer import (
    build_curve_spec,
    generate_synthetic_pull,
    save_winpep_csv,
)
from io_contracts import safe_path

logger = get_stdout_logger(__name__)


def _load_index(path: str) -> List[DynoChartMeta]:
    safe = safe_path(path)
    with safe.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [meta_from_row(row) for row in reader]


def _write_index(path: str, metas: Iterable[DynoChartMeta]) -> None:
    safe = safe_path(path)
    safe.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f for f in META_FIELD_ORDER if f != "notes"]
    with safe.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for meta in metas:
            writer.writerow(meta_to_row(meta, include_notes=False))


def cmd_scrape_fuelmoto(args: argparse.Namespace) -> None:
    run_fuelmoto_scrape(args.index_out, images_dir=args.images_dir)
    metas = _load_index(args.index_out)
    metas = annotate_meta_with_ocr(metas)
    _write_index(args.index_out, metas)
    logger.info("Fuel Moto scrape + OCR complete: %d entries", len(metas))


def cmd_scrape_dynojet(args: argparse.Namespace) -> None:
    run_dynojet_scrape(
        listing_urls=args.listing_url,
        output_index_csv=args.index_out,
        images_dir=args.images_dir,
    )
    logger.info("Dynojet scrape complete: %s", args.index_out)


def cmd_synthesize_winpep(args: argparse.Namespace) -> None:
    metas = _load_index(args.index_csv)
    filtered = (
        [m for m in metas if m.source == args.source]
        if args.source in {"fuelmoto", "dynojet"}
        else metas
    )
    written = 0
    for meta in filtered:
        spec = build_curve_spec(meta)
        if not spec:
            logger.info("Skipping %s (missing peak data)", meta.id)
            continue
        df = generate_synthetic_pull(spec)
        save_winpep_csv(df, meta, args.output_dir)
        written += 1
    logger.info("Synthetic WinPEP generation complete: %d runs", written)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="External dyno scraper + generator CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fuel = subparsers.add_parser(
        "scrape-fuelmoto", help="Scrape Fuel Moto University charts"
    )
    fuel.add_argument("--index-out", required=True, help="Path to write index CSV")
    fuel.add_argument(
        "--images-dir",
        default=None,
        help="Directory for chart images (defaults to external/fuelmoto/images)",
    )
    fuel.set_defaults(func=cmd_scrape_fuelmoto)

    dyno = subparsers.add_parser(
        "scrape-dynojet", help="Scrape curated Dynojet chart listings"
    )
    dyno.add_argument("--index-out", required=True, help="Path to write index CSV")
    dyno.add_argument(
        "--images-dir",
        default=None,
        help="Directory for chart images (defaults to external/dynojet/images)",
    )
    dyno.add_argument(
        "--listing-url",
        action="append",
        required=True,
        help="Dynojet listing URL (may be provided multiple times)",
    )
    dyno.set_defaults(func=cmd_scrape_dynojet)

    synth = subparsers.add_parser(
        "synthesize-winpep", help="Generate synthetic WinPEP logs"
    )
    synth.add_argument(
        "--index-csv", required=True, help="Input index CSV with dyno metadata"
    )
    synth.add_argument(
        "--output-dir", required=True, help="Base output directory for runs/"
    )
    synth.add_argument(
        "--source",
        choices=["fuelmoto", "dynojet", "all"],
        default="all",
        help="Filter by source",
    )
    synth.set_defaults(func=cmd_synthesize_winpep)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
