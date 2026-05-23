"""Deterministic engine evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from target_radar.config import RatingConfig
from target_radar.domain import (
    Evidence,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
    domain_from_url,
)
from target_radar.engines.draft import DraftEngine, DraftSkippedError
from target_radar.engines.lead import SearchResult
from target_radar.engines.lead.source_quality import SourceQualityClassifier
from target_radar.engines.rating import AIRatingResponse, FakeAIRatingProvider, RatingEngine
from target_radar.use_cases import get_default_use_case


DEFAULT_EVALUATION_FIXTURE = "docs/evaluation/engine-eval-baseline.json"


def run_evaluation(fixture_path: str | Path = DEFAULT_EVALUATION_FIXTURE) -> dict[str, Any]:
    payload = _load_fixture(fixture_path)
    sections = {
        "source_quality": _run_source_quality_cases(payload.get("source_quality", [])),
        "rating": _run_rating_cases(payload.get("rating", [])),
        "draft": _run_draft_cases(payload.get("draft", [])),
    }
    total = sum(section["total"] for section in sections.values())
    passed = sum(section["passed"] for section in sections.values())
    return {
        "suite": payload.get("name", "engine_eval"),
        "source": payload.get("source"),
        "status": "passed" if passed == total else "failed",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": _ratio(passed, total),
        "sections": sections,
    }


def _run_source_quality_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case.get("use_case") or "company_osint"))
        classifier = SourceQualityClassifier.from_source_policy(use_case.source_policy)
        result = classifier.classify(_search_result(case))
        actual = {
            "source_type": result.source_type.value,
            "action": result.recommended_action.value,
            "score": result.score,
        }
        expected = {
            "source_type": case["expected_source_type"],
            "action": case["expected_action"],
        }
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _run_rating_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case["use_case"]))
        rating = RatingEngine(
            config=RatingConfig(),
            ai_provider=_ai_provider(case),
        ).rate(
            _target(case),
            _search_profile(case),
            _evidence(case),
            use_case=use_case,
        )
        actual = {
            "recommended_action": rating.recommended_action.value,
            "rating_status": rating.rating_status,
            "rule_score": rating.rule_score,
            "ai_score": rating.ai_score,
            "confidence": rating.confidence,
            "risk_types": sorted(
                {
                    str(risk.get("type"))
                    for risk in rating.risks
                    if isinstance(risk, dict) and risk.get("type")
                }
            ),
        }
        expected = {
            "recommended_action": case["expected_action"],
            "rating_status": case["expected_status"],
        }
        if "expected_risk_types" in case:
            expected["risk_types"] = sorted(case["expected_risk_types"])
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _run_draft_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case["use_case"]))
        target = _target(case)
        rating = RatingResult(
            target_id=target.id or 1,
            recommended_action=RecommendedAction(case["rating_action"]),
            rule_score=int(case.get("rule_score", 80)),
            ai_score=case.get("ai_score", 80),
            confidence=float(case.get("confidence", 0.75)),
            rating_status=str(case.get("rating_status") or "use_case_rated"),
            rating_version="eval-rating-v1",
        )
        expected_status = str(case["expected_status"])
        try:
            draft = DraftEngine().create_draft(
                profile=_profile(case),
                target=target,
                rating=rating,
                evidence=_evidence(case),
                draft_policy=use_case.draft_policy,
            )
            actual = {
                "status": "generated",
                "draft_type": draft.draft_type,
                "claim_ref_count": len(draft.used_context.get("claim_refs", [])),
                "body_contains": {
                    value: value in draft.body
                    for value in case.get("required_body_contains", [])
                },
            }
        except DraftSkippedError as exc:
            actual = {
                "status": "skipped",
                "error": str(exc),
            }
        expected: dict[str, Any] = {"status": expected_status}
        if expected_status == "generated":
            expected["draft_type"] = case["expected_draft_type"]
            if "expected_claim_ref_count" in case:
                expected["claim_ref_count"] = case["expected_claim_ref_count"]
            expected["body_contains"] = {
                value: True for value in case.get("required_body_contains", [])
            }
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _case_result(
    case_id: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    failures = [
        f"{key}: expected {expected_value!r}, got {actual.get(key)!r}"
        for key, expected_value in expected.items()
        if actual.get(key) != expected_value
    ]
    return {
        "id": case_id,
        "passed": not failures,
        "expected": expected,
        "actual": actual,
        "failures": failures,
    }


def _section_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": _ratio(passed, total),
        "failures": [result for result in results if not result["passed"]],
    }


def _load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("evaluation fixture must contain a JSON object")
    return payload


def _search_result(case: dict[str, Any]) -> SearchResult:
    metadata = dict(case.get("metadata") or {})
    if case.get("provider_rank") is not None:
        metadata["provider_rank"] = case["provider_rank"]
    return SearchResult(
        url=str(case["url"]),
        title=str(case.get("title") or ""),
        snippet=str(case.get("snippet") or ""),
        metadata=metadata,
    )


def _profile(case: dict[str, Any]) -> Profile:
    return Profile(
        id=1,
        name=str(case.get("profile_name") or "Eval Profile"),
        draft_language=str(case.get("draft_language") or "de"),
    )


def _search_profile(case: dict[str, Any]) -> SearchProfile:
    search = case.get("search_profile") or {}
    return SearchProfile(
        id=1,
        profile_id=1,
        name=str(search.get("name") or case.get("id") or "Eval Search"),
        roles=_tuple(search.get("roles")),
        regions=_tuple(search.get("regions")),
        tech_keywords=_tuple(search.get("tech_keywords")),
        industry_keywords=_tuple(search.get("industry_keywords")),
        exclude_keywords=_tuple(search.get("exclude_keywords")),
        attributes=dict(search.get("attributes") or {}),
        draft_language=str(search.get("draft_language") or "de"),
    )


def _target(case: dict[str, Any]) -> Target:
    url = str(case.get("url") or case.get("base_url") or "https://example.com")
    return Target(
        id=int(case.get("target_id") or 1),
        domain=str(case.get("domain") or domain_from_url(url)),
        base_url=url,
        source=str(case.get("source") or "eval"),
        status=TargetStatus.DRAFT_PENDING,
        metadata=dict(case.get("target_metadata") or {}),
    )


def _evidence(case: dict[str, Any]) -> list[Evidence]:
    target_id = int(case.get("target_id") or 1)
    evidence_items = []
    for index, item in enumerate(case.get("evidence") or [], start=1):
        evidence_items.append(
            Evidence(
                id=index,
                target_id=target_id,
                source_url=str(item["source_url"]),
                text=str(item["text"]),
                context_type=str(item.get("context_type") or "page"),
                priority=int(item.get("priority", 50)),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return evidence_items


def _ai_provider(case: dict[str, Any]) -> FakeAIRatingProvider:
    ai_response = case.get("ai_response")
    if not isinstance(ai_response, dict):
        return FakeAIRatingProvider()
    return FakeAIRatingProvider(
        AIRatingResponse(
            ai_score=int(ai_response["ai_score"]),
            confidence=float(ai_response["confidence"]),
            recommended_action=RecommendedAction(ai_response["recommended_action"]),
            reasons=list(ai_response.get("reasons") or []),
            risks=list(ai_response.get("risks") or []),
            model_name=str(ai_response.get("model_name") or "eval-fake-ai"),
        )
    )


def _tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _ratio(passed: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(passed / total, 3)
