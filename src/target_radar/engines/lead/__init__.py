"""LeadEngine package."""

from target_radar.engines.lead.engine import LeadEngine, LeadEngineConfig
from target_radar.engines.lead.fake import FakeLeadEngine
from target_radar.engines.lead.provider import (
    BraveSearchProvider,
    FakeSearchProvider,
    SearchProviderError,
    SearchResult,
)
from target_radar.engines.lead.query import QueryBuilder, QueryCandidate

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
]
