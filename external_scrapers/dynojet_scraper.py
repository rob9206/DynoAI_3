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

KEYWORDS = ("dyno chart", "dyno run")


def _parse_engine_info(title: str) -> tuple[Optional[str], Optional[float]]:
    family = None
    lowered = title.lower()
    if "milwaukee-eight" in lowered or "m8" in lowered:
        family = "M8"
    elif "twin cam" in lowered:
        family = "Twin Cam"
    elif "sport" in lowered:
        family = "Sport"

    displacement = None
    match = re.search(r"(\d{3})[″\"]", title)
    if match:
        displacement = float(match.group(1))
    return family, displacement


def _nearest_heading(tag) -> str:
    heading = tag.find_previous(["h2", "h3", "h4"])
    return heading.get_text(" ", strip=True) if heading else "Dynojet"


def _is_relevant_link(anchor) -> bool:
    text = anchor.get_text(" ", strip=True).lower()
    has_keyword = any(key in text for key in KEYWORDS)
    has_image = anchor.find("img") is not None
    if has_image and not text:
        alt = anchor.find("img").get("alt") or ""
        text = alt.lower()
        has_keyword = has_keyword or any(key in text for key in KEYWORDS)
    return has_keyword or has_image


class DynojetScraper:
    def __init__(
        self, listing_urls: List[str], images_dir: str | Path | None = None
    ) -> None:
        self.listing_urls = listing_urls
        default_dir = Path("external") / "dynojet" / "images"
        self.images_dir = safe_path(str(images_dir or default_dir))

    def scrape(self) -> List[DynoChartMeta]:
        entries: List[DynoChartMeta] = []
        for listing_url in self.listing_urls:
            logger.info("Processing Dynojet listing %s", listing_url)
            response = fetch(listing_url)
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a"):
                if not _is_relevant_link(link):
                    continue
                href = link.get("href")
                if not href:
                    continue
                page_url = urljoin(listing_url, href)
                title = link.get_text(" ", strip=True) or (
                    link.find("img").get("alt", "").strip() if link.find("img") else ""
                )
                category = _nearest_heading(link)
                meta_id = slugify_title("dynojet", f"{category}_{title}")
                logger.info("Scraping Dynojet entry %s", meta_id)
                entry = self._scrape_entry(
                    page_url=page_url,
                    category=category,
                    title=title,
                    meta_id=meta_id,
                )
                entries.append(entry)
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
            source="dynojet",
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
        logger.info("Saved Dynojet image for %s to %s", meta_id, rel_path)
        return str(rel_path)


def run_dynojet_scrape(
    listing_urls: List[str], output_index_csv: str, images_dir: str | Path | None = None
) -> None:
    scraper = DynojetScraper(listing_urls, images_dir=images_dir)
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
        "Dynojet scrape complete: %d entries written to %s", len(entries), safe_csv_path
    )
