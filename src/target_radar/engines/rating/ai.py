"""AI rating provider abstraction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from target_radar.domain import RecommendedAction
from target_radar.llm import LLMRouter


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


@dataclass(frozen=True, slots=True)
class LLMAIRatingProvider:
    router: LLMRouter
    task: str = "heavy"

    def rate(self, request: AIRatingRequest) -> AIRatingResponse:
        response = self.router.complete(
            _rating_prompt(request),
            task=self.task,
            instructions=_rating_instructions(),
            temperature=0.1,
        )
        payload = _load_json_object(response.text)
        action = RecommendedAction(str(payload.get("recommended_action", "review")))
        return AIRatingResponse(
            ai_score=_int_between(payload.get("ai_score"), 0, 100),
            confidence=_float_between(payload.get("confidence"), 0, 1),
            recommended_action=action,
            reasons=_list_of_dicts(payload.get("reasons")),
            risks=_list_of_dicts(payload.get("risks")),
            model_name=response.model,
        )


def _rating_instructions() -> str:
    return (
        "You rate target fit for Target Radar. Return only valid JSON with keys "
        "ai_score, confidence, recommended_action, reasons and risks. "
        "recommended_action must be one of skip, review, draft. Every positive "
        "reason must include source_url and evidence."
    )


def _rating_prompt(request: AIRatingRequest) -> str:
    return json.dumps(
        {
            "target_domain": request.target_domain,
            "search_terms": request.search_terms,
            "rule_score": request.rule_score,
            "context_text": request.context_text,
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def _load_json_object(text: str) -> dict[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM rating response did not contain JSON")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM rating response must be a JSON object")
    return payload


def _int_between(value: object, minimum: int, maximum: int) -> int:
    parsed = int(value)
    return max(minimum, min(maximum, parsed))


def _float_between(value: object, minimum: float, maximum: float) -> float:
    parsed = float(value)
    return max(minimum, min(maximum, parsed))


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
