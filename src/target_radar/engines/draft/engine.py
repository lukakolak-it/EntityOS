"""DraftEngine MVP implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from target_radar.domain import (
    Draft,
    DraftStatus,
    Evidence,
    Profile,
    RatingResult,
    RecommendedAction,
    Target,
)
from target_radar.engines.draft.context import DraftContextBuilder
from target_radar.engines.draft.templates import TemplateDraftGenerator
from target_radar.engines.draft.validator import DraftValidationError, DraftValidator
from target_radar.use_cases import DraftPolicy


class DraftSkippedError(RuntimeError):
    """Raised when rating does not allow draft generation."""


@dataclass(slots=True)
class DraftEngine:
    context_builder: DraftContextBuilder = field(default_factory=DraftContextBuilder)
    generator: TemplateDraftGenerator = field(default_factory=TemplateDraftGenerator)
    validator: DraftValidator = field(default_factory=DraftValidator)
    draft_version: str = "application-email-v1"

    def create_draft(
        self,
        *,
        profile: Profile,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        draft_type: str = "application_email",
        draft_policy: DraftPolicy | None = None,
        language: str | None = None,
        regenerated_from_draft_id: int | None = None,
    ) -> Draft:
        if target.id is None:
            raise ValueError("target must be persisted before drafting")
        if rating.recommended_action != RecommendedAction.DRAFT:
            raise DraftSkippedError("rating recommended_action must be draft")

        selected_draft_type = draft_policy.draft_type if draft_policy is not None else draft_type
        selected_language = (
            language
            or (draft_policy.language if draft_policy is not None else None)
        )
        max_body_chars = draft_policy.max_length_chars if draft_policy is not None else None
        required_sections = draft_policy.required_sections if draft_policy is not None else ()
        forbidden_claims = draft_policy.forbidden_claims if draft_policy is not None else ()
        context = self.context_builder.build(
            profile=profile,
            target=target,
            rating=rating,
            evidence=evidence,
            language=selected_language,
            max_context_chars=_context_budget(selected_draft_type, max_body_chars),
            max_snippets=_snippet_limit(selected_draft_type),
        )
        subject, body = self.generator.generate(context, draft_type=selected_draft_type)
        validation = self.validator.validate(
            subject=subject,
            body=body,
            evidence_snippets=context.evidence_snippets,
            max_body_chars=max_body_chars,
            required_sections=required_sections,
            forbidden_claims=forbidden_claims,
        )
        if not validation.valid:
            raise DraftValidationError(validation.errors)

        return Draft(
            target_id=target.id,
            score_id=rating.id,
            draft_type=selected_draft_type,
            draft_version=_draft_version(selected_draft_type),
            language=context.language,
            subject=subject,
            body=body,
            status=DraftStatus.NEEDS_REVIEW,
            used_context={
                "rating_version": context.rating_version,
                "evidence_count": len(context.evidence_snippets),
                "evidence_total_chars": context.evidence_total_chars,
                "evidence_truncated": context.evidence_truncated,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "source_url": item.source_url,
                        "evidence_type": item.evidence_type,
                        "context_type": item.context_type,
                        "priority": item.priority,
                    }
                    for item in context.evidence_items
                ],
                "draft_policy": draft_policy.to_dict() if draft_policy is not None else None,
            },
            regenerated_from_draft_id=regenerated_from_draft_id,
        )


def _draft_version(draft_type: str) -> str:
    if draft_type == "research_summary":
        return "research-summary-v1"
    return "application-email-v1"


def _context_budget(draft_type: str, max_body_chars: int | None) -> int:
    if draft_type == "research_summary":
        if max_body_chars is None:
            return 1800
        return max(600, min(1800, max_body_chars // 2))
    return 500


def _snippet_limit(draft_type: str) -> int:
    if draft_type == "research_summary":
        return 4
    return 1
