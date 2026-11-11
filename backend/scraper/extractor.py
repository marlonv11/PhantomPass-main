"""HTTP fetch + HTML parsing that respects robots.txt and site Terms of Service."""

from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "PhantomPass/0.1 (+https://github.com/JoseMorales44/PhantomPass)"


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt disallows fetching the requested URL."""


class RobotsUnavailableError(RobotsDisallowedError):
    """Raised when robots.txt cannot be checked safely."""


class Scraper:
    """Minimal, polite scraper.

    - Checks robots.txt before every fetch (cached per host).
    - Sends a descriptive User-Agent.
    - Sleeps between requests to avoid overloading servers.
    """

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        delay_seconds: float = 1.0,
        timeout: int = 15,
    ) -> None:
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent

    def _robots_for(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._robots_cache:
            rp = RobotFileParser()
            robots_url = urljoin(host, "/robots.txt")
            rp.set_url(robots_url)
            try:
                response = self._session.get(robots_url, timeout=self.timeout)
            except requests.RequestException as exc:
                raise RobotsUnavailableError(
                    f"Could not verify robots.txt for {host}"
                ) from exc

            if response.status_code == 404:
                rp.parse([])
            elif not 200 <= response.status_code < 300:
                raise RobotsUnavailableError(
                    f"Could not verify robots.txt for {host} "
                    f"(HTTP {response.status_code})"
                )
            else:
                rp.parse(response.text.splitlines())

            self._robots_cache[host] = rp
        return self._robots_cache[host]

    def is_allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.user_agent, url)

    def fetch(self, url: str) -> str:
        """Return the HTML body of *url*, or raise if disallowed/failed."""
        if not self.is_allowed(url):
            raise RobotsDisallowedError(f"robots.txt disallows: {url}")
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        time.sleep(self.delay_seconds)
        return response.text

    def extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            links.append(urljoin(base_url, anchor["href"]))
        return links

    def extract_text(self, html: str, selector: Optional[str] = None) -> str:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.select_one(selector) if selector else soup
        if node is None:
            return ""
        raw = node.get_text(separator=" ", strip=True)
        return " ".join(raw.split())
