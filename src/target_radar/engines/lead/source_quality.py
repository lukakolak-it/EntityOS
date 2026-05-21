"""Source quality classification for discovery results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

from target_radar.domain import domain_from_url, normalize_domain
from target_radar.engines.lead.provider import SearchResult


class SourceType(StrEnum):
    OFFICIAL_SITE = "official_site"
    COMPANY_SITE = "company_site"
    DIRECTORY = "directory"
    JOB_BOARD = "job_board"
    SOCIAL = "social"
    REPOSITORY = "repository"
    NEWS = "news"
    REGISTRY = "registry"
    MARKETPLACE = "marketplace"
    UNKNOWN = "unknown"


class SourceImportAction(StrEnum):
    IMPORT = "import"
    REVIEW_SOURCE = "review_source"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class SourceQualityResult:
    source_type: SourceType
    score: int
    recommended_action: SourceImportAction
    signals: tuple[dict[str, object], ...] = ()
    risks: tuple[dict[str, object], ...] = ()

    @property
    def blocked(self) -> bool:
        return self.recommended_action == SourceImportAction.BLOCK

    def to_metadata(self) -> dict[str, object]:
        return {
            "source_type": self.source_type.value,
            "source_quality_score": self.score,
            "recommended_import_action": self.recommended_action.value,
            "source_signals": list(self.signals),
            "source_risks": list(self.risks),
        }


@dataclass(frozen=True, slots=True)
class SourceQualityClassifier:
    """Score SERP results before target import.

    The classifier is intentionally heuristic and transparent. It should improve
    discovery ordering and filtering, while final target fit remains the
    RatingEngine's responsibility.
    """

    extra_blocked_domains: tuple[str, ...] = ()
    block_threshold: int = 35
    blocked_source_types: tuple[SourceType, ...] = (
        SourceType.JOB_BOARD,
        SourceType.SOCIAL,
        SourceType.MARKETPLACE,
    )
    _extra_blocked: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_extra_blocked",
            frozenset(normalize_domain(domain) for domain in self.extra_blocked_domains),
        )

    def classify(self, result: SearchResult) -> SourceQualityResult:
        domain = domain_from_url(result.url)
        parsed = urlparse(result.url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        title = (result.title or "").strip()
        snippet = (result.snippet or "").strip()
        haystack = " ".join([domain, path, title, snippet]).lower()

        source_type = _classify_domain(domain)
        score = 50
        signals: list[dict[str, object]] = []
        risks: list[dict[str, object]] = []

        if domain in self._extra_blocked:
            risks.append({"type": "configured_blocked_domain", "value": domain})
            return SourceQualityResult(
                source_type=source_type,
                score=0,
                recommended_action=SourceImportAction.BLOCK,
                risks=tuple(risks),
            )

        if source_type in {SourceType.COMPANY_SITE, SourceType.OFFICIAL_SITE}:
            score += 20
            signals.append({"type": "direct_domain", "value": domain, "points": 20})
        elif source_type == SourceType.DIRECTORY:
            score -= 20
            risks.append({"type": "secondary_source", "value": source_type.value})
        elif source_type in {SourceType.REPOSITORY, SourceType.NEWS, SourceType.REGISTRY}:
            score -= 10
            risks.append({"type": "context_source", "value": source_type.value})
        elif source_type in self.blocked_source_types:
            score -= 40
            risks.append({"type": "blocked_source_type", "value": source_type.value})

        if _has_relevant_path(path):
            score += 15
            signals.append({"type": "relevant_path", "value": path or "/", "points": 15})

        if _looks_like_listing_page(path, query, haystack):
            score -= 25
            risks.append({"type": "listing_or_search_page", "value": path or "/"})

        if _looks_like_login_or_tracking(path, query):
            score -= 20
            risks.append({"type": "login_or_tracking_page", "value": path or "/"})

        if _has_concrete_title(title):
            score += 5
            signals.append({"type": "concrete_title", "value": title[:120], "points": 5})
        elif title:
            score -= 10
            risks.append({"type": "generic_title", "value": title[:120]})

        provider_rank = _provider_rank(result)
        if provider_rank is not None and provider_rank <= 3:
            score += 5
            signals.append({"type": "provider_rank", "value": provider_rank, "points": 5})

        score = max(0, min(100, score))
        action = _recommended_action(
            source_type=source_type,
            score=score,
            block_threshold=self.block_threshold,
            blocked_source_types=self.blocked_source_types,
        )
        return SourceQualityResult(
            source_type=source_type,
            score=score,
            recommended_action=action,
            signals=tuple(signals),
            risks=tuple(risks),
        )


_DOMAIN_SOURCE_TYPES: dict[str, SourceType] = {
    "studentjob.de": SourceType.JOB_BOARD,
    "stepstone.de": SourceType.JOB_BOARD,
    "indeed.com": SourceType.JOB_BOARD,
    "indeed.de": SourceType.JOB_BOARD,
    "linkedin.com": SourceType.SOCIAL,
    "xing.com": SourceType.SOCIAL,
    "facebook.com": SourceType.SOCIAL,
    "instagram.com": SourceType.SOCIAL,
    "x.com": SourceType.SOCIAL,
    "twitter.com": SourceType.SOCIAL,
    "github.com": SourceType.REPOSITORY,
    "gitlab.com": SourceType.REPOSITORY,
    "bitbucket.org": SourceType.REPOSITORY,
    "crunchbase.com": SourceType.DIRECTORY,
    "northdata.de": SourceType.DIRECTORY,
    "firmenwissen.de": SourceType.DIRECTORY,
    "gelbeseiten.de": SourceType.DIRECTORY,
    "dasoertliche.de": SourceType.DIRECTORY,
    "unternehmensregister.de": SourceType.REGISTRY,
    "handelsregister.de": SourceType.REGISTRY,
    "bundesanzeiger.de": SourceType.REGISTRY,
}

_JOB_BOARD_TOKENS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stellen",
    "stellenangebote",
    "praktikum",
    "werkstudent",
)
_RELEVANT_PATH_TOKENS = (
    "career",
    "careers",
    "karriere",
    "jobs",
    "kontakt",
    "contact",
    "impressum",
    "about",
    "ueber",
    "uber",
    "team",
    "services",
)
_LISTING_TOKENS = (
    "search",
    "suche",
    "stellenangebote",
    "jobboerse",
    "jobsuche",
    "vacancies",
    "results",
    "listing",
)
_LOGIN_TOKENS = ("login", "signin", "signup", "register", "bewerben")


def _classify_domain(domain: str) -> SourceType:
    if domain in _DOMAIN_SOURCE_TYPES:
        return _DOMAIN_SOURCE_TYPES[domain]
    for known_domain, source_type in _DOMAIN_SOURCE_TYPES.items():
        if domain.endswith(f".{known_domain}"):
            return source_type
    if any(token in domain for token in ("jobs", "stellen", "career")):
        return SourceType.JOB_BOARD
    if any(token in domain for token in ("marketplace", "shop", "store")):
        return SourceType.MARKETPLACE
    return SourceType.COMPANY_SITE


def _has_relevant_path(path: str) -> bool:
    return any(token in path for token in _RELEVANT_PATH_TOKENS)


def _looks_like_listing_page(path: str, query: str, haystack: str) -> bool:
    if any(token in path for token in _LISTING_TOKENS):
        return True
    if query and any(token in query for token in ("q=", "query=", "search=")):
        return True
    generic_hits = sum(1 for token in _JOB_BOARD_TOKENS if token in haystack)
    return generic_hits >= 4


def _looks_like_login_or_tracking(path: str, query: str) -> bool:
    if any(token in path for token in _LOGIN_TOKENS):
        return True
    return any(token in query for token in ("utm_", "fbclid=", "gclid="))


def _has_concrete_title(title: str) -> bool:
    clean = title.strip()
    if not clean:
        return False
    lower = clean.lower()
    if any(token in lower for token in ("jobsuche", "stellenangebote", "jobboerse")):
        return False
    return any(char.isalpha() for char in clean) and len(clean) >= 8


def _provider_rank(result: SearchResult) -> int | None:
    rank = result.metadata.get("provider_rank")
    if rank is None:
        return None
    try:
        return int(rank)
    except (TypeError, ValueError):
        return None


def _recommended_action(
    *,
    source_type: SourceType,
    score: int,
    block_threshold: int,
    blocked_source_types: tuple[SourceType, ...],
) -> SourceImportAction:
    if source_type in blocked_source_types:
        return SourceImportAction.BLOCK
    if score < block_threshold:
        return SourceImportAction.BLOCK
    if score >= 65:
        return SourceImportAction.IMPORT
    return SourceImportAction.REVIEW_SOURCE
