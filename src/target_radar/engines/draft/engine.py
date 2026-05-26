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
from target_radar.engines.draft.context import (
    DraftContext,
    DraftContextBuilder,
    DraftEvidenceSnippet,
)
from target_radar.engines.draft.templates import TemplateDraftGenerator
from target_radar.engines.draft.validator import DraftValidationError, DraftValidator
from target_radar.use_cases import DraftPolicy


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
        draft_policy: DraftPolicy | None = None,
        language: str | None = None,
        regenerated_from_draft_id: int | None = None,
    ) -> Draft:
        if target.id is None:
            raise ValueError("target must be persisted before drafting")
        if rating.recommended_action != RecommendedAction.DRAFT:
            raise DraftSkippedError("rating recommended_action must be draft")

        selected_draft_type = draft_policy.draft_type if draft_policy is not None else draft_type
        selected_language = (
            language
            or (draft_policy.language if draft_policy is not None else None)
        )
        max_body_chars = draft_policy.max_length_chars if draft_policy is not None else None
        selected_max_body_chars = max_body_chars or self.validator.max_body_chars
        required_sections = draft_policy.required_sections if draft_policy is not None else ()
        forbidden_claims = draft_policy.forbidden_claims if draft_policy is not None else ()
        context = self.context_builder.build(
            profile=profile,
            target=target,
            rating=rating,
            evidence=evidence,
            language=selected_language,
            max_context_chars=_context_budget(selected_draft_type, max_body_chars),
            max_snippets=_snippet_limit(selected_draft_type),
        )
        subject, body = self.generator.generate(context, draft_type=selected_draft_type)
        body = _fit_body_to_limit(
            draft_type=selected_draft_type,
            subject=subject,
            body=body,
            context=context,
            max_body_chars=selected_max_body_chars,
        )
        validation = self.validator.validate(
            subject=subject,
            body=body,
            evidence_snippets=context.evidence_snippets,
            max_body_chars=selected_max_body_chars,
            required_sections=required_sections,
            forbidden_claims=forbidden_claims,
            required_source_urls=_required_source_urls(selected_draft_type, context),
            required_evidence_refs=_required_evidence_refs(selected_draft_type, context),
            required_claim_refs=_required_claim_refs(selected_draft_type, context),
            draft_type=selected_draft_type,
        )
        if not validation.valid:
            raise DraftValidationError(validation.errors, validation.issues)

        return Draft(
            target_id=target.id,
            score_id=rating.id,
            draft_type=selected_draft_type,
            draft_version=_draft_version(selected_draft_type),
            language=context.language,
            subject=subject,
            body=body,
            status=DraftStatus.NEEDS_REVIEW,
            used_context={
                "rating_version": context.rating_version,
                "evidence_count": len(context.evidence_snippets),
                "evidence_total_chars": context.evidence_total_chars,
                "evidence_truncated": context.evidence_truncated,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "ref": item.ref,
                        "source_url": item.source_url,
                        "evidence_type": item.evidence_type,
                        "evidence_category": item.evidence_category,
                        "context_type": item.context_type,
                        "priority": item.priority,
                    }
                    for item in context.evidence_items
                ],
                "claim_refs": _claim_refs(selected_draft_type, context),
                "draft_policy": draft_policy.to_dict() if draft_policy is not None else None,
            },
            regenerated_from_draft_id=regenerated_from_draft_id,
        )


def _draft_version(draft_type: str) -> str:
    if _is_research_draft(draft_type):
        return f"{draft_type.replace('_', '-')}-v1"
    return "application-email-v1"


