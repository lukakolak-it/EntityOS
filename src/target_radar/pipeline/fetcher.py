"""Controlled page fetching for targets."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html import escape
from urllib.parse import urlparse


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


@dataclass(frozen=True, slots=True)
class GeneratedFakeFetcher:
    """Generate deterministic HTML pages for local demos and tests."""

    terms: tuple[str, ...] = ()

    def fetch(self, url: str) -> FetchedPage:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/", 1)[0] or "example.local"
        page_terms = " ".join(term for term in self.terms if term.strip())
        if not page_terms:
            page_terms = "Werkstudent IT Python Essen"
        body = _generated_html(url=url, domain=domain, terms=page_terms)
        return FetchedPage(
            url=url,
            status_code=200,
            body=body,
            content_type="text/html; charset=utf-8",
            metadata={"generated": True, "bytes_read": len(body.encode("utf-8"))},
        )


def _generated_html(*, url: str, domain: str, terms: str) -> str:
    escaped_domain = escape(domain)
    escaped_terms = escape(terms)
    escaped_url = escape(url)
    local_part = domain.replace(".", "-").replace(":", "-")
    return (
        "<!doctype html><html><head>"
        f"<title>Karriere bei {escaped_domain}</title>"
        f'<meta name="description" content="Lokale Testseite fuer {escaped_terms}">'
        "</head><body>"
        f"<h1>Karriere und Jobs bei {escaped_domain}</h1>"
        f"<p>Wir suchen Profile rund um {escaped_terms} fuer lokale Projekte.</p>"
        "<p>Interessierte koennen sich direkt beim Team melden.</p>"
        f"<p>Kontakt: jobs@{escape(local_part)}.test</p>"
        f'<a href="{escaped_url}">Karriere</a>'
        "</body></html>"
    )
