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
        language: str | None = None,
        regenerated_from_draft_id: int | None = None,
    ) -> Draft:
        if target.id is None:
            raise ValueError("target must be persisted before drafting")
        if rating.recommended_action != RecommendedAction.DRAFT:
            raise DraftSkippedError("rating recommended_action must be draft")

        context = self.context_builder.build(
            profile=profile,
            target=target,
            rating=rating,
            evidence=evidence,
            language=language,
        )
        subject, body = self.generator.generate(context, draft_type=draft_type)
        validation = self.validator.validate(
            subject=subject,
            body=body,
            evidence_snippets=context.evidence_snippets,
        )
        if not validation.valid:
            raise DraftValidationError(validation.errors)

        return Draft(
            target_id=target.id,
            score_id=rating.id,
            draft_type=draft_type,
            draft_version=self.draft_version,
            language=context.language,
            subject=subject,
            body=body,
            status=DraftStatus.NEEDS_REVIEW,
            used_context={
                "rating_version": context.rating_version,
                "evidence_count": len(context.evidence_snippets),
            },
            regenerated_from_draft_id=regenerated_from_draft_id,
        )
