"""HTML extraction for fetched target pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    url: str
    page_type: str
    title: str | None = None
    description: str | None = None
    text: str = ""
    links: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


class HtmlExtractor:
    def extract(self, url: str, html: str) -> ExtractedPage:
        parser = _ReadableHtmlParser(url)
        parser.feed(html)
        text = _compact_text(" ".join(parser.text_parts))
        emails = tuple(sorted(set(EMAIL_PATTERN.findall(text))))

        return ExtractedPage(
            url=url,
            page_type=classify_page_type(url, parser.title, text),
            title=parser.title,
            description=parser.description,
            text=text,
            links=tuple(parser.links),
            emails=emails,
            metadata={"link_count": len(parser.links), "email_count": len(emails)},
        )


def classify_page_type(url: str, title: str | None = None, text: str = "") -> str:
    haystack = " ".join(
        part
        for part in (urlparse(url).path, title or "", text[:500])
        if part
    ).lower()
    if any(token in haystack for token in ("career", "karriere", "jobs", "stellen")):
        return "career"
    if "contact" in haystack or "kontakt" in haystack or "impressum" in haystack:
        return "contact"
    if "about" in haystack or "ueber-uns" in haystack or "uber-uns" in haystack:
        return "about"
    if urlparse(url).path in ("", "/"):
        return "homepage"
    return "other"


class _ReadableHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title: str | None = None
        self.description: str | None = None
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._tag_stack: list[str] = []
        self._capturing_title = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        self._tag_stack.append(tag)

        if tag == "title":
            self._capturing_title = True
        elif tag == "a" and attrs_map.get("href"):
            self.links.append(urljoin(self.base_url, attrs_map["href"] or ""))
        elif tag == "meta":
            name = (attrs_map.get("name") or attrs_map.get("property") or "").lower()
            if name in {"description", "og:description"} and attrs_map.get("content"):
                self.description = attrs_map["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capturing_title = False
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not data.strip() or self._is_ignored_context:
            return
        if self._capturing_title:
            self.title = _compact_text(data)
        else:
            self.text_parts.append(data)

    @property
    def _is_ignored_context(self) -> bool:
        return any(tag in {"script", "style", "noscript"} for tag in self._tag_stack)


def _compact_text(value: str) -> str:
    return " ".join(value.split()).strip()
