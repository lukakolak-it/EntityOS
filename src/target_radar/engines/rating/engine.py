"""RatingEngine MVP implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from target_radar.config import RatingConfig
from target_radar.domain import (
    Evidence,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
)
from target_radar.engines.rating.ai import (
    AIRatingProvider,
    AIRatingRequest,
    AIRatingResponse,
)
from target_radar.engines.rating.rules import RuleRater


@dataclass(slots=True)
class RatingEngine:
    config: RatingConfig = field(default_factory=RatingConfig)
    rule_rater: RuleRater = field(default_factory=RuleRater)
    ai_provider: AIRatingProvider | None = None
    rating_version: str = "rules-v1"

    def rate(
        self,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
        *,
        pipeline_run_id: int | None = None,
    ) -> RatingResult:
        rule_result = self.rule_rater.rate(target, search_profile, evidence)
        evidence_payload = _evidence_payload(evidence)
        context_text = " ".join(item.text for item in evidence)

        if rule_result.hard_stop:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_result.score,
                recommended_action=RecommendedAction.SKIP,
                rating_status="rule_skipped",
                rating_version=self.rating_version,
                reasons=rule_result.reasons,
                risks=rule_result.risks,
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence),
            )

        if not evidence:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_result.score,
                recommended_action=RecommendedAction.REVIEW,
                rating_status="rating_partial",
                rating_version=self.rating_version,
                reasons=rule_result.reasons,
                risks=rule_result.risks,
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence),
            )

        if rule_result.score < self.config.min_rule_score_for_ai:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_result.score,
                recommended_action=RecommendedAction.SKIP,
                rating_status="rule_skipped",
                rating_version=self.rating_version,
                reasons=rule_result.reasons,
                risks=rule_result.risks,
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence),
            )

        if self.ai_provider is None:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_result.score,
                recommended_action=RecommendedAction.REVIEW,
                rating_status="rating_partial",
                rating_version=self.rating_version,
                reasons=rule_result.reasons,
                risks=rule_result.risks
                + [{"type": "missing_ai_provider", "value": "AI rating skipped"}],
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence),
            )

        ai_response = self.ai_provider.rate(
            AIRatingRequest(
                target_domain=target.domain,
                search_terms=(
                    search_profile.roles
                    + search_profile.tech_keywords
                    + search_profile.regions
                ),
                context_text=context_text,
                rule_score=rule_result.score,
            )
        )
        return self._merge(
            target=target,
            search_profile=search_profile,
            evidence=evidence,
            rule_result=rule_result,
            ai_response=ai_response,
            pipeline_run_id=pipeline_run_id,
        )

    def _merge(
        self,
        *,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
        rule_result,
        ai_response: AIRatingResponse,
        pipeline_run_id: int | None,
    ) -> RatingResult:
        evidence_payload = _evidence_payload(evidence)
        evidence_ok = _ai_reasons_have_evidence(ai_response)
        confidence = ai_response.confidence if evidence_ok else min(ai_response.confidence, 0.4)

        if not evidence_ok:
            action = RecommendedAction.REVIEW
            rating_status = "rating_partial"
            risks = rule_result.risks + [
                {"type": "missing_ai_evidence", "value": "AI reasons lack sources"}
            ]
        else:
            action = _decision_merge(self.config, ai_response.ai_score, confidence)
            rating_status = "ai_passed"
            risks = rule_result.risks + ai_response.risks

        return RatingResult(
            target_id=_target_id(target),
            pipeline_run_id=pipeline_run_id,
            rule_score=rule_result.score,
            ai_score=ai_response.ai_score,
            raw_confidence=ai_response.confidence,
            confidence=confidence,
            recommended_action=action,
            rating_status=rating_status,
            rating_version=self.rating_version + "+ai-v1",
            reasons=rule_result.reasons + ai_response.reasons,
            risks=risks,
            evidence=evidence_payload,
            input_snapshot=_input_snapshot(search_profile, evidence),
        )


def _decision_merge(
    config: RatingConfig,
    ai_score: int,
    confidence: float,
) -> RecommendedAction:
    if (
        ai_score >= config.min_ai_score_for_draft
        and confidence >= config.min_confidence_for_draft
    ):
        return RecommendedAction.DRAFT
    if ai_score >= config.min_ai_score_for_review:
        return RecommendedAction.REVIEW
    return RecommendedAction.SKIP


def _ai_reasons_have_evidence(response: AIRatingResponse) -> bool:
    if not response.reasons:
        return False
    return all(reason.get("source_url") and reason.get("evidence") for reason in response.reasons)


def _evidence_payload(evidence: list[Evidence]) -> list[dict[str, object]]:
    return [
        {
            "evidence_id": item.id,
            "source_url": item.source_url,
            "context_type": item.context_type,
        }
        for item in evidence
    ]


def _input_snapshot(
    search_profile: SearchProfile,
    evidence: list[Evidence],
) -> dict[str, object]:
    return {
        "search_profile_id": search_profile.id,
        "evidence_ids": [item.id for item in evidence],
    }


def _target_id(target: Target) -> int:
    if target.id is None:
        raise ValueError("target must be persisted before rating")
    return target.id
