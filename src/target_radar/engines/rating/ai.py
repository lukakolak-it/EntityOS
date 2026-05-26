"""AI rating provider abstraction."""

from __future__ import annotations

import json
import re
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
        ai_score = _int_between(
            _first_present(payload, ("ai_score", "score", "rating_score")),
            0,
            100,
        )
        confidence = _float_between(
            _first_present(payload, ("confidence", "certainty", "confidence_score")),
            0,
            1,
        )
        return AIRatingResponse(
            ai_score=ai_score,
            confidence=confidence,
            recommended_action=_recommended_action(payload.get("recommended_action")),
            reasons=_reason_dicts(payload.get("reasons"), request.context_text),
            risks=_risk_dicts(payload.get("risks")),
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
    parsed = round(_coerce_numeric(value, maximum=maximum))
    return max(minimum, min(maximum, parsed))


def _float_between(value: object, minimum: float, maximum: float) -> float:
    if value is None:
        raise ValueError("LLM rating response missing numeric value")
    parsed = _coerce_numeric(value, maximum=maximum)
    return max(minimum, min(maximum, parsed))


def _recommended_action(value: object) -> RecommendedAction:
    normalized = str(value or "review").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "accept": RecommendedAction.DRAFT,
        "approve": RecommendedAction.DRAFT,
        "approved": RecommendedAction.DRAFT,
        "go": RecommendedAction.DRAFT,
        "include_in_osint_collection": RecommendedAction.DRAFT,
        "recommended": RecommendedAction.DRAFT,
        "yes": RecommendedAction.DRAFT,
        "maybe": RecommendedAction.REVIEW,
        "needs_context": RecommendedAction.REVIEW,
        "needs_review": RecommendedAction.REVIEW,
        "review_needed": RecommendedAction.REVIEW,
        "not_relevant": RecommendedAction.SKIP,
        "no": RecommendedAction.SKIP,
        "reject": RecommendedAction.SKIP,
        "rejected": RecommendedAction.SKIP,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return RecommendedAction(normalized)
    except ValueError:
        return RecommendedAction.REVIEW


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _reason_dicts(value: object, context_text: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    reasons: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            reasons.append(item)
        elif isinstance(item, str) and item.strip():
            reasons.append(_ground_reason_text(item, context_text))
    return reasons


def _risk_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    risks: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            risks.append(item)
        elif isinstance(item, str) and item.strip():
            risks.append({"type": "llm_risk", "value": item.strip()})
    return risks


def _first_present(payload: dict[str, object], keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


_LABEL_VALUES = {
    "very_high": 0.95,
    "excellent": 0.95,
    "certain": 0.95,
    "high": 0.85,
    "good": 0.8,
    "hoch": 0.85,
    "medium": 0.55,
    "moderate": 0.55,
    "average": 0.55,
    "mittel": 0.55,
    "low": 0.25,
    "weak": 0.25,
    "niedrig": 0.25,
    "very_low": 0.1,
    "uncertain": 0.35,
}
_FRACTION_RE = re.compile(r"(-?\d+(?:[\.,]\d+)?)\s*/\s*(-?\d+(?:[\.,]\d+)?)")
_NUMBER_RE = re.compile(r"-?\d+(?:[\.,]\d+)?")


def _coerce_numeric(value: object, *, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError("LLM rating response numeric value must not be boolean")
    if isinstance(value, (int, float)):
        return _scale_number(float(value), maximum=maximum)
    text = str(value).strip().lower()
    if not text:
        raise ValueError("LLM rating response numeric value is empty")
    normalized_label = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if normalized_label in _LABEL_VALUES:
        return _LABEL_VALUES[normalized_label] * maximum

    fraction = _FRACTION_RE.search(text)
    if fraction is not None:
        numerator = float(fraction.group(1).replace(",", "."))
        denominator = float(fraction.group(2).replace(",", "."))
        if denominator == 0:
            raise ValueError("LLM rating response numeric fraction denominator is zero")
        return (numerator / denominator) * maximum

    match = _NUMBER_RE.search(text)
    if match is None:
        raise ValueError(f"LLM rating response numeric value is not parseable: {value!r}")
    number = float(match.group(0).replace(",", "."))
    if "%" in text:
        return (number / 100) * maximum
    return _scale_number(number, maximum=maximum)


def _scale_number(number: float, *, maximum: float) -> float:
    if maximum <= 1 and number > 1:
        return number / 100
    if maximum > 1 and 0 < number < 1:
        return number * maximum
    if maximum > 1 and 1 <= number <= 5:
        return (number / 5) * maximum
    return number


_CONTEXT_ENTRY_RE = re.compile(
    r"Source:\s*(?P<source>.*?)\nEvidence:\s*(?P<evidence>.*?)(?=\n\nSource:|\Z)",
    re.DOTALL,
)
_REASON_STOPWORDS = frozenset(
    {
        "about",
        "and",
        "are",
        "der",
        "die",
        "for",
        "from",
        "has",
        "ist",
        "mit",
        "not",
        "oder",
        "the",
        "this",
        "und",
        "with",
    }
)


def _ground_reason_text(reason_text: str, context_text: str) -> dict[str, object]:
    reason = reason_text.strip()
    entries = _context_entries(context_text)
    if not entries:
        return {"text": reason}
    reason_tokens = _reason_tokens(reason)
    source_url, evidence = max(
        entries,
        key=lambda item: _token_overlap(reason_tokens, _reason_tokens(item[1])),
    )
    return {
        "text": reason,
        "source_url": source_url,
        "evidence": _evidence_excerpt(evidence, reason_tokens),
    }


def _context_entries(context_text: str) -> list[tuple[str, str]]:
    entries = []
    for match in _CONTEXT_ENTRY_RE.finditer(context_text):
        source = match.group("source").strip()
        evidence = match.group("evidence").strip()
        if source and evidence:
            entries.append((source, evidence))
    return entries


def _reason_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+", value.casefold(), flags=re.UNICODE)
        if len(token) >= 4 and token not in _REASON_STOPWORDS
    }


def _token_overlap(left: set[str], right: set[str]) -> int:
    if not left or not right:
        return 0
    return len(left & right)


def _evidence_excerpt(evidence: str, reason_tokens: set[str], *, max_chars: int = 220) -> str:
    cleaned = " ".join(evidence.split())
    if len(cleaned) <= max_chars:
        return cleaned
    lowered = cleaned.casefold()
    positions = [
        lowered.find(token)
        for token in reason_tokens
        if lowered.find(token) >= 0
    ]
    center = min(positions) if positions else 0
    start = max(0, center - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    return cleaned[start:end].strip()
