"""Factories for configured LeadEngine dependencies."""

from __future__ import annotations

from target_radar.config import AppConfig, SearchProviderSettings
from target_radar.engines.lead.engine import LeadEngine, LeadEngineConfig
from target_radar.engines.lead.provider import (
    BraveSearchProvider,
    FakeSearchProvider,
    SearchProvider,
)
from target_radar.engines.lead.source_quality import SourceQualityClassifier
from target_radar.storage import SQLiteStore


def create_search_provider(settings: SearchProviderSettings) -> SearchProvider:
    provider = settings.provider.strip().lower()
    if provider in {"mock", "fake"}:
        return FakeSearchProvider()
    if provider == "brave":
        api_key = settings.brave_api_key or settings.search_engine_token
        if not api_key:
            raise ValueError("BRAVE_API_KEY or SEARCH_ENGINE_TOKEN is required")
        return BraveSearchProvider(api_key=api_key)
    raise ValueError(f"unsupported search provider: {settings.provider}")


def create_lead_engine(
    config: AppConfig,
    *,
    store: SQLiteStore | None = None,
    pipeline_run_id: int | None = None,
) -> LeadEngine:
    return LeadEngine(
        provider=create_search_provider(config.search_provider),
        config=LeadEngineConfig(
            request_budget=config.lead_budget.request_budget,
            results_per_query=config.lead_budget.results_per_query,
            source_block_threshold=config.lead_budget.source_block_threshold,
        ),
        source_quality_classifier=SourceQualityClassifier(
            extra_blocked_domains=config.lead_budget.blocked_source_domains,
            block_threshold=config.lead_budget.source_block_threshold,
        ),
        store=store,
        pipeline_run_id=pipeline_run_id,
    )
