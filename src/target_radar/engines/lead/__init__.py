"""LeadEngine package."""

from target_radar.engines.lead.engine import LeadEngine, LeadEngineConfig
from target_radar.engines.lead.factory import create_lead_engine, create_search_provider
from target_radar.engines.lead.fake import FakeLeadEngine
from target_radar.engines.lead.provider import (
    BraveSearchProvider,
    FakeSearchProvider,
    SearchProviderError,
    SearchResult,
)
from target_radar.engines.lead.query import QueryBuilder, QueryCandidate
from target_radar.engines.lead.source_quality import (
    SourceImportAction,
    SourceQualityClassifier,
    SourceQualityResult,
    SourceType,
)

__all__ = [
    "BraveSearchProvider",
    "FakeLeadEngine",
    "FakeSearchProvider",
    "LeadEngine",
    "LeadEngineConfig",
    "QueryBuilder",
    "QueryCandidate",
    "SearchProviderError",
    "SearchResult",
    "SourceImportAction",
    "SourceQualityClassifier",
    "SourceQualityResult",
    "SourceType",
    "create_lead_engine",
    "create_search_provider",
]
