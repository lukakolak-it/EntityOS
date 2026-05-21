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
    ) -> DraftValidationResult:
        errors: list[str] = []
        if not subject.strip():
            errors.append("subject is required")
        if not body.strip():
            errors.append("body is required")
        if len(body) > self.max_body_chars:
            errors.append("body exceeds max length")
        if not evidence_snippets:
            errors.append("at least one evidence snippet is required")

        lower_body = body.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower_body:
                errors.append(f"banned phrase: {phrase}")

        return DraftValidationResult(valid=not errors, errors=tuple(errors))


class DraftValidationError(ValueError):
    def __init__(self, errors: tuple[str, ...]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
