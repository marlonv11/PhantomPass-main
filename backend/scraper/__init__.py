"""Scraper package: fetch/parse (extractor) and normalization (data_cleaner)."""

from .extractor import Scraper, RobotsDisallowedError
from .data_cleaner import clean_text

__all__ = ["Scraper", "RobotsDisallowedError", "clean_text"]
