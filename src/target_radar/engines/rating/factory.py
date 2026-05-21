"""Factories for configured RatingEngine dependencies."""

from __future__ import annotations

from target_radar.config import AppConfig
from target_radar.engines.rating.ai import LLMAIRatingProvider
from target_radar.engines.rating.engine import RatingEngine
from target_radar.llm import LLMRouter, create_llm_router


def create_rating_engine(
    config: AppConfig,
    *,
    router: LLMRouter | None = None,
    task: str = "heavy",
) -> RatingEngine:
    llm_router = router or create_llm_router(config)
    return RatingEngine(
        config=config.rating,
        ai_provider=LLMAIRatingProvider(router=llm_router, task=task),
        rating_version="rules-v1+llm",
    )
