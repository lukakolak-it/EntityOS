"""Core domain objects for Target Radar.

The models in this module intentionally stay persistence-agnostic. Engines,
storage adapters and API code can share them without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def normalize_domain(value: str) -> str:
    """Normalize a domain-like string for dedupe and persistence."""

    candidate = value.strip().lower()
    if not candidate:
        raise ValueError("domain must not be empty")

    parsed = urlparse(candidate)
    if parsed.netloc:
        candidate = parsed.netloc
    else:
        candidate = candidate.split("/", 1)[0]

    if candidate.startswith("www."):
        candidate = candidate[4:]

    if not candidate or "." not in candidate:
        raise ValueError(f"invalid domain: {value!r}")

    return candidate


def domain_from_url(url: str) -> str:
    """Extract and normalize a domain from a URL."""

    candidate = url.strip()
    if not candidate:
        raise ValueError("url must not be empty")

    parsed = urlparse(candidate)
    if not parsed.netloc:
        parsed = urlparse(f"https://{candidate}")

    return normalize_domain(parsed.netloc)


def ensure_non_empty(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def ensure_score(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return value


def ensure_confidence(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return value


class PipelineRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelinePhase(StrEnum):
    LEAD = "lead"
    IMPORT = "import"
    FETCH = "fetch"
    EXTRACT = "extract"
    RATING = "rating"
    DRAFT = "draft"
    REVIEW = "review"
    REPROCESS = "reprocess"


class TargetStatus(StrEnum):
    CANDIDATE = "candidate"
    BLOCKED_SOURCE = "blocked_source"
    IMPORTED = "imported"
    EXISTING = "existing"
    FETCH_PENDING = "fetch_pending"
    FETCH_PARTIAL = "fetch_partial"
    FETCH_FAILED = "fetch_failed"
    FETCHED = "fetched"
    RATING_PENDING = "rating_pending"
    RULE_PASSED = "rule_passed"
    RULE_SKIPPED = "rule_skipped"
    AI_PENDING = "ai_pending"
    AI_PASSED = "ai_passed"
    RATING_PARTIAL = "rating_partial"
    RATING_FAILED = "rating_failed"
    DRAFT_PENDING = "draft_pending"
    DRAFT_FAILED = "draft_failed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    APPROVED = "approved"
    BLACKLISTED = "blacklisted"


class ImportStatus(StrEnum):
    IMPORTED = "imported"
    EXISTING = "existing"
    DUPLICATE_INPUT = "duplicate_input"
    BLOCKED_SOURCE = "blocked_source"
    BLACKLISTED = "blacklisted"
    INVALID = "invalid"


class LeadResultStatus(StrEnum):
    CANDIDATE = "candidate"
    BLOCKED_SOURCE = "blocked_source"
    DUPLICATE_DOMAIN = "duplicate_domain"
    IMPORTED = "imported"
    EXISTING = "existing"
    BLACKLISTED = "blacklisted"
    INVALID = "invalid"


class RecommendedAction(StrEnum):
    SKIP = "skip"
    REVIEW = "review"
    DRAFT = "draft"


class DraftStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRAFT_FAILED = "draft_failed"


@dataclass(slots=True)
class Profile:
    name: str
    preset: str = "application"
    draft_language: str = "de"
    attributes: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.name = ensure_non_empty(self.name, "name")
        self.preset = ensure_non_empty(self.preset, "preset")
        self.draft_language = ensure_non_empty(self.draft_language, "draft_language")


@dataclass(slots=True)
class SearchProfile:
    profile_id: int
    name: str
    roles: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    tech_keywords: tuple[str, ...] = ()
    industry_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    manual_query: str | None = None
    draft_language: str | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.profile_id <= 0:
            raise ValueError("profile_id must be positive")
        self.name = ensure_non_empty(self.name, "name")
        self.roles = tuple(item.strip() for item in self.roles if item.strip())
        self.regions = tuple(item.strip() for item in self.regions if item.strip())
        self.tech_keywords = tuple(item.strip() for item in self.tech_keywords if item.strip())
        self.industry_keywords = tuple(
            item.strip() for item in self.industry_keywords if item.strip()
        )
        self.exclude_keywords = tuple(
            item.strip() for item in self.exclude_keywords if item.strip()
        )
        if self.manual_query is not None:
            self.manual_query = self.manual_query.strip() or None
        if self.draft_language is not None:
            self.draft_language = self.draft_language.strip() or None


@dataclass(slots=True)
class TargetCandidate:
    url: str
    source: str
    title: str | None = None
    snippet: str | None = None
    domain: str | None = None
    status: LeadResultStatus = LeadResultStatus.CANDIDATE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.url = ensure_non_empty(self.url, "url")
        self.source = ensure_non_empty(self.source, "source")
        self.domain = normalize_domain(self.domain) if self.domain else domain_from_url(self.url)


@dataclass(slots=True)
class Target:
    domain: str
    base_url: str
    source: str = "manual"
    status: TargetStatus = TargetStatus.CANDIDATE
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.domain = normalize_domain(self.domain)
        self.base_url = ensure_non_empty(self.base_url, "base_url")
        self.source = ensure_non_empty(self.source, "source")


@dataclass(slots=True)
class PipelineRun:
    search_profile_id: int
    mode: str = "focused"
    status: PipelineRunStatus = PipelineRunStatus.PENDING
    phases: tuple[PipelinePhase, ...] = (
        PipelinePhase.LEAD,
        PipelinePhase.FETCH,
        PipelinePhase.RATING,
        PipelinePhase.DRAFT,
    )
    request_budget: int | None = None
    results_per_query: int | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.search_profile_id <= 0:
            raise ValueError("search_profile_id must be positive")
        self.mode = ensure_non_empty(self.mode, "mode")
        if self.request_budget is not None and self.request_budget < 0:
            raise ValueError("request_budget must not be negative")
        if self.results_per_query is not None and self.results_per_query < 0:
            raise ValueError("results_per_query must not be negative")


@dataclass(slots=True)
class StatusLog:
    target_id: int
    to_status: TargetStatus
    phase: PipelinePhase
    pipeline_run_id: int | None = None
    from_status: TargetStatus | None = None
    reason: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.target_id <= 0:
            raise ValueError("target_id must be positive")
        if self.pipeline_run_id is not None and self.pipeline_run_id <= 0:
            raise ValueError("pipeline_run_id must be positive when set")


@dataclass(slots=True)
class Evidence:
    target_id: int
    source_url: str
    text: str
    context_type: str = "page"
    priority: int = 0
    page_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.target_id <= 0:
            raise ValueError("target_id must be positive")
        self.source_url = ensure_non_empty(self.source_url, "source_url")
        self.text = ensure_non_empty(self.text, "text")
        self.context_type = ensure_non_empty(self.context_type, "context_type")


@dataclass(slots=True)
class RatingResult:
    target_id: int
    recommended_action: RecommendedAction
    rule_score: int | None = None
    ai_score: int | None = None
    raw_confidence: float | None = None
    confidence: float | None = None
    rating_status: str = "rating_pending"
    source_quality: str | None = None
    rating_version: str = "rules-v1"
    reasons: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    pipeline_run_id: int | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.target_id <= 0:
            raise ValueError("target_id must be positive")
        self.rule_score = ensure_score(self.rule_score, "rule_score")
        self.ai_score = ensure_score(self.ai_score, "ai_score")
        self.raw_confidence = ensure_confidence(self.raw_confidence, "raw_confidence")
        self.confidence = ensure_confidence(self.confidence, "confidence")
        self.rating_status = ensure_non_empty(self.rating_status, "rating_status")
        self.rating_version = ensure_non_empty(self.rating_version, "rating_version")


@dataclass(slots=True)
class Draft:
    target_id: int
    draft_type: str
    draft_version: str
    language: str
    subject: str
    body: str
    status: DraftStatus = DraftStatus.NEEDS_REVIEW
    score_id: int | None = None
    used_context: dict[str, Any] = field(default_factory=dict)
    regenerated_from_draft_id: int | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.target_id <= 0:
            raise ValueError("target_id must be positive")
        self.draft_type = ensure_non_empty(self.draft_type, "draft_type")
        self.draft_version = ensure_non_empty(self.draft_version, "draft_version")
        self.language = ensure_non_empty(self.language, "language")
        self.subject = ensure_non_empty(self.subject, "subject")
        self.body = ensure_non_empty(self.body, "body")
