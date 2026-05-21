"""Search provider abstractions for LeadEngine."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SearchResult:
    url: str
    title: str | None = None
    snippet: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        """Search for a query and return provider-normalized results."""


@dataclass(slots=True)
class FakeSearchProvider:
    """Deterministic provider for tests and local development."""

    results_by_query: dict[str, list[SearchResult]] = field(default_factory=dict)
    name: str = "mock"

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if query in self.results_by_query:
            return self.results_by_query[query][:limit]

        slug = _slug(query)
        return [
            SearchResult(
                url=f"https://{slug}.example/careers",
                title=f"{query} Karriere",
                snippet="Generated fake provider result.",
            )
        ][:limit]


@dataclass(frozen=True, slots=True)
class BraveSearchProvider:
    """Small Brave Web Search adapter isolated behind the provider interface."""

    api_key: str
    country: str = "DE"
    language: str = "de"
    endpoint: str = "https://api.search.brave.com/res/v1/web/search"
    name: str = "brave"

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if not self.api_key:
            raise ValueError("Brave API key is required")

        params = urllib.parse.urlencode(
            {
                "q": query,
                "count": limit,
                "country": self.country,
                "search_lang": self.language,
                "safesearch": "moderate",
            }
        )
        request = urllib.request.Request(
            f"{self.endpoint}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise SearchProviderError(str(exc)) from exc

        web_results = payload.get("web", {}).get("results", [])
        return [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title"),
                snippet=item.get("description"),
                metadata={"provider_rank": index + 1},
            )
            for index, item in enumerate(web_results[:limit])
            if item.get("url")
        ]


class SearchProviderError(RuntimeError):
    """Raised when a search provider call fails."""


def _slug(value: str) -> str:
    cleaned = "".join(
        char.lower() if char.isalnum() else "-"
        for char in value.strip()
        if char.isalnum() or char.isspace() or char in "-_"
    )
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "target"
