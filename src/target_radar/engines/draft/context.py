"""Draft context building."""

from __future__ import annotations

import re
from dataclasses import dataclass

from target_radar.domain import Evidence, Profile, RatingResult, RecommendedAction, Target


@dataclass(frozen=True, slots=True)
class DraftEvidenceSnippet:
    ref: str
    text: str
    source_url: str
    evidence_id: int | None
    evidence_type: str
    evidence_category: str
    context_type: str
    priority: int


@dataclass(frozen=True, slots=True)
class DraftContext:
    profile_name: str
    target_domain: str
    language: str
    recommended_action: RecommendedAction
    evidence_snippets: tuple[str, ...]
    evidence_items: tuple[DraftEvidenceSnippet, ...]
    risks: tuple[dict[str, object], ...]
    rating_version: str
    evidence_total_chars: int
    evidence_truncated: bool


class DraftContextBuilder:
    DEFAULT_CONTEXT_BUDGET_CHARS = 1800
    DEFAULT_MAX_SNIPPETS = 4

    def build(
        self,
        *,
        profile: Profile,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        language: str | None = None,
        max_snippet_chars: int = 500,
        max_context_chars: int | None = None,
        max_snippets: int | None = None,
    ) -> DraftContext:
        budget = max_context_chars or self.DEFAULT_CONTEXT_BUDGET_CHARS
        snippet_limit = max_snippets or self.DEFAULT_MAX_SNIPPETS
        ranked = _dedupe_ranked_evidence(sorted(
            (item for item in evidence if item.text.strip()),
            key=_evidence_sort_key,
        ))
        items: list[DraftEvidenceSnippet] = []
        used_chars = 0
        truncated = False
        for item in ranked:
            if len(items) >= snippet_limit or used_chars >= budget:
                truncated = True
                break
            remaining = budget - used_chars
            limit = min(max_snippet_chars, remaining)
            text = _summary_snippet(item, limit)
            if not text:
                continue
            items.append(
                DraftEvidenceSnippet(
                    ref=f"E{len(items) + 1}",
                    text=text,
                    source_url=item.source_url,
                    evidence_id=item.id,
                    evidence_type=_evidence_type(item),
                    evidence_category=_evidence_category(item),
                    context_type=item.context_type,
                    priority=item.priority,
                )
            )
            used_chars += len(text)
            if len(item.text.strip()) > len(text):
                truncated = True
        return DraftContext(
            profile_name=profile.name,
            target_domain=target.domain,
            language=language or profile.draft_language,
            recommended_action=rating.recommended_action,
            evidence_snippets=tuple(item.text for item in items),
            evidence_items=tuple(items),
            risks=tuple(rating.risks),
            rating_version=rating.rating_version,
            evidence_total_chars=used_chars,
            evidence_truncated=truncated,
        )


def _evidence_sort_key(evidence: Evidence) -> tuple[int, int, str]:
    return (
        -max(_type_priority(_evidence_type(evidence)), _type_priority(_evidence_category(evidence))),
        -evidence.priority,
        evidence.source_url,
    )


def _dedupe_ranked_evidence(ranked: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Evidence] = []
    for item in ranked:
        key = (item.source_url.rstrip("/").lower(), _evidence_type(item))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _type_priority(evidence_type: str) -> int:
    priorities = {
        "identity": 125,
        "official_claim": 75,
        "reputation": 110,
        "third_party_claim": 100,
        "contact": 95,
        "activity": 85,
        "context_registry": 120,
        "context_news": 105,
        "context_directory": 100,
        "target_contact": 90,
        "target_about": 80,
        "target_homepage": 70,
        "target_career": 60,
        "target_page": 50,
        "context_repository": 45,
        "context_source": 40,
    }
    return priorities.get(evidence_type, 10)


def _evidence_category(evidence: Evidence) -> str:
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    explicit_category = metadata.get("evidence_category")
    if explicit_category:
        return str(explicit_category)
    evidence_type = _evidence_type(evidence)
    return {
        "target_contact": "contact",
        "target_career": "activity",
        "target_about": "official_claim",
        "target_homepage": "official_claim",
        "target_page": "official_claim",
        "context_registry": "identity",
        "context_directory": "reputation",
        "context_news": "activity",
        "context_repository": "activity",
        "context_source": "third_party_claim",
    }.get(evidence_type, "official_claim")


