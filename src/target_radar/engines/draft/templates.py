"""Template-based draft generation for the MVP."""

from __future__ import annotations

from target_radar.engines.draft.context import DraftContext


class TemplateDraftGenerator:
    def generate(self, context: DraftContext, *, draft_type: str) -> tuple[str, str]:
        if draft_type != "application_email":
            raise ValueError(f"unsupported draft_type: {draft_type}")

        first_snippet = context.evidence_snippets[0] if context.evidence_snippets else ""
        subject = f"Bewerbung / Kontaktaufnahme: {context.target_domain}"
        body = "\n\n".join(
            [
                "Guten Tag,",
                (
                    f"ich bin auf {context.target_domain} aufmerksam geworden "
                    "und sehe eine fachliche Naehe zu meinem Profil."
                ),
                f"Relevanter Kontext: {first_snippet}",
                (
                    "Ich wuerde mich ueber eine kurze Rueckmeldung freuen "
                    "und pruefe die Details gern manuell weiter."
                ),
                "Viele Gruesse",
                context.profile_name,
            ]
        )
        return subject, body
