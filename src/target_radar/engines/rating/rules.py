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
