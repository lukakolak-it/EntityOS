"""Deterministic draft validation."""

from __future__ import annotations

from dataclasses import dataclass, field


BANNED_PHRASES = (
    "wie besprochen",
    "as discussed",
    "automatisch versendet",
)
DRAFT_TYPE_BANNED_PHRASES = {
    "research_summary": (
        "guten tag,",
        "viele gruesse",
        "ich wuerde mich ueber eine kurze rueckmeldung freuen",
        "bewerbung / kontaktaufnahme",
    ),
}


@dataclass(frozen=True, slots=True)
class DraftValidationIssue:
    code: str
    message: str
    field: str | None = None
    value: str | None = None


@dataclass(frozen=True, slots=True)
class DraftValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[DraftValidationIssue, ...] = field(default_factory=tuple)


class DraftValidator:
    def __init__(self, *, max_body_chars: int = 4000) -> None:
        self.max_body_chars = max_body_chars

    def validate(
        self,
        *,
        subject: str,
        body: str,
        evidence_snippets: tuple[str, ...],
        max_body_chars: int | None = None,
        required_sections: tuple[str, ...] = (),
        forbidden_claims: tuple[str, ...] = (),
        required_source_urls: tuple[str, ...] = (),
        required_evidence_refs: tuple[str, ...] = (),
        draft_type: str | None = None,
    ) -> DraftValidationResult:
        selected_max_body_chars = max_body_chars or self.max_body_chars
        issues: list[DraftValidationIssue] = []
        if not subject.strip():
            _add_issue(issues, "missing_subject", "subject is required", field="subject")
        if not body.strip():
            _add_issue(issues, "missing_body", "body is required", field="body")
        if len(body) > selected_max_body_chars:
            _add_issue(
                issues,
                "too_long",
                "body exceeds max length",
                field="body",
                value=str(len(body)),
            )
        if not evidence_snippets:
            _add_issue(
                issues,
                "missing_evidence",
                "at least one evidence snippet is required",
                field="evidence",
            )

        lower_body = _normalize_for_matching(body)
        for phrase in BANNED_PHRASES:
            if _normalize_for_matching(phrase) in lower_body:
                _add_issue(
                    issues,
                    "banned_phrase",
                    f"banned phrase: {phrase}",
                    field="body",
                    value=phrase,
                )
        for phrase in DRAFT_TYPE_BANNED_PHRASES.get(draft_type or "", ()):
            if _normalize_for_matching(phrase) in lower_body:
                _add_issue(
                    issues,
                    "draft_type_banned_phrase",
                    f"banned phrase for {draft_type}: {phrase}",
                    field="body",
                    value=phrase,
                )
        for claim in forbidden_claims:
            if _normalize_for_matching(claim) in lower_body:
                _add_issue(
                    issues,
                    "forbidden_claim",
                    f"forbidden claim: {claim}",
                    field="body",
                    value=claim,
                )
        for section in required_sections:
            label = _section_label(section).lower()
            if label not in lower_body:
                _add_issue(
                    issues,
                    "missing_section",
                    f"missing required section: {section}",
                    field="body",
                    value=section,
                )
        for source_url in required_source_urls:
            if source_url and source_url not in body:
                _add_issue(
                    issues,
                    "ungrounded_claim",
                    f"missing evidence source: {source_url}",
                    field="body",
                    value=source_url,
                )
        for ref in required_evidence_refs:
            if ref and f"{ref}:" not in body:
                _add_issue(
                    issues,
                    "ungrounded_claim",
                    f"missing evidence reference: {ref}",
                    field="body",
                    value=ref,
                )

        errors = tuple(issue.message for issue in issues)
        return DraftValidationResult(
            valid=not issues,
            errors=errors,
            issues=tuple(issues),
        )


class DraftValidationError(ValueError):
    def __init__(
        self,
        errors: tuple[str, ...],
        issues: tuple[DraftValidationIssue, ...] = (),
    ) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
        self.issues = issues
        self.codes = tuple(issue.code for issue in issues)


def _section_label(section: str) -> str:
    return section.replace("_", " ").title()


def _normalize_for_matching(value: str) -> str:
    return (
        value.lower()
        .replace("\u00e4", "ae")
        .replace("\u00f6", "oe")
        .replace("\u00fc", "ue")
        .replace("\u00df", "ss")
    )


def _add_issue(
    issues: list[DraftValidationIssue],
    code: str,
    message: str,
    *,
    field: str | None = None,
    value: str | None = None,
) -> None:
    issues.append(
        DraftValidationIssue(
            code=code,
            message=message,
            field=field,
            value=value,
        )
    )
