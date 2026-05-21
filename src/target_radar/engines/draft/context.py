"""Draft context building."""

from __future__ import annotations

from dataclasses import dataclass

from target_radar.domain import Evidence, Profile, RatingResult, RecommendedAction, Target


@dataclass(frozen=True, slots=True)
class DraftContext:
    profile_name: str
    target_domain: str
    language: str
    recommended_action: RecommendedAction
    evidence_snippets: tuple[str, ...]
    risks: tuple[dict[str, object], ...]
    rating_version: str


class DraftContextBuilder:
    def build(
        self,
        *,
        profile: Profile,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        language: str | None = None,
        max_snippet_chars: int = 500,
    ) -> DraftContext:
        snippets = tuple(
            item.text[:max_snippet_chars]
            for item in evidence
            if item.text.strip()
        )
        return DraftContext(
            profile_name=profile.name,
            target_domain=target.domain,
            language=language or profile.draft_language,
            recommended_action=rating.recommended_action,
            evidence_snippets=snippets,
            risks=tuple(rating.risks),
            rating_version=rating.rating_version,
        )
