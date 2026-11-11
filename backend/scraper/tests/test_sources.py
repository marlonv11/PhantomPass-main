import textwrap

import pytest

from scraper.sources import load_sources


def _write(tmp_path, content: str):
    path = tmp_path / "sources.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_loads_sources_and_defaults_allowed_false(tmp_path):
    path = _write(
        tmp_path,
        """
        sources:
          demo:
            name: "Demo"
            base_url: "https://example.com"
            selectors:
              title: "h1"
        """,
    )
    sources = load_sources(path)
    assert "demo" in sources
    assert sources["demo"].allowed is False
    assert sources["demo"].selectors == {"title": "h1"}


def test_allowed_true_is_respected(tmp_path):
    path = _write(
        tmp_path,
        """
        sources:
          demo:
            base_url: "https://example.com"
            allowed: true
        """,
    )
    assert load_sources(path)["demo"].allowed is True


def test_missing_base_url_raises(tmp_path):
    path = _write(
        tmp_path,
        """
        sources:
          broken:
            name: "No URL"
        """,
    )
    with pytest.raises(ValueError):
        load_sources(path)
