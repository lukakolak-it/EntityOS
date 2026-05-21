"""LeadEngine MVP implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from target_radar.domain import (
    LeadResultStatus,
    SearchProfile,
    TargetCandidate,
    domain_from_url,
    normalize_domain,
)
from target_radar.engines.lead.provider import SearchProvider, SearchResult
from target_radar.engines.lead.query import QueryBuilder, hash_query
from target_radar.storage import SQLiteStore


@dataclass(frozen=True, slots=True)
class LeadEngineConfig:
    request_budget: int = 100
    results_per_query: int = 10
    template_set: str | None = None


@dataclass(slots=True)
class LeadEngine:
    provider: SearchProvider
    config: LeadEngineConfig = field(default_factory=LeadEngineConfig)
    query_builder: QueryBuilder = field(default_factory=QueryBuilder)
    blocked_domains: set[str] = field(default_factory=set)
    store: SQLiteStore | None = None
    pipeline_run_id: int | None = None

    def __post_init__(self) -> None:
        self.blocked_domains = {
            normalize_domain(domain) for domain in self.blocked_domains
        }

    def discover(
        self,
        search_profile: SearchProfile,
        *,
        limit: int | None = None,
    ) -> list[TargetCandidate]:
        request_budget = min(
            self.config.request_budget,
            limit if limit is not None else self.config.request_budget,
        )
        queries = self.query_builder.build(
            search_profile,
            template_set=self.config.template_set,
            limit=request_budget,
        )

        candidates: list[TargetCandidate] = []
        seen_domains: set[str] = set()
        for query in queries:
            provider_query_hash = hash_query(self.provider.name, query.text)
            source_query_id = self._record_source_query(
                query_text=query.text,
                query_hash=provider_query_hash,
                query_template=query.query_template,
                template_set=query.template_set,
                query_score=query.score,
            )
            results = self.provider.search(
                query.text,
                limit=self.config.results_per_query,
            )
            for result in results:
                candidate = self._candidate_from_result(result, seen_domains)
                candidates.append(candidate)
                if candidate.status == LeadResultStatus.CANDIDATE:
                    seen_domains.add(candidate.domain or "")
                self._record_serp_result(source_query_id, candidate, result)

        return candidates

    def _candidate_from_result(
        self,
        result: SearchResult,
        seen_domains: set[str],
    ) -> TargetCandidate:
        domain = domain_from_url(result.url)
        if domain in self.blocked_domains:
            status = LeadResultStatus.BLOCKED_SOURCE
        elif domain in seen_domains:
            status = LeadResultStatus.DUPLICATE_DOMAIN
        else:
            status = LeadResultStatus.CANDIDATE

        return TargetCandidate(
            url=result.url,
            source=f"serp:{self.provider.name}",
            title=result.title,
            snippet=result.snippet,
            domain=domain,
            status=status,
            metadata=dict(result.metadata),
        )

    def _record_source_query(
        self,
        *,
        query_text: str,
        query_hash: str,
        query_template: str,
        template_set: str,
        query_score: int,
    ) -> int | None:
        if self.store is None:
            return None
        return self.store.create_source_query(
            provider=self.provider.name,
            query_text=query_text,
            query_hash=query_hash,
            pipeline_run_id=self.pipeline_run_id,
            query_template=query_template,
            template_set=template_set,
            query_score=query_score,
        )

    def _record_serp_result(
        self,
        source_query_id: int | None,
        candidate: TargetCandidate,
        result: SearchResult,
    ) -> None:
        if self.store is None or source_query_id is None:
            return
        self.store.create_serp_result(
            source_query_id=source_query_id,
            url=result.url,
            domain=candidate.domain or "",
            title=result.title,
            snippet=result.snippet,
            status=candidate.status,
            metadata=dict(result.metadata),
        )
