"""Source quality classification for discovery results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import parse_qs, urlparse

from target_radar.domain import domain_from_url, normalize_domain
from target_radar.engines.lead.provider import SearchResult
from target_radar.use_cases import SourcePolicy


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
    SEARCH_RESULT = "search_result"
    UNKNOWN = "unknown"


class SourceImportAction(StrEnum):
    IMPORT = "import"
    REVIEW_SOURCE = "review_source"
    BLOCK = "block"


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
    "ranking",
    "rankings",
    "topliste",
    "toplisten",
    "branchenbuch",
    "stellenangebote",
    "jobboerse",
    "jobsuche",
    "vacancies",
    "results",
    "listing",
)


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
    import_threshold: int = 65
    preferred_source_types: tuple[SourceType, ...] = (
        SourceType.COMPANY_SITE,
        SourceType.OFFICIAL_SITE,
    )
    context_source_types: tuple[SourceType, ...] = (
        SourceType.REPOSITORY,
        SourceType.NEWS,
        SourceType.REGISTRY,
    )
    blocked_source_types: tuple[SourceType, ...] = (
        SourceType.JOB_BOARD,
        SourceType.SOCIAL,
        SourceType.MARKETPLACE,
        SourceType.SEARCH_RESULT,
    )
    preferred_domains: tuple[str, ...] = ()
    relevant_path_tokens: tuple[str, ...] = _RELEVANT_PATH_TOKENS
    listing_path_tokens: tuple[str, ...] = _LISTING_TOKENS
    _extra_blocked: frozenset[str] = field(init=False, repr=False)
    _preferred_domains: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_extra_blocked",
            frozenset(normalize_domain(domain) for domain in self.extra_blocked_domains),
        )
        object.__setattr__(
            self,
            "_preferred_domains",
            frozenset(normalize_domain(domain) for domain in self.preferred_domains),
        )

    @classmethod
    def from_source_policy(
        cls,
        source_policy: SourcePolicy,
        *,
        extra_blocked_domains: tuple[str, ...] = (),
        block_threshold: int | None = None,
    ) -> SourceQualityClassifier:
        blocked_domains = tuple(extra_blocked_domains) + tuple(source_policy.blocked_domains)
        return cls(
            extra_blocked_domains=blocked_domains,
            block_threshold=(
                source_policy.review_threshold
                if block_threshold is None
                else block_threshold
            ),
            import_threshold=source_policy.import_threshold,
            preferred_source_types=_source_types(source_policy.preferred_source_types),
            context_source_types=_source_types(source_policy.context_source_types),
            blocked_source_types=_source_types(source_policy.blocked_source_types),
            preferred_domains=source_policy.preferred_domains,
            relevant_path_tokens=source_policy.relevant_path_tokens or _RELEVANT_PATH_TOKENS,
            listing_path_tokens=source_policy.listing_path_tokens or _LISTING_TOKENS,
        )

    def classify(self, result: SearchResult) -> SourceQualityResult:
        domain = domain_from_url(result.url)
        parsed = urlparse(result.url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        query_params = parse_qs(parsed.query)
        title = (result.title or "").strip()
        snippet = (result.snippet or "").strip()
        text_haystack = " ".join([title, snippet]).lower()

        source_type = _classify_domain(domain, path)
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

        if domain in self._preferred_domains:
            score += 20
            signals.append({"type": "preferred_domain", "value": domain, "points": 20})
        elif source_type in self.preferred_source_types:
            score += 20
            signals.append({"type": "direct_domain", "value": domain, "points": 20})
        elif source_type in self.context_source_types:
            score -= 10
            risks.append({"type": "context_source", "value": source_type.value})
        elif source_type in self.blocked_source_types:
            score -= 40
            risks.append({"type": "blocked_source_type", "value": source_type.value})
        elif source_type == SourceType.DIRECTORY:
            score -= 20
            risks.append({"type": "secondary_source", "value": source_type.value})

        if (
            _has_relevant_path(path, self.relevant_path_tokens)
            and source_type not in self.blocked_source_types
        ):
            score += 15
            signals.append({"type": "relevant_path", "value": path or "/", "points": 15})

        if _looks_like_listing_page(
            path,
            query_params,
            text_haystack,
            self.listing_path_tokens,
        ):
            score -= 25
            risks.append({"type": "listing_or_search_page", "value": path or "/"})

        if _looks_like_login_or_tracking(path, query):
            score -= 20
            risks.append({"type": "login_or_tracking_page", "value": path or "/"})

        path_depth = _path_depth(path)
        if path_depth >= 4:
            score -= 10
            risks.append({"type": "deep_url", "value": path_depth})

        if _has_concrete_title(title):
            score += 5
            signals.append({"type": "concrete_title", "value": title[:120], "points": 5})
        elif title:
            score -= 10
            risks.append({"type": "generic_title", "value": title[:120]})

        provider_rank = _provider_rank(result)
        rank_points = _provider_rank_points(provider_rank)
        if rank_points:
            score += rank_points
            signals.append(
                {
                    "type": "provider_rank",
                    "value": provider_rank,
                    "points": rank_points,
                }
            )

        score = max(0, min(100, score))
        action = _recommended_action(
            source_type=source_type,
            score=score,
            block_threshold=self.block_threshold,
            import_threshold=self.import_threshold,
            context_source_types=self.context_source_types,
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
    "jooble.org": SourceType.JOB_BOARD,
    "kimeta.de": SourceType.JOB_BOARD,
    "jobmensa.de": SourceType.JOB_BOARD,
    "meinpraktikum.de": SourceType.JOB_BOARD,
    "get-in-it.de": SourceType.JOB_BOARD,
    "monster.de": SourceType.JOB_BOARD,
    "absolventa.de": SourceType.JOB_BOARD,
    "glassdoor.de": SourceType.JOB_BOARD,
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
    "kununu.com": SourceType.DIRECTORY,
    "northdata.de": SourceType.DIRECTORY,
    "firmenwissen.de": SourceType.DIRECTORY,
    "gelbeseiten.de": SourceType.DIRECTORY,
    "dasoertliche.de": SourceType.DIRECTORY,
    "regiomanager.de": SourceType.DIRECTORY,
    "unternehmensregister.de": SourceType.REGISTRY,
    "handelsregister.de": SourceType.REGISTRY,
    "bundesanzeiger.de": SourceType.REGISTRY,
    "tagesschau.de": SourceType.NEWS,
    "spiegel.de": SourceType.NEWS,
    "zeit.de": SourceType.NEWS,
    "faz.net": SourceType.NEWS,
    "sueddeutsche.de": SourceType.NEWS,
    "heise.de": SourceType.NEWS,
    "google.com": SourceType.SEARCH_RESULT,
    "bing.com": SourceType.SEARCH_RESULT,
    "duckduckgo.com": SourceType.SEARCH_RESULT,
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
_LOGIN_TOKENS = ("login", "signin", "signup", "register", "bewerben")
_DOMAIN_JOB_BOARD_TOKENS = frozenset({"jobs", "stellen", "karriere", "career"})
_MARKETPLACE_TOKENS = frozenset({"marketplace", "shop", "store"})
_LISTING_QUERY_KEYS = frozenset({"q", "query", "search", "s", "keyword"})
_NEWS_PATH_TOKENS = ("/news/", "/article/", "/artikel/", "/meldung/", "/story/")
_DIRECTORY_PATH_TOKENS = (
    "/ranking/",
    "/rankings/",
    "/topliste/",
    "/toplisten/",
    "/branchenbuch/",
)


def _classify_domain(domain: str, path: str = "") -> SourceType:
    if domain in _DOMAIN_SOURCE_TYPES:
        return _DOMAIN_SOURCE_TYPES[domain]
    for known_domain, source_type in _DOMAIN_SOURCE_TYPES.items():
        if domain.endswith(f".{known_domain}"):
            return source_type
    if _is_official_domain(domain):
        return SourceType.OFFICIAL_SITE
    if _is_news_path(path):
        return SourceType.NEWS
    if _is_directory_path(path):
        return SourceType.DIRECTORY
    domain_tokens = _domain_tokens(domain)
    if domain_tokens & _DOMAIN_JOB_BOARD_TOKENS:
        return SourceType.JOB_BOARD
    if domain_tokens & _MARKETPLACE_TOKENS:
        return SourceType.MARKETPLACE
    return SourceType.COMPANY_SITE


def _has_relevant_path(path: str, relevant_path_tokens: tuple[str, ...]) -> bool:
    return any(token in path for token in relevant_path_tokens)


def _looks_like_listing_page(
    path: str,
    query_params: dict[str, list[str]],
    text_haystack: str,
    listing_path_tokens: tuple[str, ...],
) -> bool:
    if _path_tokens(path) & set(listing_path_tokens):
        return True
    if _LISTING_QUERY_KEYS & {key.lower() for key in query_params}:
        return True
    generic_hits = len(_text_tokens(text_haystack) & set(_JOB_BOARD_TOKENS))
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


def _provider_rank_points(provider_rank: int | None) -> int:
    if provider_rank is None:
        return 0
    if provider_rank == 1:
        return 8
    if provider_rank <= 3:
        return 5
    if provider_rank <= 7:
        return 2
    return 0


def _path_depth(path: str) -> int:
    return len([segment for segment in path.split("/") if segment])


def _domain_tokens(domain: str) -> set[str]:
    return {token for token in re.split(r"[\.\-_]", domain.lower()) if token}


def _text_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _path_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _is_official_domain(domain: str) -> bool:
    return domain.endswith((".gov", ".bund.de", ".edu")) or ".ac." in domain


def _is_news_path(path: str) -> bool:
    if any(token in path for token in _NEWS_PATH_TOKENS):
        return True
    return re.search(r"/20\d{2}/\d{1,2}/\d{1,2}/", path) is not None


def _is_directory_path(path: str) -> bool:
    return any(token in path for token in _DIRECTORY_PATH_TOKENS)


def _source_types(values: tuple[str, ...]) -> tuple[SourceType, ...]:
    return tuple(SourceType(value) for value in values)


def _recommended_action(
    *,
    source_type: SourceType,
    score: int,
    block_threshold: int,
    import_threshold: int,
    context_source_types: tuple[SourceType, ...],
    blocked_source_types: tuple[SourceType, ...],
) -> SourceImportAction:
    if source_type in blocked_source_types:
        return SourceImportAction.BLOCK
    if source_type in context_source_types:
        return SourceImportAction.REVIEW_SOURCE
    if score < block_threshold:
        return SourceImportAction.BLOCK
    if score >= import_threshold:
        return SourceImportAction.IMPORT
    return SourceImportAction.REVIEW_SOURCE
