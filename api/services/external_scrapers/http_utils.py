"""
Robots-aware HTTP helpers for external scrapers.

Calling code must still honor each site's Terms of Use and rate limits—checking
robots.txt is necessary but not sufficient for compliance.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from external_scrapers import get_stdout_logger

DEFAULT_USER_AGENT = "DawsonDynamicsDynoAI/0.1"
REQUEST_DELAY = 1.0

_last_request_at = 0.0
_request_lock = threading.Lock()

logger = get_stdout_logger(__name__)


class RobotsDisallowed(RuntimeError):
    """Raised when robots.txt disallows fetching a URL."""

    pass


@dataclass
class RobotsClient:
    domain: str
    parser: RobotFileParser

    _cache: ClassVar[Dict[str, "RobotsClient"]] = {}

    @classmethod
    def for_domain(cls, domain: str) -> "RobotsClient":
        if domain in cls._cache:
            return cls._cache[domain]

        parser = RobotFileParser()
        parser.set_url(f"https://{domain}/robots.txt")
        try:
            parser.read()
            logger.info("Fetched robots.txt for %s", domain)
        except Exception as exc:  # pragma: no cover - network failure path
            logger.warning(
                "Failed to read robots.txt for %s: %s; defaulting to disallow all",
                domain,
                exc,
            )
            parser.parse(["User-agent: *", "Disallow: /"])

        client = cls(domain=domain, parser=parser)
        cls._cache[domain] = client
        return client

    def can_fetch(self, path: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
        return self.parser.can_fetch(user_agent, path)


def _respect_rate_limit() -> None:
    global _last_request_at
    with _request_lock:
        now = time.monotonic()
        elapsed = now - _last_request_at
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        _last_request_at = time.monotonic()


def normalize_url(base_url: str, href: str) -> str:
    """
    Normalize a possibly-relative URL against a base URL.

    Args:
        base_url: The base URL to resolve against.
        href: The URL or path to normalize.

    Returns:
        Fully-qualified URL string.
    """
    return urljoin(base_url, href)


def fetch(
    url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 10.0
) -> requests.Response:
    """
    Fetch a URL while honoring robots.txt and a simple client-side delay.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for fetch: {url}")

    domain = parsed.netloc
    path = parsed.path or "/"
    robots_client = RobotsClient.for_domain(domain)
    if not robots_client.can_fetch(path, user_agent=user_agent):
        raise RobotsDisallowed(
            f"Robots.txt for {domain} disallows fetching {path} as {user_agent}"
        )

    _respect_rate_limit()
    logger.info("Fetching %s", url)
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    return response


@dataclass
class RobotsAwareSession:
    """
    A session-based HTTP client that respects robots.txt rules.

    Maintains a requests.Session for connection pooling and provides
    deterministic, polite web scraping with configurable delays.
    """

    base_url: str
    user_agent: str = DEFAULT_USER_AGENT
    delay_seconds: float = REQUEST_DELAY
    _session: requests.Session = field(init=False, repr=False)
    _robots: Optional[RobotFileParser] = field(init=False, repr=False)
    _last_request: float = field(init=False, default=0.0, repr=False)

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = self.user_agent

        parsed = urlparse(self.base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self._robots = RobotFileParser()
        self._robots.set_url(robots_url)
        try:
            self._robots.read()
            logger.info("RobotsAwareSession: Loaded robots.txt from %s", robots_url)
        except Exception as exc:
            logger.warning(
                "RobotsAwareSession: Failed to read robots.txt from %s: %s; "
                "defaulting to allow all",
                robots_url,
                exc,
            )
            self._robots = None

    def normalize_url(self, href: str) -> str:
        """Normalize a relative URL against this session's base_url."""
        return urljoin(self.base_url, href)

    def _allowed(self, url: str) -> bool:
        """Check if robots.txt allows fetching the given URL."""
        if self._robots is None:
            return True
        parsed = urlparse(url)
        base_parsed = urlparse(self.base_url)
        # Offsite URLs: robots file does not apply
        if parsed.netloc and parsed.netloc != base_parsed.netloc:
            return True
        return self._robots.can_fetch(self.user_agent, parsed.path or "/")

    def _respect_delay(self) -> None:
        """Sleep if needed to respect the delay between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request = time.monotonic()

    def get(
        self,
        url: str,
        *,
        allow_offsite: bool = False,
        timeout: float = 15.0,
    ) -> requests.Response:
        """
        Perform a GET request with robots.txt checking and rate limiting.

        Args:
            url: URL or path to fetch (relative URLs resolved against base_url).
            allow_offsite: If True, skip robots check for URLs on other domains.
            timeout: Request timeout in seconds.

        Returns:
            requests.Response object.

        Raises:
            RobotsDisallowed: If robots.txt disallows fetching the URL.
            requests.HTTPError: On HTTP error responses.
        """
        full_url = self.normalize_url(url)
        parsed = urlparse(full_url)
        base_parsed = urlparse(self.base_url)
        is_offsite = parsed.netloc and parsed.netloc != base_parsed.netloc

        if not is_offsite and not self._allowed(full_url):
            raise RobotsDisallowed(f"Robots.txt disallows fetching {full_url}")

        if is_offsite and not allow_offsite:
            raise ValueError(
                f"Offsite URL {full_url} not allowed without allow_offsite=True"
            )

        self._respect_delay()
        logger.info("RobotsAwareSession: GET %s", full_url)
        resp = self._session.get(full_url, timeout=timeout)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def __enter__(self) -> "RobotsAwareSession":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


__all__ = [
    "fetch",
    "normalize_url",
    "RobotsClient",
    "RobotsAwareSession",
    "RobotsDisallowed",
    "DEFAULT_USER_AGENT",
    "REQUEST_DELAY",
]
