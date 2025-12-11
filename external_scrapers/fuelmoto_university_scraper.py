from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from external_scrapers import get_stdout_logger
from external_scrapers.dyno_models import (
    META_FIELD_ORDER,
    DynoChartMeta,
    meta_to_row,
    slugify_title,
)
from external_scrapers.http_utils import fetch
from io_contracts import safe_path

logger = get_stdout_logger(__name__)


def _parse_engine_info(title: str) -> tuple[Optional[str], Optional[float]]:
    """Infer engine family and displacement from a title string."""
    family = None
    lowered = title.lower()
    if "milwaukee-eight" in lowered or "m8" in lowered:
        family = "M8"
    elif "twin cam" in lowered:
        family = "Twin Cam"
    elif "sportster" in lowered:
        family = "Sportster"

    displacement = None
    match = re.search(r"(\d{3})[″\"]", title)
    if match:
        displacement = float(match.group(1))
    return family, displacement


def _find_category_links(header_tag) -> Iterable:
    """Return all anchor tags within the first UL/DIV following the header."""
    sibling = header_tag.find_next_sibling()
    while sibling is not None:
        if sibling.name in ("h1", "h2", "h3", "h4"):
            break
        if sibling.name in ("ul", "div"):
            return sibling.find_all("a")
        sibling = sibling.find_next_sibling()
    return []


class FuelMotoUniversityScraper:
    def __init__(self, images_dir: str | Path | None = None) -> None:
        default_dir = Path("external") / "fuelmoto" / "images"
        self.images_dir = safe_path(str(images_dir or default_dir))

    def scrape(
        self, base_url: str = "https://university.fuelmotousa.com/dyno-charts/"
    ) -> List[DynoChartMeta]:
        response = fetch(base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        harley_heading = soup.find(
            lambda tag: tag.name in ("h2", "h3", "h4")
            and "harley" in tag.get_text(" ", strip=True).lower()
        )
        if not harley_heading:
            logger.warning("Could not locate Harley-Davidson section on %s", base_url)
            return []

        entries: List[DynoChartMeta] = []
        node = harley_heading.find_next_sibling()
        while node is not None:
            if node.name in ("h1", "h2") and node is not harley_heading:
                break
            if node.name in ("h3", "h4"):
                category = node.get_text(" ", strip=True)
                for link in _find_category_links(node):
                    href = link.get("href")
                    if not href:
                        continue
                    page_url = urljoin(base_url, href)
                    title = link.get_text(" ", strip=True)
                    meta_id = slugify_title("fuelmoto", title)
                    logger.info("Scraping Fuel Moto entry %s", meta_id)
                    meta = self._scrape_entry(
                        page_url=page_url,
                        category=category,
                        title=title,
                        meta_id=meta_id,
                    )
                    entries.append(meta)
            node = node.find_next_sibling()

        return entries

    def _scrape_entry(
        self, page_url: str, category: str, title: str, meta_id: str
    ) -> DynoChartMeta:
        page_response = fetch(page_url)
        page_soup = BeautifulSoup(page_response.text, "html.parser")
        image_url = self._select_best_image(page_soup, page_url)
        image_file: Optional[str] = None

        if image_url:
            image_file = self._download_image(meta_id, image_url)

        engine_family, displacement = _parse_engine_info(title)
        return DynoChartMeta(
            source="fuelmoto",
            id=meta_id,
            category=category,
            title=title,
            page_url=page_url,
            image_url=image_url,
            image_file=image_file,
            engine_family=engine_family,
            displacement_ci=displacement,
            cam_info=None,
            exhaust_info=None,
            notes=None,
            max_power_hp=None,
            max_power_rpm=None,
            max_torque_ftlb=None,
            max_torque_rpm=None,
        )

    def _select_best_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        content_root = soup.find("article") or soup.find(class_="entry-content")
        search_scope = content_root or soup
        images = search_scope.find_all("img")
        if not images:
            return None

        def _weight(tag) -> int:
            width = tag.get("width")
            try:
                return int(width)
            except (TypeError, ValueError):
                return 0

        best_img = max(images, key=_weight)
        src = best_img.get("src") or best_img.get("data-src")
        if not src:
            return None
        return urljoin(base_url, src)

    def _download_image(self, meta_id: str, image_url: str) -> str:
        response = fetch(image_url)
        target_path = self.images_dir / f"{meta_id}.jpg"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)
        rel_path = target_path.relative_to(Path.cwd())
        logger.info("Saved Fuel Moto image for %s to %s", meta_id, rel_path)
        return str(rel_path)


def run_fuelmoto_scrape(
    output_index_csv: str, images_dir: str | Path | None = None
) -> None:
    scraper = FuelMotoUniversityScraper(images_dir=images_dir)
    entries = scraper.scrape()
    safe_csv_path = safe_path(output_index_csv)
    safe_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [f for f in META_FIELD_ORDER if f != "notes"]
    with safe_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for meta in entries:
            writer.writerow(meta_to_row(meta, include_notes=False))
    logger.info(
        "Fuel Moto scrape complete: %d entries written to %s",
        len(entries),
        safe_csv_path,
    )
