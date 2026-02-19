"""
Dynojet site scraper for known example pages.

This module scrapes specific known Dynojet pages that contain dyno chart
images. It does NOT crawl the entire dynojet.com site—only URLs explicitly
listed in DYNOJET_SAMPLE_PAGES are fetched.

Calling code must still honor each site's Terms of Use.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from external_scrapers import get_stdout_logger
from external_scrapers.dyno_models import (
    META_FIELD_ORDER,
    DynoChartMeta,
    meta_to_row,
    slugify_title,
)
from external_scrapers.http_utils import (
    RobotsAwareSession,
    RobotsDisallowed,
)
from dynoai.core.io_contracts import safe_path

logger = get_stdout_logger(__name__)


# Fixed list of known Dynojet pages containing dyno chart images.
# This list should be curated manually—no crawling.
DYNOJET_SAMPLE_PAGES: List[str] = [
    # Dynojet blog/docs pages with sample charts
    # Add URLs here as they are identified
    # Example: "https://www.dynojet.com/blog/some-article-with-dyno-chart/"
]

# Patterns to identify Dynojet graph images
DYNOJET_IMAGE_PATTERNS = [
    re.compile(r"dynojet", re.IGNORECASE),
    re.compile(r"DA00", re.IGNORECASE),  # Common Dynojet chart filename prefix
    re.compile(r"power\s*commander", re.IGNORECASE),
    re.compile(r"dyno.*chart", re.IGNORECASE),
    re.compile(r"hp.*tq", re.IGNORECASE),
]


def _is_dynojet_chart_image(img_tag) -> bool:
    """
    Determine if an img tag likely contains a Dynojet chart.

    Checks src, alt, title, and class attributes for patterns.
    """
    src = img_tag.get("src", "") or ""
    alt = img_tag.get("alt", "") or ""
    title = img_tag.get("title", "") or ""
    classes = " ".join(img_tag.get("class", []))

    combined = f"{src} {alt} {title} {classes}"

    for pattern in DYNOJET_IMAGE_PATTERNS:
        if pattern.search(combined):
            return True

    # Check for typical dyno chart image dimensions (usually wider than tall)
    width = img_tag.get("width")
    height = img_tag.get("height")
    try:
        w, h = int(width), int(height)
        if w > 400 and h > 200 and w > h:
            # Reasonable dyno chart dimensions, check for graph-like keywords
            if any(
                kw in combined.lower()
                for kw in ["graph", "chart", "dyno", "power", "torque"]
            ):
                return True
    except (TypeError, ValueError):
        pass

    return False


def _extract_title_from_img(img_tag, page_title: str) -> str:
    """Extract a meaningful title from an image tag."""
    alt = img_tag.get("alt", "").strip()
    title = img_tag.get("title", "").strip()

    if alt and len(alt) > 5:
        return alt
    if title and len(title) > 5:
        return title

    # Fall back to filename
    src = img_tag.get("src", "")
    if src:
        filename = Path(urlparse(src).path).stem
        # Clean up filename
        clean_name = re.sub(r"[-_]+", " ", filename).strip()
        if clean_name and len(clean_name) > 3:
            return clean_name.title()

    return page_title


def _infer_category_from_page(soup: BeautifulSoup, page_url: str) -> str:
    """Infer category from page title, heading, or URL."""
    # Try page title
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        if "harley" in title_text.lower():
            return "Harley-Davidson"
        if "honda" in title_text.lower():
            return "Honda"
        if "yamaha" in title_text.lower():
            return "Yamaha"
        if "kawasaki" in title_text.lower():
            return "Kawasaki"

    # Try H1
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(strip=True)
        if len(h1_text) < 50:
            return h1_text

    # Fall back to URL path
    path = urlparse(page_url).path
    segments = [s for s in path.split("/") if s]
    if segments:
        return segments[-1].replace("-", " ").title()

    return "Dynojet"


class DynojetSiteScraper:
    """
    Scraper for known Dynojet pages containing dyno charts.

    Only fetches URLs from the DYNOJET_SAMPLE_PAGES list—no crawling.
    """

    def __init__(
        self,
        images_dir: Optional[str | Path] = None,
        sample_pages: Optional[List[str]] = None,
    ) -> None:
        default_dir = Path("external") / "dynojet" / "images"
        self.images_dir = safe_path(str(images_dir or default_dir))
        self.sample_pages = sample_pages or DYNOJET_SAMPLE_PAGES

    def scrape_known_pages(self) -> List[DynoChartMeta]:
        """
        Scrape all known Dynojet sample pages for chart images.

        Returns:
            List of DynoChartMeta entries for discovered charts.
        """
        if not self.sample_pages:
            logger.info("No Dynojet sample pages configured; skipping scrape")
            return []

        entries: List[DynoChartMeta] = []

        for page_url in self.sample_pages:
            try:
                page_entries = self._scrape_page(page_url)
                entries.extend(page_entries)
            except RobotsDisallowed as e:
                logger.warning("Skipping %s: %s", page_url, e)
            except Exception as e:
                logger.error("Error scraping %s: %s", page_url, e)

        return entries

    def _scrape_page(self, page_url: str) -> List[DynoChartMeta]:
        """Scrape a single page for dyno chart images."""
        parsed = urlparse(page_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        with RobotsAwareSession(base_url=base_url) as session:
            response = session.get(page_url, allow_offsite=True)
            soup = BeautifulSoup(response.text, "html.parser")

            page_title_tag = soup.find("title")
            page_title = (
                page_title_tag.get_text(strip=True) if page_title_tag else "Dynojet Chart"
            )

            category = _infer_category_from_page(soup, page_url)
            entries: List[DynoChartMeta] = []

            for img in soup.find_all("img"):
                if not _is_dynojet_chart_image(img):
                    continue

                src = img.get("src") or img.get("data-src")
                if not src:
                    continue

                image_url = urljoin(page_url, src)
                title = _extract_title_from_img(img, page_title)
                meta_id = slugify_title("dynojet", title)

                logger.info("Found Dynojet chart: %s", meta_id)

                # Download the image
                image_file = self._download_image(meta_id, image_url, session)

                entry = DynoChartMeta(
                    source="dynojet",
                    id=meta_id,
                    category=category,
                    title=title,
                    page_url=page_url,
                    image_url=image_url,
                    image_file=image_file,
                    engine_family=None,
                    displacement_ci=None,
                    cam_info=None,
                    exhaust_info=None,
                    notes=None,
                    max_power_hp=None,
                    max_power_rpm=None,
                    max_torque_ftlb=None,
                    max_torque_rpm=None,
                )
                entries.append(entry)

            return entries

    def _download_image(
        self, meta_id: str, image_url: str, session: RobotsAwareSession
    ) -> Optional[str]:
        """Download a chart image and return the local path."""
        try:
            response = session.get(image_url, allow_offsite=True)
            target_path = self.images_dir / f"{meta_id}.jpg"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(response.content)
            rel_path = target_path.relative_to(Path.cwd())
            logger.info("Saved Dynojet image for %s to %s", meta_id, rel_path)
            return str(rel_path)
        except Exception as e:
            logger.warning("Failed to download image %s: %s", image_url, e)
            return None


def run_dynojet_scrape(
    output_index_csv: str,
    images_dir: Optional[str | Path] = None,
    sample_pages: Optional[List[str]] = None,
) -> None:
    """
    Run the Dynojet scraper and write results to CSV.

    Args:
        output_index_csv: Path to output CSV file.
        images_dir: Directory for downloaded images.
        sample_pages: List of page URLs to scrape (overrides default).
    """
    scraper = DynojetSiteScraper(images_dir=images_dir, sample_pages=sample_pages)
    entries = scraper.scrape_known_pages()

    if not entries:
        logger.info("No Dynojet charts found; skipping CSV write")
        return

    safe_csv_path = safe_path(output_index_csv)
    safe_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [f for f in META_FIELD_ORDER if f != "notes"]
    with safe_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for meta in entries:
            writer.writerow(meta_to_row(meta, include_notes=False))

    logger.info(
        "Dynojet scrape complete: %d entries written to %s",
        len(entries),
        safe_csv_path,
    )


__all__ = [
    "DynojetSiteScraper",
    "run_dynojet_scrape",
    "DYNOJET_SAMPLE_PAGES",
]

