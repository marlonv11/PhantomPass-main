from unittest.mock import MagicMock, patch

from scraper.extractor import (
    RobotsDisallowedError,
    RobotsUnavailableError,
    Scraper,
)
from scraper.data_cleaner import clean_text, dedupe


SAMPLE_HTML = """
<html><body>
  <h1>  Hello   world </h1>
  <a href="/about">About</a>
  <a href="https://example.com/contact">Contact</a>
</body></html>
"""


def test_extract_text_with_selector():
    scraper = Scraper()
    assert scraper.extract_text(SAMPLE_HTML, "h1") == "Hello world"


def test_extract_links_resolves_relative():
    scraper = Scraper()
    links = scraper.extract_links(SAMPLE_HTML, "https://example.com")
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links


def test_fetch_raises_when_robots_disallows():
    scraper = Scraper()
    with patch.object(scraper, "is_allowed", return_value=False):
        try:
            scraper.fetch("https://example.com/private")
        except RobotsDisallowedError:
            pass
        else:
            raise AssertionError("expected RobotsDisallowedError")


def test_fetch_returns_html_when_allowed():
    scraper = Scraper(delay_seconds=0)
    fake_response = MagicMock()
    fake_response.text = SAMPLE_HTML
    fake_response.raise_for_status.return_value = None
    with patch.object(scraper, "is_allowed", return_value=True), patch.object(
        scraper._session, "get", return_value=fake_response
    ):
        assert scraper.fetch("https://example.com") == SAMPLE_HTML


def test_robots_forbidden_fails_closed():
    scraper = Scraper()
    response = MagicMock(status_code=403)
    with patch.object(scraper._session, "get", return_value=response):
        try:
            scraper.is_allowed("https://example.com/blog")
        except RobotsUnavailableError as exc:
            assert "HTTP 403" in str(exc)
        else:
            raise AssertionError("expected RobotsUnavailableError")


def test_missing_robots_file_has_no_restrictions():
    scraper = Scraper()
    response = MagicMock(status_code=404, text="")
    with patch.object(scraper._session, "get", return_value=response):
        assert scraper.is_allowed("https://example.com/blog") is True


def test_clean_text_collapses_whitespace():
    assert clean_text("  a   b\n\tc ") == "a b c"


def test_dedupe_preserves_order():
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
