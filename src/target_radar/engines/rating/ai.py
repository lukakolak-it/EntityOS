"""AI rating provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from target_radar.domain import RecommendedAction


@dataclass(frozen=True, slots=True)
class AIRatingRequest:
    target_domain: str
    search_terms: tuple[str, ...]
    context_text: str
    rule_score: int


@dataclass(frozen=True, slots=True)
class AIRatingResponse:
    ai_score: int
    confidence: float
    recommended_action: RecommendedAction
    reasons: list[dict[str, object]] = field(default_factory=list)
    risks: list[dict[str, object]] = field(default_factory=list)
    model_name: str = "fake-ai"


class AIRatingProvider(Protocol):
    def rate(self, request: AIRatingRequest) -> AIRatingResponse:
        """Return an AI-like qualitative rating."""


@dataclass(frozen=True, slots=True)
class FakeAIRatingProvider:
    response: AIRatingResponse | None = None

    def rate(self, request: AIRatingRequest) -> AIRatingResponse:
        if self.response is not None:
            return self.response
        action = (
            RecommendedAction.DRAFT
            if request.rule_score >= 70
            else RecommendedAction.REVIEW
        )
        return AIRatingResponse(
            ai_score=min(100, max(0, request.rule_score)),
            confidence=0.75,
            recommended_action=action,
            reasons=[
                {
                    "text": "Rule score indicates a relevant target.",
                    "source_url": "local://rule-rating",
                    "evidence": request.context_text[:120],
                }
            ],
        )
