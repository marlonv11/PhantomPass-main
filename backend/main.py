"""Orquestador CLI: scrape una fuente configurada o una URL ad-hoc.

Uso:
  python backend/main.py --list-sources
  python backend/main.py --source example
  python backend/main.py --url https://example.com --selector h1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scraper.extractor import RobotsDisallowedError, Scraper
from scraper.data_cleaner import clean_text
from scraper.sources import Source, load_sources

DEFAULT_SOURCES = Path(__file__).resolve().parent / "sources.yaml"


def scrape_source(scraper: Scraper, source: Source) -> dict[str, str]:
    """Fetch the source once and extract each configured field."""
    html = scraper.fetch(source.base_url)
    return {
        field: clean_text(scraper.extract_text(html, selector))
        for field, selector in source.selectors.items()
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PhantomPass scraper (ethical use only).")
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES), help="Path to sources.yaml")
    parser.add_argument("--list-sources", action="store_true", help="List configured sources")
    parser.add_argument("--source", help="Key of a configured source to scrape")
    parser.add_argument("--url", help="Ad-hoc URL to fetch")
    parser.add_argument("--selector", default=None, help="CSS selector for ad-hoc fetch")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    sources = load_sources(args.sources)

    if args.list_sources:
        for key, src in sources.items():
            flag = "allowed" if src.allowed else "blocked"
            print(f"{key}\t{src.name}\t{src.base_url}\t[{flag}]")
        return 0

    scraper = Scraper()

    if args.source:
        source = sources.get(args.source)
        if source is None:
            print(f"[error] unknown source '{args.source}'", file=sys.stderr)
            return 2
        if not source.allowed:
            print(f"[skip] source '{args.source}' is not marked allowed", file=sys.stderr)
            return 2
        try:
            record = scrape_source(scraper, source)
        except RobotsDisallowedError as exc:
            print(f"[skip] {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # network / HTTP errors
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    if args.url:
        try:
            html = scraper.fetch(args.url)
        except RobotsDisallowedError as exc:
            print(f"[skip] {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        print(clean_text(scraper.extract_text(html, args.selector)))
        return 0

    parser.error("use --list-sources, --source <key>, or --url <url>")


if __name__ == "__main__":
    raise SystemExit(main())
