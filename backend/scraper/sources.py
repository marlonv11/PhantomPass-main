"""Load and validate the configurable scraping sources registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    base_url: str
    allowed: bool
    selectors: dict[str, str]
    notes: str = ""


def load_sources(path: str | Path) -> dict[str, Source]:
    """Parse a sources.yaml file into a {key: Source} mapping.

    Raises ValueError on malformed entries. `allowed` defaults to False so a
    source is never scraped without explicit opt-in.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_sources = data.get("sources") or {}
    if not isinstance(raw_sources, dict):
        raise ValueError("'sources' must be a mapping of key -> config")

    sources: dict[str, Source] = {}
    for key, cfg in raw_sources.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"source '{key}' must be a mapping")
        base_url = cfg.get("base_url")
        if not base_url:
            raise ValueError(f"source '{key}' is missing 'base_url'")
        selectors = cfg.get("selectors") or {}
        if not isinstance(selectors, dict):
            raise ValueError(f"source '{key}' selectors must be a mapping")
        sources[key] = Source(
            key=key,
            name=cfg.get("name", key),
            base_url=base_url,
            allowed=bool(cfg.get("allowed", False)),
            selectors={str(k): str(v) for k, v in selectors.items()},
            notes=cfg.get("notes", ""),
        )
    return sources
