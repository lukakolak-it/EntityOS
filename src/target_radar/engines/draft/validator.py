"""Deterministic draft validation."""

from __future__ import annotations

from dataclasses import dataclass, field


BANNED_PHRASES = (
    "wie besprochen",
    "as discussed",
    "automatisch versendet",
)


@dataclass(frozen=True, slots=True)
class DraftValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


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
    ) -> DraftValidationResult:
        selected_max_body_chars = max_body_chars or self.max_body_chars
        errors: list[str] = []
        if not subject.strip():
            errors.append("subject is required")
        if not body.strip():
            errors.append("body is required")
        if len(body) > selected_max_body_chars:
            errors.append("body exceeds max length")
        if not evidence_snippets:
            errors.append("at least one evidence snippet is required")

        lower_body = body.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower_body:
                errors.append(f"banned phrase: {phrase}")
        for claim in forbidden_claims:
            if claim.lower() in lower_body:
                errors.append(f"forbidden claim: {claim}")
        for section in required_sections:
            label = _section_label(section).lower()
            if label not in lower_body:
                errors.append(f"missing required section: {section}")
        for source_url in required_source_urls:
            if source_url and source_url not in body:
                errors.append(f"missing evidence source: {source_url}")
        for ref in required_evidence_refs:
            if ref and f"{ref}:" not in body:
                errors.append(f"missing evidence reference: {ref}")

        return DraftValidationResult(valid=not errors, errors=tuple(errors))


class DraftValidationError(ValueError):
    def __init__(self, errors: tuple[str, ...]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _section_label(section: str) -> str:
    return section.replace("_", " ").title()
