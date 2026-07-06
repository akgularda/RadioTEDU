from __future__ import annotations

from .base import SearchResult


class DuckDuckGoSearchProvider:
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        return [SearchResult(title="Search unavailable", url="", snippet="DuckDuckGo adapter is not configured.", source="duckduckgo")]
