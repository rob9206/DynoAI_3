"""
External data ingestion orchestration.

This module coordinates scraping external dyno chart sources and
generating synthetic WinPEP8-style runs from the collected metadata.

This is a dev/CLI tool—NOT a public API endpoint.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List, Optional

from external_scrapers import get_stdout_logger
from external_scrapers.dyno_models import DynoChartMeta, meta_from_row
from external_scrapers.dynojet_site_scraper import run_dynojet_scrape
from external_scrapers.fuelmoto_university_scraper import run_fuelmoto_scrape
from dynoai.core.io_contracts import safe_path
from synthetic.winpep8_from_peaks import PeakInfo, generate_and_write_run

logger = get_stdout_logger(__name__)

# Default paths for index CSVs
FUELMOTO_INDEX_CSV = "external/fuelmoto/index.csv"
DYNOJET_INDEX_CSV = "external/dynojet/index.csv"


def _load_index_csv(csv_path: str) -> List[DynoChartMeta]:
    """Load DynoChartMeta entries from an index CSV."""
    safe_csv = safe_path(csv_path)
    if not safe_csv.exists():
        logger.warning("Index CSV not found: %s", csv_path)
        return []

    entries: List[DynoChartMeta] = []
    with safe_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                meta = meta_from_row(row)
                entries.append(meta)
            except Exception as e:
                logger.warning("Failed to parse row: %s - %s", row, e)

    logger.info("Loaded %d entries from %s", len(entries), csv_path)
    return entries


def _meta_to_peak_info(meta: DynoChartMeta) -> Optional[PeakInfo]:
    """
    Convert DynoChartMeta to PeakInfo if peak values are available.

    Returns None if required peak values are missing.
    """
    if (
        meta.max_power_hp is None
        or meta.max_power_rpm is None
        or meta.max_torque_ftlb is None
        or meta.max_torque_rpm is None
    ):
        return None

    try:
        return PeakInfo(
            hp_peak=meta.max_power_hp,
            hp_peak_rpm=meta.max_power_rpm,
            tq_peak=meta.max_torque_ftlb,
            tq_peak_rpm=meta.max_torque_rpm,
        )
    except ValueError as e:
        logger.warning("Invalid peak values for %s: %s", meta.id, e)
        return None


def run_scrapers(
    skip_fuelmoto: bool = False,
    skip_dynojet: bool = False,
) -> None:
    """
    Run external scrapers to collect dyno chart metadata and images.

    Args:
        skip_fuelmoto: Skip Fuel Moto University scrape.
        skip_dynojet: Skip Dynojet site scrape.
    """
    if not skip_fuelmoto:
        logger.info("Running Fuel Moto University scraper...")
        try:
            run_fuelmoto_scrape(FUELMOTO_INDEX_CSV)
        except Exception as e:
            logger.error("Fuel Moto scrape failed: %s", e)

    if not skip_dynojet:
        logger.info("Running Dynojet site scraper...")
        try:
            run_dynojet_scrape(DYNOJET_INDEX_CSV)
        except Exception as e:
            logger.error("Dynojet scrape failed: %s", e)


def generate_synthetic_runs(
    fuelmoto_index: str = FUELMOTO_INDEX_CSV,
    dynojet_index: str = DYNOJET_INDEX_CSV,
    require_peaks: bool = True,
) -> List[str]:
    """
    Generate synthetic WinPEP8 runs from scraped index CSVs.

    For each entry with peak HP/TQ values, generates a synthetic
    dyno run and saves it under runs/{source}/{id}/run.csv.

    Args:
        fuelmoto_index: Path to Fuel Moto index CSV.
        dynojet_index: Path to Dynojet index CSV.
        require_peaks: If True, only generate runs for entries with peak values.

    Returns:
        List of paths to generated run CSV files.
    """
    generated_paths: List[str] = []

    # Process Fuel Moto entries
    fuelmoto_entries = _load_index_csv(fuelmoto_index)
    for meta in fuelmoto_entries:
        peak_info = _meta_to_peak_info(meta)
        if peak_info is None:
            if require_peaks:
                logger.debug(
                    "Skipping %s: missing peak values (OCR not yet implemented)",
                    meta.id,
                )
                continue
            # Use placeholder values for testing if peaks not required
            peak_info = PeakInfo(
                hp_peak=100.0,
                hp_peak_rpm=5500.0,
                tq_peak=100.0,
                tq_peak_rpm=3500.0,
            )

        run_id = f"fuelmoto/{meta.id}"
        try:
            path = generate_and_write_run(
                run_id=run_id,
                peak=peak_info,
                engine_family=meta.engine_family,
            )
            generated_paths.append(path)
            logger.info("Generated synthetic run: %s", path)
        except Exception as e:
            logger.error("Failed to generate run for %s: %s", run_id, e)

    # Process Dynojet entries
    dynojet_entries = _load_index_csv(dynojet_index)
    for meta in dynojet_entries:
        peak_info = _meta_to_peak_info(meta)
        if peak_info is None:
            if require_peaks:
                logger.debug(
                    "Skipping %s: missing peak values (OCR not yet implemented)",
                    meta.id,
                )
                continue
            peak_info = PeakInfo(
                hp_peak=100.0,
                hp_peak_rpm=5500.0,
                tq_peak=100.0,
                tq_peak_rpm=3500.0,
            )

        run_id = f"dynojet/{meta.id}"
        try:
            path = generate_and_write_run(
                run_id=run_id,
                peak=peak_info,
                engine_family=meta.engine_family,
            )
            generated_paths.append(path)
            logger.info("Generated synthetic run: %s", path)
        except Exception as e:
            logger.error("Failed to generate run for %s: %s", run_id, e)

    logger.info("Generated %d synthetic runs total", len(generated_paths))
    return generated_paths


def ingest_external_dyno_sources(
    run_scrapers_first: bool = True,
    skip_fuelmoto: bool = False,
    skip_dynojet: bool = False,
    require_peaks: bool = True,
) -> List[str]:
    """
    Main orchestration function for external data ingestion.

    1. Runs scrapers to collect dyno chart metadata and images
    2. Generates synthetic WinPEP8 runs from charts with peak values

    This function is intended for CLI/dev use, not as a public API.

    Args:
        run_scrapers_first: If True, run scrapers before generating runs.
        skip_fuelmoto: Skip Fuel Moto scraper.
        skip_dynojet: Skip Dynojet scraper.
        require_peaks: Only generate runs for entries with peak values.

    Returns:
        List of paths to generated run CSV files.
    """
    if run_scrapers_first:
        run_scrapers(skip_fuelmoto=skip_fuelmoto, skip_dynojet=skip_dynojet)

    return generate_synthetic_runs(require_peaks=require_peaks)


def main() -> None:
    """CLI entry point for external data ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest external dyno chart sources and generate synthetic runs."
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping, only generate runs from existing index CSVs",
    )
    parser.add_argument(
        "--skip-fuelmoto",
        action="store_true",
        help="Skip Fuel Moto University scraper",
    )
    parser.add_argument(
        "--skip-dynojet",
        action="store_true",
        help="Skip Dynojet site scraper",
    )
    parser.add_argument(
        "--no-require-peaks",
        action="store_true",
        help="Generate runs even without peak values (uses placeholders)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    generated = ingest_external_dyno_sources(
        run_scrapers_first=not args.skip_scrape,
        skip_fuelmoto=args.skip_fuelmoto,
        skip_dynojet=args.skip_dynojet,
        require_peaks=not args.no_require_peaks,
    )

    print(f"\n{'=' * 60}")
    print(f"Ingestion complete. Generated {len(generated)} synthetic runs.")
    if generated:
        print("\nGenerated run paths:")
        for path in generated[:10]:
            print(f"  - {path}")
        if len(generated) > 10:
            print(f"  ... and {len(generated) - 10} more")


if __name__ == "__main__":
    main()

