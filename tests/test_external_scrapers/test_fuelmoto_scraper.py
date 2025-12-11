from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

import external_scrapers.http_utils as http_utils
from external_scrapers.fuelmoto_university_scraper import FuelMotoUniversityScraper


class StubResponse:
    def __init__(self, text: str | None = None, content: bytes = b"") -> None:
        self.text = text or ""
        self.content = content

    def raise_for_status(self) -> None:
        return None


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(http_utils, "_respect_rate_limit", lambda: None)
    monkeypatch.setattr(http_utils, "REQUEST_DELAY", 0.0)


def _allow_all_robots(monkeypatch) -> None:
    class StubRobots:
        def can_fetch(
            self, path: str, user_agent: str = http_utils.DEFAULT_USER_AGENT
        ) -> bool:
            return True

    monkeypatch.setattr(
        http_utils.RobotsClient,
        "for_domain",
        classmethod(lambda cls, domain: StubRobots()),
    )


def test_fuelmoto_scraper_parses_categories_and_links(monkeypatch) -> None:
    base_url = "https://university.fuelmotousa.com/dyno-charts/"
    detail_url = "https://university.fuelmotousa.com/dyno-charts/sample-entry"
    image_url = "https://university.fuelmotousa.com/content/chart-main.jpg"

    main_html = """
    <h2>Harley-Davidson</h2>
    <h3>24+ Gen2 Milwaukee-Eight Models</h3>
    <ul>
      <li><a href="/dyno-charts/sample-entry">2025 FLTRXS FM 132″ Z Factor RS 534</a></li>
    </ul>
    <h2>Other Section</h2>
    """
    detail_html = f"""
    <article>
      <div class="entry-content">
        <p>Chart body</p>
        <img src="{image_url}" width="800" />
      </div>
    </article>
    """
    responses: Dict[str, StubResponse] = {
        base_url: StubResponse(text=main_html),
        detail_url: StubResponse(text=detail_html),
        image_url: StubResponse(content=b"fake-bytes"),
    }

    def fake_get(url: str, headers=None, timeout: float = 10.0) -> StubResponse:
        assert url in responses, f"unexpected URL {url}"
        return responses[url]

    _allow_all_robots(monkeypatch)
    monkeypatch.setattr(http_utils.requests, "get", fake_get)

    images_dir = Path("tmp_test") / "fuelmoto_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    scraper = FuelMotoUniversityScraper(images_dir=images_dir)
    metas = scraper.scrape(base_url)

    assert len(metas) == 1
    meta = metas[0]
    assert meta.category == "24+ Gen2 Milwaukee-Eight Models"
    assert meta.id == "fuelmoto_2025_fltrxs_fm_132_z_factor_rs_534"
    assert meta.image_file is not None
    assert (images_dir / f"{meta.id}.jpg").exists()


def test_fuelmoto_scraper_respects_robots(monkeypatch) -> None:
    class DisallowRobots:
        def can_fetch(
            self, path: str, user_agent: str = http_utils.DEFAULT_USER_AGENT
        ) -> bool:
            return False

    monkeypatch.setattr(
        http_utils.RobotsClient,
        "for_domain",
        classmethod(lambda cls, domain: DisallowRobots()),
    )

    with pytest.raises(RuntimeError):
        FuelMotoUniversityScraper().scrape(
            "https://university.fuelmotousa.com/dyno-charts/"
        )
