"""Evidence construction and provenance tagging."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from target_radar.domain import Evidence, TargetPage


class EvidenceType(StrEnum):
    TARGET_HOMEPAGE = "target_homepage"
    TARGET_CAREER = "target_career"
    TARGET_CONTACT = "target_contact"
    TARGET_ABOUT = "target_about"
    TARGET_PAGE = "target_page"
    CONTEXT_DIRECTORY = "context_directory"
    CONTEXT_NEWS = "context_news"
    CONTEXT_REGISTRY = "context_registry"
    CONTEXT_REPOSITORY = "context_repository"
    CONTEXT_SOURCE = "context_source"


@dataclass(frozen=True, slots=True)
class EvidenceEngine:
    """Build typed Evidence objects from target pages and context sources."""

    max_page_chars: int = 5000
    max_context_chars: int = 2000

    def from_target_page(
        self,
        page: TargetPage,
        *,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence | None:
        body = _clip(text if text is not None else page.text or "", self.max_page_chars)
        if not body:
            return None

        context_type = _target_context_type(page.page_type)
        evidence_type = _target_evidence_type(context_type)
        evidence_metadata = _clean_metadata(metadata or {})
        evidence_metadata.update(
            _clean_metadata(
                {
                    "evidence_type": evidence_type.value,
                    "provenance": "target_page",
                    "page_id": page.id,
                    "page_type": page.page_type,
                    "source_url": page.url,
                    "title": page.title,
                }
            )
        )

        return Evidence(
            target_id=page.target_id,
            page_id=page.id,
            source_url=page.url,
            text=body,
            context_type=context_type,
            priority=_target_priority(context_type),
            metadata=evidence_metadata,
        )

    def from_context_source(
        self,
        *,
        target_id: int,
        context_source: dict[str, Any],
    ) -> Evidence | None:
        title = str(context_source.get("title") or "").strip()
        snippet = str(context_source.get("snippet") or "").strip()
        source_url = str(context_source.get("url") or "").strip()
        if not source_url:
            return None
        body = _clip(
            " ".join(part for part in (title, snippet) if part),
            self.max_context_chars,
        )
        if not body:
            body = _clip(source_url, self.max_context_chars)
        if not body:
            return None

        metadata = context_source.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        source_quality = metadata.get("source_quality")
        if not isinstance(source_quality, dict):
            source_quality = {}
        source_type = str(source_quality.get("source_type") or "unknown")
        evidence_type = _context_evidence_type(source_type)

        evidence_metadata = _clean_metadata(
            {
                "evidence_type": evidence_type.value,
                "provenance": "context_source",
                "context_source_id": context_source.get("id"),
                "source_query_id": context_source.get("source_query_id"),
                "pipeline_run_id": context_source.get("pipeline_run_id"),
                "search_profile_id": context_source.get("search_profile_id"),
                "use_case_id": context_source.get("use_case_id"),
                "use_case_slug": context_source.get("use_case_slug"),
                "query_text": context_source.get("query_text"),
                "query_template": context_source.get("query_template"),
                "template_set": context_source.get("template_set"),
                "domain": context_source.get("domain"),
                "title": title,
                "snippet": snippet,
                "source_type": source_type,
                "source_quality_score": source_quality.get("source_quality_score"),
                "source_quality": source_quality or None,
            }
        )

        return Evidence(
            target_id=target_id,
            source_url=source_url,
            text=body,
            context_type="context_source",
            priority=_context_priority(source_type),
            metadata=evidence_metadata,
        )


def _target_context_type(page_type: str) -> str:
    if page_type in {"career", "contact", "about", "homepage"}:
        return page_type
    return "page"


def _target_evidence_type(context_type: str) -> EvidenceType:
    return {
        "career": EvidenceType.TARGET_CAREER,
        "contact": EvidenceType.TARGET_CONTACT,
        "about": EvidenceType.TARGET_ABOUT,
        "homepage": EvidenceType.TARGET_HOMEPAGE,
    }.get(context_type, EvidenceType.TARGET_PAGE)


def _context_evidence_type(source_type: str) -> EvidenceType:
    return {
        "directory": EvidenceType.CONTEXT_DIRECTORY,
        "news": EvidenceType.CONTEXT_NEWS,
        "registry": EvidenceType.CONTEXT_REGISTRY,
        "repository": EvidenceType.CONTEXT_REPOSITORY,
    }.get(source_type, EvidenceType.CONTEXT_SOURCE)


def _target_priority(context_type: str) -> int:
    return {
        "career": 100,
        "contact": 80,
        "about": 60,
        "homepage": 40,
    }.get(context_type, 10)


def _context_priority(source_type: str) -> int:
    return {
        "registry": 85,
        "official_site": 85,
        "news": 65,
        "directory": 60,
        "repository": 55,
    }.get(source_type, 35)


def _clip(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "."


def _clean_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item is not None and item != "" and item != []
    }
