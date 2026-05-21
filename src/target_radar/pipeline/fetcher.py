"""Controlled page fetching for targets."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int | None = None
    body: str | None = None
    content_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error_message is None and self.status_code is not None


@dataclass(frozen=True, slots=True)
class FetchConfig:
    timeout_seconds: float = 10.0
    user_agent: str = "TargetRadar/0.1 local"
    max_bytes: int = 1_000_000


class HttpFetcher:
    """Small HTTP fetcher with explicit timeout and bounded response size."""

    def __init__(self, config: FetchConfig | None = None) -> None:
        self.config = config or FetchConfig()

    def fetch(self, url: str) -> FetchedPage:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.user_agent},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                raw = response.read(self.config.max_bytes)
                content_type = response.headers.get("Content-Type")
                encoding = response.headers.get_content_charset() or "utf-8"
                return FetchedPage(
                    url=url,
                    status_code=response.status,
                    body=raw.decode(encoding, errors="replace"),
                    content_type=content_type,
                    metadata={"bytes_read": len(raw)},
                )
        except urllib.error.HTTPError as exc:
            return FetchedPage(
                url=url,
                status_code=exc.code,
                error_message=str(exc),
            )
        except urllib.error.URLError as exc:
            return FetchedPage(url=url, error_message=str(exc.reason))


@dataclass(slots=True)
class FakeFetcher:
    """Fixture-backed fetcher for tests."""

    pages: dict[str, FetchedPage]

    def fetch(self, url: str) -> FetchedPage:
        return self.pages.get(url) or FetchedPage(
            url=url,
            error_message="fixture not found",
        )
