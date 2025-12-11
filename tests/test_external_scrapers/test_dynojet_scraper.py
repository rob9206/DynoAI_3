from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

import external_scrapers.http_utils as http_utils
from external_scrapers.dynojet_scraper import DynojetScraper


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


def test_dynojet_scraper_parses_entries(monkeypatch) -> None:
    listing_url = "https://www.dynojet.com/dyno-charts/"
    detail_url = "https://www.dynojet.com/dyno-charts/road-glide"
    image_url = "https://www.dynojet.com/images/road-glide-chart.jpg"

    listing_html = f"""
    <div>
      <h2>Baggers</h2>
      <a href="/dyno-charts/road-glide"><img src="/thumb.jpg" alt="Road Glide Dyno Chart" /></a>
    </div>
    """
    detail_html = f"""
    <article>
      <div class="entry-content">
        <img src="{image_url}" width="900" />
      </div>
    </article>
    """
    responses: Dict[str, StubResponse] = {
        listing_url: StubResponse(text=listing_html),
        detail_url: StubResponse(text=detail_html),
        image_url: StubResponse(content=b"img-bytes"),
    }

    def fake_get(url: str, headers=None, timeout: float = 10.0) -> StubResponse:
        assert url in responses, f"unexpected URL {url}"
        return responses[url]

    _allow_all_robots(monkeypatch)
    monkeypatch.setattr(http_utils.requests, "get", fake_get)

    images_dir = Path("tmp_test") / "dynojet_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    scraper = DynojetScraper([listing_url], images_dir=images_dir)
    metas = scraper.scrape()

    assert len(metas) == 1
    meta = metas[0]
    assert meta.source == "dynojet"
    assert meta.category == "Baggers"
    assert meta.id.startswith("dynojet_baggers_road_glide_dyno_chart")
    assert meta.image_file is not None
    assert (images_dir / Path(meta.image_file).name).exists()
