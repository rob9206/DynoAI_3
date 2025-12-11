"""
Tests for Fuel Moto University scraper.

Uses a saved HTML fixture to test parsing without live HTTP.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from external_scrapers.dyno_models import DynoChartMeta
from external_scrapers.fuelmoto_university_scraper import (
    FuelMotoUniversityScraper,
    _parse_engine_info,
)

# Sample HTML fixture simulating the Fuel Moto dyno-charts page
SAMPLE_FUELMOTO_HTML = """
<!DOCTYPE html>
<html>
<head><title>Dyno Charts - Fuel Moto University</title></head>
<body>
<article>
<h2>Harley-Davidson Dyno Charts</h2>

<h3>Milwaukee-Eight 131″</h3>
<ul>
    <li><a href="https://university.fuelmotousa.com/m8-131-stage2/">M8 131″ Stage 2 with S&amp;S 475 Cam</a></li>
    <li><a href="https://university.fuelmotousa.com/m8-131-stage3/">M8 131″ Stage 3 Big Bore</a></li>
</ul>

<h3>Milwaukee-Eight 117″</h3>
<ul>
    <li><a href="https://university.fuelmotousa.com/m8-117-stock/">M8 117″ Stock Baseline</a></li>
</ul>

<h3>Twin Cam 110″</h3>
<ul>
    <li><a href="https://university.fuelmotousa.com/tc-110-stage1/">Twin Cam 110″ Stage 1</a></li>
</ul>

<h2>Indian Motorcycle Dyno Charts</h2>
<h3>Thunder Stroke 116″</h3>
<ul>
    <li><a href="https://university.fuelmotousa.com/indian-116/">Thunder Stroke 116 Stage 1</a></li>
</ul>
</article>
</body>
</html>
"""

SAMPLE_ENTRY_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>M8 131″ Stage 2 - Fuel Moto University</title></head>
<body>
<article class="entry-content">
<h1>Milwaukee-Eight 131″ Stage 2 with S&amp;S 475 Cam</h1>
<p>This build features the S&amp;S 475 cam with a 131″ big bore kit.</p>
<img src="https://university.fuelmotousa.com/wp-content/uploads/m8-131-stage2-dyno.jpg"
     width="800" height="500" alt="M8 131 Stage 2 Dyno Chart">
<p>Max Power: 164.03 HP @ 5800 RPM</p>
<p>Max Torque: 160.17 ft-lb @ 3800 RPM</p>
</article>
</body>
</html>
"""


class TestEngineInfoParsing:
    """Tests for _parse_engine_info function."""

    def test_m8_detection(self) -> None:
        family, disp = _parse_engine_info("M8 131″ Stage 2")
        assert family == "M8"
        assert disp == 131.0

    def test_milwaukee_eight_detection(self) -> None:
        family, disp = _parse_engine_info("Milwaukee-Eight 117″ Stock")
        assert family == "M8"
        assert disp == 117.0

    def test_twin_cam_detection(self) -> None:
        family, disp = _parse_engine_info('Twin Cam 110" Stage 1')
        assert family == "Twin Cam"
        assert disp == 110.0

    def test_sportster_detection(self) -> None:
        family, disp = _parse_engine_info("Sportster 1200 Stage Kit")
        assert family == "Sportster"
        assert disp is None  # No displacement in quotes

    def test_no_match(self) -> None:
        family, disp = _parse_engine_info("Generic Motorcycle Dyno")
        assert family is None
        assert disp is None


class TestFuelMotoScraperParsing:
    """Tests for FuelMotoUniversityScraper parsing logic."""

    @patch("external_scrapers.fuelmoto_university_scraper.fetch")
    def test_parses_harley_section_links(self, mock_fetch: MagicMock) -> None:
        """Test that scraper correctly parses Harley links from main page."""
        # Mock the main page response
        mock_response = MagicMock()
        mock_response.text = SAMPLE_FUELMOTO_HTML

        # Mock entry page responses
        mock_entry_response = MagicMock()
        mock_entry_response.text = SAMPLE_ENTRY_PAGE_HTML
        mock_entry_response.content = b"fake image bytes"

        mock_fetch.side_effect = [mock_response] + [mock_entry_response] * 10

        scraper = FuelMotoUniversityScraper(images_dir="test_images")
        # Don't actually download images in test
        scraper._download_image = MagicMock(return_value="test_path.jpg")

        entries = scraper.scrape()

        # Should find 4 Harley entries (stops at Indian section)
        assert len(entries) == 4

        # Check categories
        categories = {e.category for e in entries}
        assert "Milwaukee-Eight 131″" in categories
        assert "Milwaukee-Eight 117″" in categories
        assert "Twin Cam 110″" in categories

        # Check titles
        titles = {e.title for e in entries}
        assert "M8 131″ Stage 2 with S&S 475 Cam" in titles
        assert "M8 117″ Stock Baseline" in titles
        assert "Twin Cam 110″ Stage 1" in titles

    @patch("external_scrapers.fuelmoto_university_scraper.fetch")
    def test_engine_info_extracted(self, mock_fetch: MagicMock) -> None:
        """Test that engine family and displacement are extracted."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_FUELMOTO_HTML

        mock_entry_response = MagicMock()
        mock_entry_response.text = SAMPLE_ENTRY_PAGE_HTML
        mock_entry_response.content = b"fake image bytes"

        mock_fetch.side_effect = [mock_response] + [mock_entry_response] * 10

        scraper = FuelMotoUniversityScraper(images_dir="test_images")
        scraper._download_image = MagicMock(return_value="test_path.jpg")

        entries = scraper.scrape()

        # Find the M8 131 entry
        m8_entries = [e for e in entries if "131" in e.title]
        assert len(m8_entries) > 0

        entry = m8_entries[0]
        assert entry.engine_family == "M8"
        assert entry.displacement_ci == 131.0

    @patch("external_scrapers.fuelmoto_university_scraper.fetch")
    def test_empty_harley_section(self, mock_fetch: MagicMock) -> None:
        """Test graceful handling when no Harley section found."""
        mock_response = MagicMock()
        mock_response.text = "<html><body><h2>Honda Charts</h2></body></html>"
        mock_fetch.return_value = mock_response

        scraper = FuelMotoUniversityScraper(images_dir="test_images")
        entries = scraper.scrape()

        assert entries == []


class TestFuelMotoChartMetaFields:
    """Test that DynoChartMeta fields are populated correctly."""

    @patch("external_scrapers.fuelmoto_university_scraper.fetch")
    def test_all_required_fields_present(self, mock_fetch: MagicMock) -> None:
        """Test that all required fields are populated."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_FUELMOTO_HTML

        mock_entry_response = MagicMock()
        mock_entry_response.text = SAMPLE_ENTRY_PAGE_HTML
        mock_entry_response.content = b"fake image bytes"

        mock_fetch.side_effect = [mock_response] + [mock_entry_response] * 10

        scraper = FuelMotoUniversityScraper(images_dir="test_images")
        scraper._download_image = MagicMock(return_value="test/path.jpg")

        entries = scraper.scrape()
        assert len(entries) > 0

        entry = entries[0]
        assert entry.source == "fuelmoto"
        assert entry.id  # Not empty
        assert entry.category  # Not empty
        assert entry.title  # Not empty
        assert entry.page_url.startswith("http")
