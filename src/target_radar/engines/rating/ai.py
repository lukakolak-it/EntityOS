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
    criterion_key: str | None = None
    criterion_label: str | None = None
    llm_instruction: str | None = None


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
        source_url, evidence = _first_grounded_context(request.context_text)
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
                    "source_url": source_url,
                    "evidence": evidence,
                }
            ],
        )


@dataclass(frozen=True, slots=True)
class LLMAIRatingProvider:
    router: LLMRouter
    task: str = "light"

    def rate(self, request: AIRatingRequest) -> AIRatingResponse:
        response = self.router.complete(
            _rating_prompt(request),
            task=self.task,
            instructions=_rating_instructions(),
            temperature=0.1,
        )
        payload = _load_json_object(response.text)
        ai_score = _int_between(payload.get("ai_score"), 0, 100)
        confidence = _float_between(payload.get("confidence"), 0, 1)
        return AIRatingResponse(
            ai_score=ai_score,
            confidence=confidence,
            recommended_action=_recommended_action(payload.get("recommended_action")),
            reasons=_list_of_dicts(payload.get("reasons")),
            risks=_list_of_dicts(payload.get("risks")),
            model_name=response.model,
        )


def _rating_instructions() -> str:
    return (
        "You rate target fit for Target Radar. Return exactly one JSON object and "
        "no prose. Required schema: {\"ai_score\": integer 0-100, "
        "\"confidence\": number 0-1, \"recommended_action\": \"skip\"|\"review\"|"
        "\"draft\", \"reasons\": array of objects, \"risks\": array of objects}. "
        "Never return an empty object. Every positive reason must include "
        "source_url and evidence copied from the supplied context. Use only Source "
        "URLs that appear in context_text. Example: {\"ai_score\": 72, \"confidence\": 0.68, "
        "\"recommended_action\": \"review\", \"reasons\": [{\"text\": \"Relevant "
        "role\", \"source_url\": \"https://example.com\", \"evidence\": \"Werkstudent "
        "IT\"}], \"risks\": []}."
    )


def _rating_prompt(request: AIRatingRequest) -> str:
    return json.dumps(
        {
            "task": "Return a Target Radar rating as JSON only.",
            "required_keys": [
                "ai_score",
                "confidence",
                "recommended_action",
                "reasons",
                "risks",
            ],
            "target_domain": request.target_domain,
            "search_terms": request.search_terms,
            "rule_score": request.rule_score,
            "criterion_key": request.criterion_key,
            "criterion_label": request.criterion_label,
            "llm_instruction": request.llm_instruction,
            "context_text": request.context_text,
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def _first_grounded_context(context_text: str) -> tuple[str, str]:
    source_url = "local://rule-rating"
    evidence = context_text[:120]
    lines = [line.strip() for line in context_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not line.startswith("Source: "):
            continue
        source_url = line.removeprefix("Source: ").strip() or source_url
        for next_line in lines[index + 1 :]:
            if next_line.startswith("Evidence: "):
                evidence = next_line.removeprefix("Evidence: ").strip()[:120]
                return source_url, evidence
        return source_url, evidence
    return source_url, evidence


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
    if value is None:
        raise ValueError("LLM rating response missing integer value")
    parsed = int(value)
    return max(minimum, min(maximum, parsed))


def _float_between(value: object, minimum: float, maximum: float) -> float:
    if value is None:
        raise ValueError("LLM rating response missing numeric value")
    parsed = float(value)
    return max(minimum, min(maximum, parsed))


def _recommended_action(value: object) -> RecommendedAction:
    try:
        return RecommendedAction(str(value or "review").strip().lower())
    except ValueError:
        return RecommendedAction.REVIEW


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
