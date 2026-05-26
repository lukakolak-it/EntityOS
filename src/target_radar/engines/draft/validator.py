"""Deterministic draft validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


BANNED_PHRASES = (
    "wie besprochen",
    "as discussed",
    "automatisch versendet",
)
_RESEARCH_DRAFT_BANNED_PHRASES = (
    "guten tag,",
    "viele gruesse",
    "ich wuerde mich ueber eine kurze rueckmeldung freuen",
    "bewerbung / kontaktaufnahme",
)
DRAFT_TYPE_BANNED_PHRASES = {
    "research_summary": _RESEARCH_DRAFT_BANNED_PHRASES,
    "company_summary": _RESEARCH_DRAFT_BANNED_PHRASES,
    "project_summary": _RESEARCH_DRAFT_BANNED_PHRASES,
    "vendor_risk_note": _RESEARCH_DRAFT_BANNED_PHRASES,
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
        required_claim_refs: tuple[str, ...] = (),
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
        if required_claim_refs:
            _validate_claim_refs(
                issues,
                body=body,
                required_refs=required_claim_refs,
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


_CLAIM_REF_RE = re.compile(r"^\s*-\s*(E\d+)\s*:")
_RESEARCH_SUMMARY_SECTIONS = {
    "title",
    "summary",
    "key findings",
    "evidence",
    "risks or uncertainties",
    "next steps",
}


def _validate_claim_refs(
    issues: list[DraftValidationIssue],
    *,
    body: str,
    required_refs: tuple[str, ...],
) -> None:
    allowed_refs = {ref for ref in required_refs if ref}
    finding_refs: set[str] = set()
    for line in _section_lines(body, "key findings"):
        stripped = line.strip()
        if not stripped:
            continue
        match = _CLAIM_REF_RE.match(stripped)
        if match is None:
            _add_issue(
                issues,
                "ungrounded_claim",
                f"finding lacks evidence reference: {_clip_issue_value(stripped)}",
                field="body",
                value=stripped,
            )
            continue
        ref = match.group(1)
        if ref not in allowed_refs:
            _add_issue(
                issues,
                "ungrounded_claim",
                f"finding references unknown evidence: {ref}",
                field="body",
                value=ref,
            )
            continue
        finding_refs.add(ref)

    for ref in sorted(allowed_refs - finding_refs):
        _add_issue(
            issues,
            "ungrounded_claim",
            f"missing finding for evidence reference: {ref}",
            field="body",
            value=ref,
        )


def _section_lines(body: str, section_name: str) -> tuple[str, ...]:
    selected: list[str] = []
    collecting = False
    wanted = _normalize_section_name(section_name)
    for line in body.splitlines():
        normalized = _normalize_section_name(line)
        if normalized in _RESEARCH_SUMMARY_SECTIONS:
            if normalized == wanted:
                collecting = True
                continue
            if collecting:
                break
        elif collecting:
            selected.append(line)
    return tuple(selected)


def _normalize_section_name(value: str) -> str:
    return _normalize_for_matching(value).strip()


def _clip_issue_value(value: str, max_chars: int = 120) -> str:
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "."


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
