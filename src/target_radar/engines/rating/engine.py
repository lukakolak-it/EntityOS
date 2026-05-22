"""RatingEngine MVP implementation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

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
    LLMAIRatingProvider,
)
from target_radar.engines.rating.rules import RuleRater
from target_radar.use_cases import RatingCriterion, RatingEvaluation, UseCaseConfig


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
        use_case: UseCaseConfig | None = None,
    ) -> RatingResult:
        if use_case is not None:
            return self._rate_with_use_case(
                target,
                search_profile,
                evidence,
                pipeline_run_id=pipeline_run_id,
                use_case=use_case,
            )

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

        try:
            ai_response = self.ai_provider.rate(
                AIRatingRequest(
                    target_domain=target.domain,
                    search_terms=_search_terms(search_profile),
                    context_text=context_text,
                    rule_score=rule_result.score,
                )
            )
        except Exception as exc:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_result.score,
                recommended_action=RecommendedAction.REVIEW,
                rating_status="rating_partial",
                rating_version=self.rating_version,
                reasons=rule_result.reasons,
                risks=rule_result.risks
                + [{"type": "ai_provider_error", "value": str(exc)}],
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence),
                error_type=exc.__class__.__name__,
                error_message=str(exc),
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

    def _rate_with_use_case(
        self,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
        *,
        pipeline_run_id: int | None,
        use_case: UseCaseConfig,
    ) -> RatingResult:
        rule_gate = self.rule_rater.rate(target, search_profile, evidence)
        evidence_payload = _evidence_payload(evidence)
        if rule_gate.hard_stop:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_gate.score,
                recommended_action=RecommendedAction.SKIP,
                rating_status="rule_skipped",
                rating_version=f"{self.rating_version}+usecase-v{use_case.version}",
                reasons=rule_gate.reasons,
                risks=rule_gate.risks,
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence, use_case=use_case),
            )
        if not evidence:
            return RatingResult(
                target_id=_target_id(target),
                pipeline_run_id=pipeline_run_id,
                rule_score=rule_gate.score,
                recommended_action=RecommendedAction.REVIEW,
                rating_status="rating_partial",
                rating_version=f"{self.rating_version}+usecase-v{use_case.version}",
                reasons=rule_gate.reasons,
                risks=rule_gate.risks,
                evidence=evidence_payload,
                input_snapshot=_input_snapshot(search_profile, evidence, use_case=use_case),
            )

        context_text = " ".join(item.text for item in evidence)
        ai_provider = self._ai_provider_for_mode(use_case.rating_policy.llm_mode)
        criterion_results = [
            self._score_criterion(
                criterion,
                target,
                search_profile,
                evidence,
                context_text=context_text,
                ai_provider=ai_provider,
            )
            for criterion in use_case.rating_policy.criteria
        ]
        final_score = round(
            sum(item["score"] * item["weight"] / 100 for item in criterion_results)
        )
        ai_scores = [item["ai_score"] for item in criterion_results if item["ai_score"] is not None]
        raw_confidence_values = [
            item["confidence"]
            for item in criterion_results
            if item["confidence"] is not None
        ]
        raw_confidence = (
            sum(raw_confidence_values) / len(raw_confidence_values)
            if raw_confidence_values
            else None
        )
        confidence = raw_confidence if raw_confidence is not None else 0.6
        missing_llm = any(item["missing_llm"] for item in criterion_results)
        reasons = rule_gate.reasons + [
            {
                "type": "criterion_score",
                "criterion": item["key"],
                "evaluation": item["evaluation"],
                "score": item["score"],
                "weight": item["weight"],
                "weighted_score": round(item["score"] * item["weight"] / 100, 2),
            }
            for item in criterion_results
        ] + [reason for item in criterion_results for reason in item["reasons"]]
        risks = rule_gate.risks + [
            risk for item in criterion_results for risk in item["risks"]
        ]
        partial_ai_evidence = any(
            risk.get("type") == "missing_ai_evidence"
            for risk in risks
        )
        if missing_llm or partial_ai_evidence:
            action = RecommendedAction.REVIEW
            rating_status = "rating_partial"
        else:
            action = _policy_decision_merge(
                use_case,
                final_score,
                confidence,
                self.config.min_confidence_for_draft,
            )
            rating_status = "use_case_rated"
        if action == RecommendedAction.DRAFT and use_case.draft_policy.draft_type == "none":
            action = RecommendedAction.REVIEW
            reasons.append(
                {
                    "type": "draft_disabled",
                    "value": "draft_policy.none",
                }
            )

        return RatingResult(
            target_id=_target_id(target),
            pipeline_run_id=pipeline_run_id,
            rule_score=final_score,
            ai_score=round(sum(ai_scores) / len(ai_scores)) if ai_scores else None,
            raw_confidence=raw_confidence,
            confidence=confidence,
            recommended_action=action,
            rating_status=rating_status,
            rating_version=f"{self.rating_version}+usecase-v{use_case.version}",
            reasons=reasons,
            risks=risks,
            evidence=evidence_payload,
            input_snapshot=_input_snapshot(search_profile, evidence, use_case=use_case),
        )

    def _score_criterion(
        self,
        criterion: RatingCriterion,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
        *,
        context_text: str,
        ai_provider: AIRatingProvider | None,
    ) -> dict[str, object]:
        rule_score: int | None = None
        reasons: list[dict[str, object]] = []
        risks: list[dict[str, object]] = []
        if criterion.evaluation in {RatingEvaluation.RULES, RatingEvaluation.HYBRID}:
            rule_result = self.rule_rater.score_rule_set(
                criterion.rule_set or "",
                target,
                search_profile,
                evidence,
            )
            rule_score = rule_result.score
            reasons.extend(
                _criterion_payload(reason, criterion.key)
                for reason in rule_result.reasons
            )
            risks.extend(rule_result.risks)

        ai_score: int | None = None
        confidence: float | None = None
        missing_llm = False
        if criterion.evaluation in {RatingEvaluation.LLM, RatingEvaluation.HYBRID}:
            if ai_provider is None:
                missing_llm = criterion.evaluation == RatingEvaluation.LLM
                risks.append(
                    {
                        "type": "missing_ai_provider",
                        "value": criterion.key,
                    }
                )
            else:
                try:
                    response = ai_provider.rate(
                        AIRatingRequest(
                            target_domain=target.domain,
                            search_terms=_search_terms(search_profile),
                            context_text=context_text,
                            rule_score=rule_score or 0,
                            criterion_key=criterion.key,
                            criterion_label=criterion.label,
                            llm_instruction=criterion.llm_instruction,
                        )
                    )
                    ai_score = response.ai_score
                    confidence = response.confidence
                    reasons.extend(
                        _criterion_payload(reason, criterion.key)
                        for reason in response.reasons
                    )
                    risks.extend(
                        _criterion_payload(risk, criterion.key)
                        for risk in response.risks
                    )
                    if not _ai_reasons_have_evidence(response):
                        confidence = min(confidence, 0.4)
                        risks.append(
                            {
                                "type": "missing_ai_evidence",
                                "value": criterion.key,
                            }
                        )
                except Exception as exc:
                    missing_llm = criterion.evaluation == RatingEvaluation.LLM
                    risks.append(
                        {
                            "type": "ai_provider_error",
                            "criterion": criterion.key,
                            "value": str(exc),
                        }
                    )

        if criterion.evaluation == RatingEvaluation.RULES:
            score = rule_score or 0
        elif criterion.evaluation == RatingEvaluation.LLM:
            score = ai_score or 0
        else:
            score = max(rule_score or 0, ai_score or 0)

        return {
            "key": criterion.key,
            "evaluation": criterion.evaluation.value,
            "weight": criterion.weight,
            "score": max(0, min(100, score)),
            "ai_score": ai_score,
            "confidence": confidence,
            "missing_llm": missing_llm,
            "reasons": reasons,
            "risks": risks,
        }

    def _ai_provider_for_mode(self, llm_mode: str) -> AIRatingProvider | None:
        if llm_mode == "off":
            return None
        if isinstance(self.ai_provider, LLMAIRatingProvider):
            return replace(self.ai_provider, task=llm_mode)
        return self.ai_provider


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


def _policy_decision_merge(
    use_case: UseCaseConfig,
    score: int,
    confidence: float,
    min_confidence_for_draft: float,
) -> RecommendedAction:
    if (
        score >= use_case.rating_policy.min_score_for_draft
        and confidence >= min_confidence_for_draft
    ):
        return RecommendedAction.DRAFT
    if score >= use_case.rating_policy.min_score_for_review:
        return RecommendedAction.REVIEW
    return RecommendedAction.SKIP


def _ai_reasons_have_evidence(response: AIRatingResponse) -> bool:
    if not response.reasons:
        return False
    return all(reason.get("source_url") and reason.get("evidence") for reason in response.reasons)


def _criterion_payload(payload: dict[str, object], criterion_key: str) -> dict[str, object]:
    enriched = dict(payload)
    enriched.setdefault("criterion", criterion_key)
    return enriched


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
    *,
    use_case: UseCaseConfig | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "search_profile_id": search_profile.id,
        "evidence_ids": [item.id for item in evidence],
    }
    if use_case is not None:
        payload["use_case_id"] = use_case.id
        payload["use_case_version"] = use_case.version
    return payload


def _search_terms(search_profile: SearchProfile) -> tuple[str, ...]:
    terms = (
        search_profile.roles
        + search_profile.tech_keywords
        + search_profile.regions
        + search_profile.industry_keywords
    )
    extra_terms: list[str] = []
    for value in search_profile.attributes.values():
        if isinstance(value, str):
            extra_terms.append(value)
        elif isinstance(value, (list, tuple, set)):
            extra_terms.extend(str(item) for item in value)
    return terms + tuple(item.strip() for item in extra_terms if item.strip())


def _target_id(target: Target) -> int:
    if target.id is None:
        raise ValueError("target must be persisted before rating")
    return target.id