def _evidence_type(evidence: Evidence) -> str:
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    explicit_type = metadata.get("evidence_type")
    if explicit_type:
        return str(explicit_type)
    return {
        "homepage": "target_homepage",
        "career": "target_career",
        "contact": "target_contact",
        "about": "target_about",
        "page": "target_page",
        "context_source": "context_source",
    }.get(evidence.context_type, "target_page")


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\s+[|]\s+")
_BOILERPLATE_RE = re.compile(
    r"\b("
    r"website-zustimmungen bearbeiten|"
    r"zum hauptinhalt wechseln|"
    r"zum inhalt springen|"
    r"hauptmen\S*|"
    r"men\S*\s+schlie\S*en|"
    r"untermen\S*\s+des\s+men\S*eintrags\s+%s\s+umschalten|"
    r"cookie-einstellungen|"
    r"powered by|"
    r"share by"
    r")\b",
    re.IGNORECASE,
)
_NAVIGATION_TOKENS = frozenset(
    {
        "agb",
        "blog",
        "datenschutz",
        "faq",
        "home",
        "impressum",
        "kontakt",
        "links",
        "menu",
        "menue",
        "neues",
        "fragen",
        "antworten",
        "startseite",
        "was",
        "wer",
    }
)


def _summary_snippet(evidence: Evidence, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    pieces = _metadata_pieces(evidence) + _text_pieces(evidence.text)
    selected: list[str] = []
    used = 0
    for piece in _dedupe_pieces(pieces):
        if not piece:
            continue
        remaining = max_chars - used - (1 if selected else 0)
        if remaining <= 0:
            break
        clipped = _clip(piece, remaining)
        if not clipped:
            continue
        selected.append(clipped)
        used += len(clipped) + (1 if selected[:-1] else 0)
        if used >= max_chars or sum(len(item) for item in selected) >= 180:
            break
    if selected:
        return " ".join(selected)
    return _clip(_clean_text(evidence.text), max_chars)


def _metadata_pieces(evidence: Evidence) -> list[str]:
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    pieces = [
        _clean_piece(str(metadata.get("title") or "")),
        _clean_piece(str(metadata.get("description") or "")),
    ]
    return [piece for piece in pieces if piece]


def _text_pieces(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    candidates = [
        _clean_piece(candidate)
        for candidate in _SENTENCE_SPLIT_RE.split(cleaned)
    ]
    scored = [
        (_piece_score(candidate), index, candidate)
        for index, candidate in enumerate(candidates)
        if candidate and not _looks_like_navigation(candidate)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _score, _index, candidate in scored[:3]]


def _clean_text(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    cleaned = _BOILERPLATE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\bSchlie\S*en\b", " ", cleaned)
    return _clean_piece(cleaned)


def _clean_piece(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -|:;")


def _dedupe_pieces(pieces: list[str]) -> list[str]:
    deduped: list[str] = []
    normalized: list[str] = []
    for piece in pieces:
        key = piece.casefold()
        if not key:
            continue
        if any(key in existing or existing in key for existing in normalized):
            continue
        normalized.append(key)
        deduped.append(piece)
    return deduped


def _piece_score(piece: str) -> int:
    lower = piece.casefold()
    score = 0
    for token in (
        "beratung",
        "dienstleister",
        "essen",
        "gmbh",
        "impressum",
        "kontakt",
        "leistungen",
        "photovoltaik",
        "referenzen",
        "solar",
        "unternehmen",
    ):
        if token in lower:
            score += 10
    word_count = len(piece.split())
    if 8 <= word_count <= 45:
        score += 8
    if word_count > 70:
        score -= 15
    return score


def _looks_like_navigation(piece: str) -> bool:
    words = {_nav_word_key(word.strip(".,:;!?()[]")) for word in piece.split()}
    nav_hits = len(words & _NAVIGATION_TOKENS)
    return nav_hits >= 4 and len(words) >= 12


def _nav_word_key(value: str) -> str:
    return (
        value.casefold()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _clip(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 1:
        return "."
    return cleaned[: max_chars - 1].rstrip() + "."
