"""Template-based draft generation for the MVP."""

from __future__ import annotations

from target_radar.engines.draft.context import DraftContext


class TemplateDraftGenerator:
    def generate(self, context: DraftContext, *, draft_type: str) -> tuple[str, str]:
        if draft_type == "research_summary":
            return _research_summary(context)
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


def _research_summary(context: DraftContext) -> tuple[str, str]:
    subject = f"Research Summary: {context.target_domain}"
    items = context.evidence_items[:4]
    findings = "\n".join(
        _finding_line(item.ref, item.evidence_type, item.text) for item in items
    )
    if not findings:
        findings = "- Keine belastbaren Belege gefunden."
    evidence_lines = "\n".join(
        f"- {item.ref}: {item.source_url}" for item in items
    )
    if not evidence_lines:
        evidence_lines = "- Keine Quellen gespeichert."
    risks = "\n".join(_risk_line(risk) for risk in context.risks[:5])
    if not risks:
        risks = "- Keine expliziten Risiken im Rating."

    body = "\n\n".join(
        [
            f"Title\n{subject}",
            (
                "Summary\n"
                f"{context.target_domain} wurde anhand von {len(items)} lokal "
                "gespeicherten Evidence-Objekten bewertet. Die folgenden Punkte "
                "sind Arbeitsnotizen fuer die manuelle Pruefung."
            ),
            f"Key Findings\n{findings}",
            f"Evidence\n{evidence_lines}",
            f"Risks Or Uncertainties\n{risks}",
            "Next Steps\n- Quellen manuell pruefen und Entscheidung in der Review Queue treffen.",
        ]
    )
    return subject, body


def _finding_line(ref: str, evidence_type: str, text: str) -> str:
    return f"- {ref}: [{evidence_type}] {_clip_text(text, 260)}"


def _risk_line(risk: dict[str, object]) -> str:
    risk_type = str(risk.get("type", "risk"))
    value = _clip_text(str(risk.get("value") or risk.get("text") or ""), 100)
    if not value:
        return f"- {risk_type}"
    return f"- {risk_type}: {value}"


def _clip_text(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 1:
        return "."
    return cleaned[: max_chars - 1].rstrip() + "."
