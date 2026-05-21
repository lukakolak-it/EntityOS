"""Configuration loading for Target Radar.

Infrastructure settings come from the local environment. Product defaults live
in code so behavior is versioned with the repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


DEFAULT_ENV_FILE = ".env"


@dataclass(frozen=True, slots=True)
class InfrastructureSettings:
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/target-radar.local.sqlite3"
    brave_api_key: str | None = None
    openai_api_key: str | None = None


@dataclass(frozen=True, slots=True)
class RatingConfig:
    min_rule_score_for_ai: int = 40
    min_ai_score_for_review: int = 50
    min_ai_score_for_draft: int = 70
    min_confidence_for_draft: float = 0.55
    hard_stop_action: str = "skip"


@dataclass(frozen=True, slots=True)
class LeadBudgetConfig:
    request_budget: int = 100
    results_per_query: int = 10
    max_raw_results: int = 1000
    default_provider: str = "mock"


@dataclass(frozen=True, slots=True)
class FetchConfig:
    timeout_seconds: float = 10.0
    max_pages_per_target: int = 4
    user_agent: str = "TargetRadar/0.1 local"


@dataclass(frozen=True, slots=True)
class ReviewQueueConfig:
    page_size: int = 50
    max_page_size: int = 100
    default_sort: tuple[str, ...] = (
        "recommended_action",
        "ai_score",
        "confidence",
        "updated_at",
    )


@dataclass(frozen=True, slots=True)
class DraftConfig:
    default_draft_language: str = "de"
    default_draft_type: str = "application_email"
    max_body_chars: int = 4000


@dataclass(frozen=True, slots=True)
class AppConfig:
    infrastructure: InfrastructureSettings = field(default_factory=InfrastructureSettings)
    rating: RatingConfig = field(default_factory=RatingConfig)
    lead_budget: LeadBudgetConfig = field(default_factory=LeadBudgetConfig)
    fetch: FetchConfig = field(default_factory=FetchConfig)
    review_queue: ReviewQueueConfig = field(default_factory=ReviewQueueConfig)
    draft: DraftConfig = field(default_factory=DraftConfig)


def load_dotenv(path: str | Path) -> dict[str, str]:
    """Parse a simple .env file without adding a runtime dependency."""

    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_app_config(
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load application config.

    Precedence follows the concept document:
    `.env` values override process environment values, which override code
    defaults.
    """

    values = dict(os.environ if environ is None else environ)
    if env_file is not None:
        values.update(load_dotenv(env_file))

    return AppConfig(
        infrastructure=InfrastructureSettings(
            environment=_get_str(values, "TARGET_RADAR_ENV", "local"),
            log_level=_get_str(values, "LOG_LEVEL", "INFO"),
            database_url=_get_str(
                values,
                "DATABASE_URL",
                "sqlite:///data/target-radar.local.sqlite3",
            ),
            brave_api_key=_get_optional_str(values, "BRAVE_API_KEY"),
            openai_api_key=_get_optional_str(values, "OPENAI_API_KEY"),
        ),
        rating=RatingConfig(
            min_rule_score_for_ai=_get_int(
                values,
                "TARGET_RADAR_MIN_RULE_SCORE_FOR_AI",
                40,
            ),
            min_ai_score_for_review=_get_int(
                values,
                "TARGET_RADAR_MIN_AI_SCORE_FOR_REVIEW",
                50,
            ),
            min_ai_score_for_draft=_get_int(
                values,
                "TARGET_RADAR_MIN_AI_SCORE_FOR_DRAFT",
                70,
            ),
            min_confidence_for_draft=_get_float(
                values,
                "TARGET_RADAR_MIN_CONFIDENCE_FOR_DRAFT",
                0.55,
            ),
            hard_stop_action=_get_str(values, "TARGET_RADAR_HARD_STOP_ACTION", "skip"),
        ),
        lead_budget=LeadBudgetConfig(
            request_budget=_get_int(values, "TARGET_RADAR_REQUEST_BUDGET", 100),
            results_per_query=_get_int(values, "TARGET_RADAR_RESULTS_PER_QUERY", 10),
            max_raw_results=_get_int(values, "TARGET_RADAR_MAX_RAW_RESULTS", 1000),
            default_provider=_get_str(values, "TARGET_RADAR_DEFAULT_PROVIDER", "mock"),
        ),
        fetch=FetchConfig(
            timeout_seconds=_get_float(values, "TARGET_RADAR_FETCH_TIMEOUT_SECONDS", 10),
            max_pages_per_target=_get_int(values, "TARGET_RADAR_MAX_PAGES_PER_TARGET", 4),
            user_agent=_get_str(
                values,
                "TARGET_RADAR_USER_AGENT",
                "TargetRadar/0.1 local",
            ),
        ),
        review_queue=ReviewQueueConfig(
            page_size=_get_int(values, "TARGET_RADAR_REVIEW_PAGE_SIZE", 50),
            max_page_size=_get_int(values, "TARGET_RADAR_REVIEW_MAX_PAGE_SIZE", 100),
        ),
        draft=DraftConfig(
            default_draft_language=_get_str(values, "TARGET_RADAR_DRAFT_LANGUAGE", "de"),
            default_draft_type=_get_str(
                values,
                "TARGET_RADAR_DRAFT_TYPE",
                "application_email",
            ),
            max_body_chars=_get_int(values, "TARGET_RADAR_DRAFT_MAX_BODY_CHARS", 4000),
        ),
    )


def _get_optional_str(values: Mapping[str, str], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_str(values: Mapping[str, str], key: str, default: str) -> str:
    value = _get_optional_str(values, key)
    return value if value is not None else default


def _get_int(values: Mapping[str, str], key: str, default: int) -> int:
    value = _get_optional_str(values, key)
    return int(value) if value is not None else default


def _get_float(values: Mapping[str, str], key: str, default: float) -> float:
    value = _get_optional_str(values, key)
    return float(value) if value is not None else default
