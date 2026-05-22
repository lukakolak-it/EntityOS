"""Deterministic rule rating."""

from __future__ import annotations

from dataclasses import dataclass, field

from target_radar.domain import Evidence, SearchProfile, Target


@dataclass(frozen=True, slots=True)
class RuleRatingResult:
    score: int
    reasons: list[dict[str, object]] = field(default_factory=list)
    risks: list[dict[str, object]] = field(default_factory=list)
    hard_stop: bool = False


@dataclass(frozen=True, slots=True)
class RuleCriterionResult:
    score: int
    reasons: list[dict[str, object]] = field(default_factory=list)
    risks: list[dict[str, object]] = field(default_factory=list)


class RuleRater:
    """Cheap gatekeeper before optional AI rating."""

    def rate(
        self,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
    ) -> RuleRatingResult:
        context = " ".join(item.text for item in evidence).lower()
        score = 0
        reasons: list[dict[str, object]] = []
        risks: list[dict[str, object]] = []

        score += _score_terms(search_profile.roles, context, 25, reasons, "role")
        score += _score_terms(
            search_profile.tech_keywords,
            context,
            20,
            reasons,
            "tech",
        )
        score += _score_terms(search_profile.regions, context, 15, reasons, "region")
        score += _score_terms(
            search_profile.industry_keywords,
            context,
            10,
            reasons,
            "industry",
        )

        if "@" in context or "kontakt" in context or "contact" in context:
            score += 10
            reasons.append({"type": "contact_signal", "value": "contact available"})

        hard_stop = False
        for term in search_profile.exclude_keywords:
            if term.lower() in context or term.lower() in target.domain:
                hard_stop = True
                score -= 50
                risks.append({"type": "exclude_keyword", "value": term})

        score = max(0, min(100, score))
        if not evidence:
            risks.append({"type": "missing_context", "value": "no evidence"})

        return RuleRatingResult(
            score=score,
            reasons=reasons,
            risks=risks,
            hard_stop=hard_stop,
        )

    def score_rule_set(
        self,
        rule_set: str,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
    ) -> RuleCriterionResult:
        context = " ".join(item.text for item in evidence).lower()
        if rule_set == "role_keyword_match":
            return _score_match(search_profile.roles, context, "role_fit")
        if rule_set == "tech_keyword_match":
            return _score_match(search_profile.tech_keywords, context, "tech_fit")
        if rule_set == "region_keyword_match":
            return _score_match(search_profile.regions, context, "region_fit")
        if rule_set == "contactability":
            return _score_contactability(context)
        if rule_set == "evidence_quality":
            return _score_evidence_quality(evidence)
        if rule_set == "source_quality":
            return _score_source_quality(target)
        raise ValueError(f"unsupported rule_set: {rule_set}")


def _score_terms(
    terms: tuple[str, ...],
    context: str,
    points: int,
    reasons: list[dict[str, object]],
    reason_type: str,
) -> int:
    for term in terms:
        if term.lower() in context:
            reasons.append({"type": reason_type, "value": term, "points": points})
            return points
    return 0


def _score_match(
    terms: tuple[str, ...],
    context: str,
    reason_type: str,
) -> RuleCriterionResult:
    if not terms:
        return RuleCriterionResult(
            score=0,
            risks=[{"type": "missing_terms", "value": reason_type}],
        )
    for term in terms:
        if term.lower() in context:
            return RuleCriterionResult(
                score=100,
                reasons=[{"type": reason_type, "value": term, "points": 100}],
            )
    return RuleCriterionResult(
        score=0,
        risks=[{"type": "missing_match", "value": reason_type}],
    )


def _score_contactability(context: str) -> RuleCriterionResult:
    if "@" in context or "kontakt" in context or "contact" in context:
        return RuleCriterionResult(
            score=100,
            reasons=[{"type": "contactability", "value": "contact available"}],
        )
    return RuleCriterionResult(
        score=20,
        risks=[{"type": "missing_contact_signal", "value": "no contact evidence"}],
    )


def _score_evidence_quality(evidence: list[Evidence]) -> RuleCriterionResult:
    if not evidence:
        return RuleCriterionResult(
            score=0,
            risks=[{"type": "missing_context", "value": "no evidence"}],
        )
    source_count = len({item.source_url for item in evidence if item.source_url})
    text_chars = sum(len(item.text.strip()) for item in evidence)
    score = 40
    if source_count >= 1:
        score += 25
    if source_count >= 2:
        score += 15
    if text_chars >= 500:
        score += 20
    return RuleCriterionResult(
        score=min(100, score),
        reasons=[
            {
                "type": "evidence_quality",
                "value": {"source_count": source_count, "text_chars": text_chars},
                "points": min(100, score),
            }
        ],
    )


def _score_source_quality(target: Target) -> RuleCriterionResult:
    source_quality = target.metadata.get("source_quality")
    if not isinstance(source_quality, dict):
        lead_metadata = target.metadata.get("lead_metadata")
        if isinstance(lead_metadata, dict):
            source_quality = lead_metadata.get("source_quality")
    if isinstance(source_quality, dict):
        score = int(source_quality.get("source_quality_score") or 0)
        return RuleCriterionResult(
            score=max(0, min(100, score)),
            reasons=[{"type": "source_quality", "value": source_quality}],
        )
    return RuleCriterionResult(
        score=50,
        risks=[{"type": "missing_source_quality", "value": target.domain}],
    )