def _context_budget(draft_type: str, max_body_chars: int | None) -> int:
    if _is_research_draft(draft_type):
        if max_body_chars is None:
            return 1800
        return max(600, min(1800, max_body_chars // 2))
    return 500


def _snippet_limit(draft_type: str) -> int:
    if _is_research_draft(draft_type):
        return 4
    return 1


def _required_source_urls(draft_type: str, context) -> tuple[str, ...]:
    if not _is_research_draft(draft_type):
        return ()
    return tuple(item.source_url for item in context.evidence_items if item.source_url)


def _required_evidence_refs(draft_type: str, context) -> tuple[str, ...]:
    if not _is_research_draft(draft_type):
        return ()
    return tuple(item.ref for item in context.evidence_items)


def _required_claim_refs(draft_type: str, context) -> tuple[str, ...]:
    if not _is_research_draft(draft_type):
        return ()
    return tuple(item.ref for item in context.evidence_items)


def _claim_refs(draft_type: str, context) -> list[dict[str, object]]:
    if not _is_research_draft(draft_type):
        return []
    return [
        {
            "evidence_id": item.evidence_id,
            "ref": item.ref,
            "source_url": item.source_url,
            "evidence_type": item.evidence_type,
            "evidence_category": item.evidence_category,
            "context_type": item.context_type,
            "priority": item.priority,
        }
        for item in context.evidence_items
    ]


def _fit_body_to_limit(
    *,
    draft_type: str,
    subject: str,
    body: str,
    context: DraftContext,
    max_body_chars: int,
) -> str:
    if len(body) <= max_body_chars:
        return body
    if _is_research_draft(draft_type):
        compact = _compact_research_summary_body(
            subject=subject,
            context=context,
            max_body_chars=max_body_chars,
        )
        if len(compact) <= max_body_chars:
            return compact
    return _clip_text(body, max_body_chars)


def _compact_research_summary_body(
    *,
    subject: str,
    context: DraftContext,
    max_body_chars: int,
) -> str:
    for finding_chars in (240, 180, 120, 80, 50, 25, 0):
        for risk_limit in (5, 3, 1, 0):
            body = _render_compact_research_summary(
                subject=subject,
                context=context,
                finding_chars=finding_chars,
                risk_limit=risk_limit,
            )
            if len(body) <= max_body_chars:
                return body
    return _render_compact_research_summary(
        subject=subject,
        context=context,
        finding_chars=0,
        risk_limit=0,
    )


def _render_compact_research_summary(
    *,
    subject: str,
    context: DraftContext,
    finding_chars: int,
    risk_limit: int,
) -> str:
    items = context.evidence_items
    findings = "\n".join(
        _compact_finding_line(item, finding_chars=finding_chars) for item in items
    )
    if not findings:
        findings = "- Keine belastbaren Belege gefunden."
    evidence_lines = "\n".join(
        f"- {item.ref}: {item.source_url}" for item in items if item.source_url
    )
    if not evidence_lines:
        evidence_lines = "- Keine Quellen gespeichert."
    risks = _compact_risks(context, risk_limit=risk_limit)
    summary = (
        f"{context.target_domain} wurde anhand von {len(items)} Evidence-Objekten "
        "als Arbeitsnotiz bewertet."
    )
    if context.evidence_truncated:
        summary += " Der Kontext wurde gekuerzt."

    return "\n\n".join(
        [
            f"Title\n{subject}",
            f"Summary\n{summary}",
            f"Key Findings\n{findings}",
            f"Evidence\n{evidence_lines}",
            f"Risks Or Uncertainties\n{risks}",
            "Next Steps\n- Quellen manuell pruefen und Entscheidung dokumentieren.",
        ]
    )


def _compact_finding_line(item: DraftEvidenceSnippet, *, finding_chars: int) -> str:
    evidence_label = _evidence_label(item)
    if finding_chars <= 0:
        return f"- {item.ref}: [{evidence_label}] siehe Evidence."
    return f"- {item.ref}: [{evidence_label}] {_clip_text(item.text, finding_chars)}"


def _compact_risks(context: DraftContext, *, risk_limit: int) -> str:
    if risk_limit <= 0 or not context.risks:
        return "- Keine expliziten Risiken im Rating."
    lines = []
    for risk in context.risks[:risk_limit]:
        risk_type = str(risk.get("type", "risk"))
        value = _clip_text(str(risk.get("value", "")), 80)
        lines.append(f"- {risk_type}: {value}")
    return "\n".join(lines)


def _clip_text(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 1:
        return "."
    return cleaned[: max_chars - 1].rstrip() + "."


def _is_research_draft(draft_type: str) -> bool:
    return draft_type in {
        "research_summary",
        "company_summary",
        "project_summary",
        "vendor_risk_note",
    }


def _evidence_label(item: DraftEvidenceSnippet) -> str:
    if item.evidence_category and item.evidence_category != item.evidence_type:
        return f"{item.evidence_category}/{item.evidence_type}"
    return item.evidence_type
