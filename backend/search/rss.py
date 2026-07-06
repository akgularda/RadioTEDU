from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .base import SearchResult


class RSSSearchProvider:
    def __init__(self, feeds_path: str, ttl_seconds: int = 300) -> None:
        self.feeds_path = Path(feeds_path)
        self.ttl_seconds = ttl_seconds
        self._cached_at = 0.0
        self._cache: list[SearchResult] = []

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        results = self._items()
        if query:
            needle = query.lower()
            ranked = [item for item in results if needle in (item.title + " " + item.snippet).lower()]
            results = ranked or results
        return results[:limit]

    def _items(self) -> list[SearchResult]:
        if time.time() - self._cached_at < self.ttl_seconds:
            return self._cache
        feeds = self._feed_urls()
        items: list[SearchResult] = []
        for url in feeds[:8]:
            try:
                with urllib.request.urlopen(url, timeout=4) as response:
                    xml = response.read()
                root = ET.fromstring(xml)
            except Exception:
                continue
            for item in root.findall(".//item")[:8]:
                title = item.findtext("title") or "Untitled"
                link = item.findtext("link") or url
                summary = item.findtext("description") or ""
                items.append(SearchResult(title=title, url=link, snippet=summary[:280], source="rss"))
        self._cache = items
        self._cached_at = time.time()
        return items

    def _feed_urls(self) -> list[str]:
        if not self.feeds_path.exists():
            return []
        try:
            payload = json.loads(self.feeds_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict):
            return [str(item) for item in payload.get("feeds", [])]
        return []
