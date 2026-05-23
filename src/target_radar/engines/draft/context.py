"""Draft context building."""

from __future__ import annotations

from dataclasses import dataclass

from target_radar.domain import Evidence, Profile, RatingResult, RecommendedAction, Target


@dataclass(frozen=True, slots=True)
class DraftEvidenceSnippet:
    ref: str
    text: str
    source_url: str
    evidence_id: int | None
    evidence_type: str
    context_type: str
    priority: int


@dataclass(frozen=True, slots=True)
class DraftContext:
    profile_name: str
    target_domain: str
    language: str
    recommended_action: RecommendedAction
    evidence_snippets: tuple[str, ...]
    evidence_items: tuple[DraftEvidenceSnippet, ...]
    risks: tuple[dict[str, object], ...]
    rating_version: str
    evidence_total_chars: int
    evidence_truncated: bool


class DraftContextBuilder:
    DEFAULT_CONTEXT_BUDGET_CHARS = 1800
    DEFAULT_MAX_SNIPPETS = 4

    def build(
        self,
        *,
        profile: Profile,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        language: str | None = None,
        max_snippet_chars: int = 500,
        max_context_chars: int | None = None,
        max_snippets: int | None = None,
    ) -> DraftContext:
        budget = max_context_chars or self.DEFAULT_CONTEXT_BUDGET_CHARS
        snippet_limit = max_snippets or self.DEFAULT_MAX_SNIPPETS
        ranked = sorted(
            (item for item in evidence if item.text.strip()),
            key=_evidence_sort_key,
        )
        items: list[DraftEvidenceSnippet] = []
        used_chars = 0
        truncated = False
        for item in ranked:
            if len(items) >= snippet_limit or used_chars >= budget:
                truncated = True
                break
            remaining = budget - used_chars
            limit = min(max_snippet_chars, remaining)
            text = _clip(item.text, limit)
            if not text:
                continue
            items.append(
                DraftEvidenceSnippet(
                    ref=f"E{len(items) + 1}",
                    text=text,
                    source_url=item.source_url,
                    evidence_id=item.id,
                    evidence_type=_evidence_type(item),
                    context_type=item.context_type,
                    priority=item.priority,
                )
            )
            used_chars += len(text)
            if len(item.text.strip()) > len(text):
                truncated = True
        return DraftContext(
            profile_name=profile.name,
            target_domain=target.domain,
            language=language or profile.draft_language,
            recommended_action=rating.recommended_action,
            evidence_snippets=tuple(item.text for item in items),
            evidence_items=tuple(items),
            risks=tuple(rating.risks),
            rating_version=rating.rating_version,
            evidence_total_chars=used_chars,
            evidence_truncated=truncated,
        )


def _evidence_sort_key(evidence: Evidence) -> tuple[int, int, str]:
    return (
        -_type_priority(_evidence_type(evidence)),
        -evidence.priority,
        evidence.source_url,
    )


def _type_priority(evidence_type: str) -> int:
    priorities = {
        "context_registry": 120,
        "context_news": 105,
        "context_directory": 100,
        "target_contact": 90,
        "target_about": 80,
        "target_homepage": 70,
        "target_career": 60,
        "target_page": 50,
        "context_repository": 45,
        "context_source": 40,
    }
    return priorities.get(evidence_type, 10)


def _evidence_type(evidence: Evidence) -> str:
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    explicit_type = metadata.get("evidence_type")
    if explicit_type:
        return str(explicit_type)
    return {
        "homepage": "target_homepage",
        "career": "target_career",
        "contact": "target_contact",
        "about": "target_about",
        "page": "target_page",
        "context_source": "context_source",
    }.get(evidence.context_type, "target_page")


def _clip(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 1:
        return "."
    return cleaned[: max_chars - 1].rstrip() + "."
