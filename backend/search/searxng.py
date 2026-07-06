from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .base import SearchResult


class SearXNGSearchProvider:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        params = urllib.parse.urlencode({"q": query, "format": "json"})
        url = f"{self.base_url}/search?{params}"
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        results = []
        for item in payload.get("results", [])[:limit]:
            results.append(
                SearchResult(
                    title=str(item.get("title") or "Untitled"),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("content") or ""),
                    source="searxng",
                )
            )
        return results
