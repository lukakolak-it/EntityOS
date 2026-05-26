"""Template-based draft generation for the MVP."""

from __future__ import annotations

from target_radar.engines.draft.context import DraftContext


class TemplateDraftGenerator:
    def generate(self, context: DraftContext, *, draft_type: str) -> tuple[str, str]:
        if draft_type in _RESEARCH_DRAFT_TITLES:
            return _research_summary(context, draft_type=draft_type)
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


_RESEARCH_DRAFT_TITLES = {
    "research_summary": "Research Summary",
    "company_summary": "Company Summary",
    "project_summary": "Project Summary",
    "vendor_risk_note": "Vendor Risk Note",
}


def _research_summary(context: DraftContext, *, draft_type: str) -> tuple[str, str]:
    title = _RESEARCH_DRAFT_TITLES[draft_type]
    subject = f"{title}: {context.target_domain}"
    items = context.evidence_items[:4]
    findings = "\n".join(
        _finding_line(item.ref, item.evidence_type, item.evidence_category, item.text)
        for item in items
    )
    if not findings:
        findings = "- Keine belastbaren Belege gefunden."
    evidence_lines = "\n".join(
        f"- {item.ref}: [{_evidence_label(item.evidence_type, item.evidence_category)}] "
        f"{item.source_url}"
        for item in items
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
                f"{_summary_sentence(context, draft_type, len(items))} "
                "Die folgenden Punkte sind Arbeitsnotizen fuer die manuelle Pruefung."
            ),
            f"Key Findings\n{findings}",
            f"Evidence\n{evidence_lines}",
            f"Risks Or Uncertainties\n{risks}",
            f"Next Steps\n{_next_steps(draft_type)}",
        ]
    )
    return subject, body


def _summary_sentence(context: DraftContext, draft_type: str, evidence_count: int) -> str:
    if draft_type == "company_summary":
        return (
            f"{context.target_domain} wurde als Unternehmen anhand von {evidence_count} "
            "lokal gespeicherten Evidence-Objekten bewertet."
        )
    if draft_type == "project_summary":
        return (
            f"{context.target_domain} wurde als Projekt oder Repository anhand von "
            f"{evidence_count} lokal gespeicherten Evidence-Objekten bewertet."
        )
    if draft_type == "vendor_risk_note":
        return (
            f"{context.target_domain} wurde als moeglicher Anbieter anhand von "
            f"{evidence_count} lokal gespeicherten Evidence-Objekten auf Risiken "
            "und offene Pruefpunkte bewertet."
        )
    return (
        f"{context.target_domain} wurde anhand von {evidence_count} lokal gespeicherten "
        "Evidence-Objekten bewertet."
    )


def _next_steps(draft_type: str) -> str:
    if draft_type == "vendor_risk_note":
        return "\n".join(
            [
                "- Quellen manuell pruefen.",
                "- Offene Risiken vor einer Anbieterentscheidung klaeren.",
            ]
        )
    if draft_type == "project_summary":
        return "\n".join(
            [
                "- Repository- und Aktivitaetshinweise manuell pruefen.",
                "- Entscheidung in der Review Queue dokumentieren.",
            ]
        )
    return "- Quellen manuell pruefen und Entscheidung in der Review Queue treffen."


def _finding_line(ref: str, evidence_type: str, evidence_category: str, text: str) -> str:
    return f"- {ref}: [{_evidence_label(evidence_type, evidence_category)}] {_clip_text(text, 260)}"


def _evidence_label(evidence_type: str, evidence_category: str) -> str:
    if evidence_category and evidence_category != evidence_type:
        return f"{evidence_category}/{evidence_type}"
    return evidence_type


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
