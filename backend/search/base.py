from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        ...
