"""Normalization helpers for scraped data."""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Collapse whitespace and trim."""
    return _WHITESPACE.sub(" ", text).strip()


def dedupe(items: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def clean_records(records: list[dict]) -> list[dict]:
    """Apply clean_text to every string value in each record."""
    cleaned: list[dict] = []
    for record in records:
        cleaned.append(
            {k: (clean_text(v) if isinstance(v, str) else v) for k, v in record.items()}
        )
    return cleaned
