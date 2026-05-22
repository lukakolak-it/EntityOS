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
from target_radar.engines.lead.source_quality import (
    SourceImportAction,
    SourceQualityClassifier,
    SourceQualityResult,
)
from target_radar.storage import SQLiteStore
from target_radar.use_cases import UseCaseConfig


@dataclass(frozen=True, slots=True)
class LeadEngineConfig:
    request_budget: int = 100
    results_per_query: int = 10
    template_set: str | None = None
    source_block_threshold: int = 35


@dataclass(slots=True)
class LeadEngine:
    provider: SearchProvider
    config: LeadEngineConfig = field(default_factory=LeadEngineConfig)
    query_builder: QueryBuilder = field(default_factory=QueryBuilder)
    source_quality_classifier: SourceQualityClassifier = field(
        default_factory=SourceQualityClassifier
    )
    blocked_domains: set[str] = field(default_factory=set)
    store: SQLiteStore | None = None
    pipeline_run_id: int | None = None

    def __post_init__(self) -> None:
        self.blocked_domains = {
            normalize_domain(domain) for domain in self.blocked_domains
        }
        if self.source_quality_classifier.block_threshold != self.config.source_block_threshold:
            self.source_quality_classifier = SourceQualityClassifier(
                extra_blocked_domains=self.source_quality_classifier.extra_blocked_domains,
                block_threshold=self.config.source_block_threshold,
                import_threshold=self.source_quality_classifier.import_threshold,
                preferred_source_types=self.source_quality_classifier.preferred_source_types,
                context_source_types=self.source_quality_classifier.context_source_types,
                blocked_source_types=self.source_quality_classifier.blocked_source_types,
                preferred_domains=self.source_quality_classifier.preferred_domains,
                relevant_path_tokens=self.source_quality_classifier.relevant_path_tokens,
                listing_path_tokens=self.source_quality_classifier.listing_path_tokens,
            )

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
        use_case = self._use_case_for(search_profile)
        queries = self.query_builder.build(
            search_profile,
            template_set=self.config.template_set,
            limit=request_budget,
            use_case=use_case,
        )
        source_quality_classifier = self._source_quality_classifier_for(use_case)

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
            classified_results = self._prioritize_results(
                results,
                source_quality_classifier=source_quality_classifier,
            )
            for result, source_quality in classified_results:
                candidate = self._candidate_from_result(
                    result,
                    seen_domains,
                    source_quality,
                )
                candidates.append(candidate)
                if candidate.status == LeadResultStatus.CANDIDATE:
                    seen_domains.add(candidate.domain or "")
                self._record_serp_result(
                    source_query_id,
                    candidate,
                    result,
                    source_quality,
                )

        return candidates

    def _prioritize_results(
        self,
        results: list[SearchResult],
        *,
        source_quality_classifier: SourceQualityClassifier | None = None,
    ) -> list[tuple[SearchResult, SourceQualityResult]]:
        classifier = source_quality_classifier or self.source_quality_classifier
        classified = [
            (result, classifier.classify(result))
            for result in results
        ]
        return sorted(
            classified,
            key=lambda item: (
                item[1].blocked,
                -item[1].score,
                _provider_rank(item[0]),
            ),
        )

    def _use_case_for(self, search_profile: SearchProfile) -> UseCaseConfig | None:
        if self.store is None:
            return None
        use_case_id = search_profile.use_case_id
        if use_case_id is None and search_profile.id is not None:
            use_case_id = self.store.get_search_profile(search_profile.id).use_case_id
        if use_case_id is None:
            return None
        return self.store.get_use_case(use_case_id)

    def _source_quality_classifier_for(
        self,
        use_case: UseCaseConfig | None,
    ) -> SourceQualityClassifier:
        if use_case is None:
            return self.source_quality_classifier
        return SourceQualityClassifier.from_source_policy(
            use_case.source_policy,
            extra_blocked_domains=self.source_quality_classifier.extra_blocked_domains,
        )

    def _candidate_from_result(
        self,
        result: SearchResult,
        seen_domains: set[str],
        source_quality: SourceQualityResult,
    ) -> TargetCandidate:
        domain = domain_from_url(result.url)
        if domain in self.blocked_domains:
            status = LeadResultStatus.BLOCKED_SOURCE
        elif source_quality.recommended_action == SourceImportAction.BLOCK:
            status = LeadResultStatus.BLOCKED_SOURCE
        elif domain in seen_domains:
            status = LeadResultStatus.DUPLICATE_DOMAIN
        else:
            status = LeadResultStatus.CANDIDATE
        metadata = {
            **dict(result.metadata),
            "source_quality": source_quality.to_metadata(),
        }

        return TargetCandidate(
            url=result.url,
            source=f"serp:{self.provider.name}",
            title=result.title,
            snippet=result.snippet,
            domain=domain,
            status=status,
            metadata=metadata,
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
        source_quality: SourceQualityResult,
    ) -> None:
        if self.store is None or source_query_id is None:
            return
        metadata = {
            **dict(result.metadata),
            "source_quality": source_quality.to_metadata(),
        }
        self.store.create_serp_result(
            source_query_id=source_query_id,
            url=result.url,
            domain=candidate.domain or "",
            title=result.title,
            snippet=result.snippet,
            status=candidate.status,
            metadata=metadata,
        )


def _provider_rank(result: SearchResult) -> int:
    rank = result.metadata.get("provider_rank")
    try:
        return int(rank)
    except (TypeError, ValueError):
        return 999_999
