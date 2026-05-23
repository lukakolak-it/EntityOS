"""Pipeline orchestration for local Target Radar runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

from target_radar.domain import (
    Draft,
    Evidence,
    ImportStatus,
    PipelinePhase,
    PipelineRun,
    PipelineRunStatus,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetCandidate,
    TargetPage,
    TargetStatus,
)
from target_radar.engines.evidence import EvidenceEngine
from target_radar.pipeline.extractor import ExtractedPage
from target_radar.pipeline.fetcher import FetchedPage
from target_radar.pipeline.importer import TargetImportResult, TargetImporter
from target_radar.storage import SQLiteStore
from target_radar.use_cases import DraftPolicy, UseCaseConfig


class LeadEngine(Protocol):
    def discover(
        self,
        search_profile: SearchProfile,
        *,
        limit: int | None = None,
    ) -> list[TargetCandidate]:
        """Discover target candidates."""


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage:
        """Fetch a target page."""


class Extractor(Protocol):
    def extract(self, url: str, html: str) -> ExtractedPage:
        """Extract readable page content."""


class RatingEngine(Protocol):
    def rate(
        self,
        target: Target,
        search_profile: SearchProfile,
        evidence: list[Evidence],
        *,
        pipeline_run_id: int | None = None,
        use_case: UseCaseConfig | None = None,
    ) -> RatingResult:
        """Rate a target from persisted evidence."""


class DraftEngine(Protocol):
    def create_draft(
        self,
        *,
        profile: Profile,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        draft_type: str = "application_email",
        draft_policy: DraftPolicy | None = None,
        language: str | None = None,
        regenerated_from_draft_id: int | None = None,
    ) -> Draft:
        """Create a draft for a draft-approved rating."""


@dataclass(frozen=True, slots=True)
class PipelineRunRequest:
    search_profile: SearchProfile
    mode: str = "focused"
    phases: tuple[PipelinePhase, ...] = (PipelinePhase.LEAD, PipelinePhase.IMPORT)
    request_budget: int | None = None
    results_per_query: int | None = None


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    run: PipelineRun
    import_results: list[TargetImportResult] = field(default_factory=list)
    review_target_count: int = 0
    fetched_count: int = 0
    evidence_count: int = 0
    rated_count: int = 0
    drafted_count: int = 0
    error_count: int = 0


@dataclass(frozen=True, slots=True)
class TargetReprocessResult:
    target: Target
    review_target_count: int = 0
    fetched_count: int = 0
    evidence_count: int = 0
    rated_count: int = 0
    drafted_count: int = 0
    error_count: int = 0

    @classmethod
    def from_counts(cls, target: Target, counts: _PipelineCounts) -> TargetReprocessResult:
        return cls(
            target=target,
            review_target_count=counts.review_target_count,
            fetched_count=counts.fetched_count,
            evidence_count=counts.evidence_count,
            rated_count=counts.rated_count,
            drafted_count=counts.drafted_count,
            error_count=counts.error_count,
        )


class PipelineOrchestrator:
    """Coordinate discovery, import, fetch, rating and draft handoff."""

    def __init__(
        self,
        store: SQLiteStore,
        lead_engine: LeadEngine,
        importer: TargetImporter | None = None,
        *,
        fetcher: Fetcher | None = None,
        extractor: Extractor | None = None,
        rating_engine: RatingEngine | None = None,
        draft_engine: DraftEngine | None = None,
        profile: Profile | None = None,
        max_pages_per_target: int = 1,
        evidence_engine: EvidenceEngine | None = None,
    ) -> None:
        self.store = store
        self.lead_engine = lead_engine
        self.importer = importer or TargetImporter(store)
        self.fetcher = fetcher
        self.extractor = extractor
        self.rating_engine = rating_engine
        self.draft_engine = draft_engine
        self.profile = profile
        self.max_pages_per_target = max(1, max_pages_per_target)
        self.evidence_engine = evidence_engine or EvidenceEngine()

    def run(self, request: PipelineRunRequest) -> PipelineRunResult:
        if request.search_profile.id is None:
            raise ValueError("search_profile must be persisted before running pipeline")

        now = datetime.now(UTC)
        run = self.store.create_pipeline_run(
            PipelineRun(
                search_profile_id=request.search_profile.id,
                mode=request.mode,
                status=PipelineRunStatus.RUNNING,
                phases=request.phases,
                request_budget=request.request_budget,
                results_per_query=request.results_per_query,
                started_at=now,
            )
        )

        try:
            candidates: list[TargetCandidate] = []
            if PipelinePhase.LEAD in request.phases:
                if hasattr(self.lead_engine, "pipeline_run_id"):
                    self.lead_engine.pipeline_run_id = run.id
                candidates = self.lead_engine.discover(
                    request.search_profile,
                    limit=request.request_budget,
                )

            import_results: list[TargetImportResult] = []
            if PipelinePhase.IMPORT in request.phases:
                import_results = self.importer.import_candidates(candidates)

            counts = _PipelineCounts()
            for result in import_results:
                if result.status not in {ImportStatus.IMPORTED, ImportStatus.EXISTING}:
                    continue
                if result.target is None or result.target.id is None:
                    continue
                counts.add(
                    self._process_target(
                        result=result,
                        request=request,
                        pipeline_run_id=run.id,
                    )
                )

            run_status = (
                PipelineRunStatus.COMPLETED_WITH_ERRORS
                if counts.error_count
                else PipelineRunStatus.COMPLETED
            )
            completed = self.store.update_pipeline_run_status(
                run.id,
                run_status,
                stats={
                    "candidate_count": len(candidates),
                    "candidate_status_counts": _candidate_status_counts(candidates),
                    "import_status_counts": _import_status_counts(import_results),
                    "source_type_counts": _source_type_counts(import_results),
                    "imported_count": sum(
                        1
                        for result in import_results
                        if result.status == ImportStatus.IMPORTED
                    ),
                    "existing_count": sum(
                        1
                        for result in import_results
                        if result.status == ImportStatus.EXISTING
                    ),
                    "context_source_count": sum(
                        1
                        for result in import_results
                        if result.status == ImportStatus.REVIEW_SOURCE
                    ),
                    "fetched_count": counts.fetched_count,
                    "evidence_count": counts.evidence_count,
                    "rated_count": counts.rated_count,
                    "drafted_count": counts.drafted_count,
                    "review_target_count": counts.review_target_count,
                    "error_count": counts.error_count,
                },
                finished_at=datetime.now(UTC),
            )
            return PipelineRunResult(
                run=completed,
                import_results=import_results,
                review_target_count=counts.review_target_count,
                fetched_count=counts.fetched_count,
                evidence_count=counts.evidence_count,
                rated_count=counts.rated_count,
                drafted_count=counts.drafted_count,
                error_count=counts.error_count,
            )
        except Exception as exc:
            failed = self.store.update_pipeline_run_status(
                run.id,
                PipelineRunStatus.FAILED,
                error_message=str(exc),
                finished_at=datetime.now(UTC),
            )
            raise PipelineExecutionError(str(exc), failed) from exc

    def refetch_target(
        self,
        target_id: int,
        search_profile: SearchProfile,
        *,
        pipeline_run_id: int | None = None,
    ) -> TargetReprocessResult:
        target = self.store.get_target(target_id)
        request = PipelineRunRequest(
            search_profile=search_profile,
            phases=(
                PipelinePhase.FETCH,
                PipelinePhase.EXTRACT,
                PipelinePhase.RATING,
                PipelinePhase.DRAFT,
            ),
        )
        counts = self._process_target(
            result=_existing_target_import_result(target),
            request=request,
            pipeline_run_id=pipeline_run_id,
        )
        return TargetReprocessResult.from_counts(
            self.store.get_target(target_id),
            counts,
        )

    def rerate_target(
        self,
        target_id: int,
        search_profile: SearchProfile,
        *,
        pipeline_run_id: int | None = None,
    ) -> TargetReprocessResult:
        target = self.store.get_target(target_id)
        request = PipelineRunRequest(
            search_profile=search_profile,
            phases=(PipelinePhase.RATING, PipelinePhase.DRAFT),
        )
        counts = self._process_target(
            result=_existing_target_import_result(target),
            request=request,
            pipeline_run_id=pipeline_run_id,
        )
        return TargetReprocessResult.from_counts(
            self.store.get_target(target_id),
            counts,
        )

    def regenerate_draft(
        self,
        target_id: int,
        search_profile: SearchProfile,
        *,
        pipeline_run_id: int | None = None,
    ) -> TargetReprocessResult:
        target = self.store.get_target(target_id)
        ratings = self.store.list_ratings(target_id)
        if not ratings:
            raise ValueError("target has no rating to draft from")

        latest_draft = next(iter(self.store.list_drafts(target_id)), None)
        use_case = self._use_case_for_search_profile(search_profile)
        counts = self._create_draft(
            target=target,
            rating=ratings[0],
            evidence=self.store.list_evidence(target_id),
            language=search_profile.draft_language,
            pipeline_run_id=pipeline_run_id,
            draft_policy=use_case.draft_policy if use_case is not None else None,
            regenerated_from_draft_id=latest_draft.id if latest_draft else None,
        )
        return TargetReprocessResult.from_counts(
            self.store.get_target(target_id),
            counts,
        )

    def _process_target(
        self,
        *,
        result: TargetImportResult,
        request: PipelineRunRequest,
        pipeline_run_id: int | None,
    ) -> _PipelineCounts:
        counts = _PipelineCounts()
        target = result.target
        if target is None or target.id is None:
            return counts

        if not _has_processing_phase(request.phases):
            self._handoff_for_review(
                target=target,
                phase=PipelinePhase.IMPORT,
                pipeline_run_id=pipeline_run_id,
                reason="pipeline imported target for review",
                metadata=_import_metadata(result),
            )
            counts.review_target_count += 1
            return counts

        try:
            if PipelinePhase.FETCH in request.phases:
                fetch_counts, can_continue = self._fetch_and_extract(
                    target=target,
                    request=request,
                    pipeline_run_id=pipeline_run_id,
                )
                counts.add(fetch_counts)
                if not can_continue:
                    return counts

            if PipelinePhase.RATING in request.phases:
                counts.add(
                    self._rate_and_maybe_draft(
                        target=target,
                        request=request,
                        pipeline_run_id=pipeline_run_id,
                    )
                )
                return counts

            self._handoff_for_review(
                target=target,
                phase=PipelinePhase.IMPORT,
                pipeline_run_id=pipeline_run_id,
                reason="pipeline has no rating phase; target requires review",
                metadata=_import_metadata(result),
            )
            counts.review_target_count += 1
            return counts
        except Exception as exc:
            self._record_target_error(
                target_id=target.id,
                pipeline_run_id=pipeline_run_id,
                error=exc,
            )
            counts.error_count += 1
            return counts

    def _fetch_and_extract(
        self,
        *,
        target: Target,
        request: PipelineRunRequest,
        pipeline_run_id: int | None,
    ) -> tuple[_PipelineCounts, bool]:
        counts = _PipelineCounts()
        if target.id is None:
            return counts, False

        if self.fetcher is None:
            self._handoff_for_review(
                target=target,
                phase=PipelinePhase.FETCH,
                pipeline_run_id=pipeline_run_id,
                reason="fetch phase requested but no fetcher is configured",
                metadata={"target_url": target.base_url},
            )
            counts.review_target_count += 1
            return counts, False

        self.store.set_target_status(
            target.id,
            TargetStatus.FETCH_PENDING,
            PipelinePhase.FETCH,
            pipeline_run_id=pipeline_run_id,
            reason="fetch queued",
            metadata={
                "target_url": target.base_url,
                "max_pages": self.max_pages_per_target,
            },
        )

        pending = [target.base_url]
        seen: set[str] = set()
        failed_count = 0

        while pending and len(seen) < self.max_pages_per_target:
            url = pending.pop(0)
            if url in seen:
                continue
            seen.add(url)

            fetched = self.fetcher.fetch(url)
            if not fetched.ok or not fetched.body:
                failed_count += 1
                error_message = fetched.error_message or "empty response body"
                self.store.create_target_page(
                    TargetPage(
                        target_id=target.id,
                        url=fetched.url,
                        http_status=fetched.status_code,
                        error_message=error_message,
                        metadata=_fetch_metadata(fetched),
                        fetched_at=datetime.now(UTC),
                    )
                )
                continue

            extracted, page = self._persist_fetched_page(
                target=target,
                fetched=fetched,
                request=request,
            )
            counts.fetched_count += 1

            evidence_text = _evidence_text(extracted, page.text)
            evidence_candidate = self.evidence_engine.from_target_page(
                page,
                text=evidence_text,
                metadata=_evidence_metadata(extracted),
            )
            if evidence_candidate is not None:
                evidence = self.store.add_evidence(evidence_candidate)
                counts.evidence_count += 1 if evidence.id is not None else 0

            if extracted is not None:
                pending.extend(
                    _relevant_links(
                        base_url=target.base_url,
                        links=extracted.links,
                        seen=seen,
                        pending=pending,
                        remaining=self.max_pages_per_target - len(seen),
                    )
                )

        if counts.fetched_count == 0:
            self.store.set_target_status(
                target.id,
                TargetStatus.FETCH_FAILED,
                PipelinePhase.FETCH,
                pipeline_run_id=pipeline_run_id,
                reason="fetch failed",
                error_message="no usable target page fetched",
                metadata={
                    "target_url": target.base_url,
                    "attempted_urls": list(seen),
                },
            )
            counts.error_count += max(1, failed_count)
            return counts, False

        counts.error_count += failed_count
        status = TargetStatus.FETCH_PARTIAL if failed_count else TargetStatus.FETCHED
        self.store.set_target_status(
            target.id,
            status,
            PipelinePhase.FETCH,
            pipeline_run_id=pipeline_run_id,
            reason="target pages fetched",
            metadata={
                "fetched_count": counts.fetched_count,
                "failed_count": failed_count,
                "attempted_urls": list(seen),
            },
        )
        return counts, True

    def _persist_fetched_page(
        self,
        *,
        target: Target,
        fetched: FetchedPage,
        request: PipelineRunRequest,
    ) -> tuple[ExtractedPage | None, TargetPage]:
        if target.id is None:
            raise ValueError("target must be persisted before page persistence")

        extracted: ExtractedPage | None = None
        page_text = fetched.body
        page_title: str | None = None
        page_type = "other"
        if PipelinePhase.EXTRACT in request.phases and self.extractor is not None:
            extracted = self.extractor.extract(fetched.url, fetched.body or "")
            page_text = extracted.text
            page_title = extracted.title
            page_type = extracted.page_type

        page = self.store.create_target_page(
            TargetPage(
                target_id=target.id,
                url=fetched.url,
                page_type=page_type,
                http_status=fetched.status_code,
                title=page_title,
                text=page_text or None,
                metadata=_page_metadata(fetched, extracted),
                fetched_at=datetime.now(UTC),
            )
        )
        return extracted, page

    def _rate_and_maybe_draft(
        self,
        *,
        target: Target,
        request: PipelineRunRequest,
        pipeline_run_id: int | None,
    ) -> _PipelineCounts:
        counts = _PipelineCounts()
        if target.id is None:
            return counts

        if self.rating_engine is None:
            self._handoff_for_review(
                target=target,
                phase=PipelinePhase.RATING,
                pipeline_run_id=pipeline_run_id,
                reason="rating phase requested but no rating engine is configured",
                metadata={"target_url": target.base_url},
            )
            counts.review_target_count += 1
            return counts

        self.store.set_target_status(
            target.id,
            TargetStatus.RATING_PENDING,
            PipelinePhase.RATING,
            pipeline_run_id=pipeline_run_id,
            reason="rating queued",
        )
        try:
            persisted_target = self.store.get_target(target.id)
            evidence = self.store.list_evidence(target.id)
            use_case = self._use_case_for_search_profile(request.search_profile)
            rating = self.rating_engine.rate(
                persisted_target,
                request.search_profile,
                evidence,
                pipeline_run_id=pipeline_run_id,
                use_case=use_case,
            )
            saved_rating = self.store.save_rating(rating)
            counts.rated_count += 1
        except Exception as exc:
            self.store.set_target_status(
                target.id,
                TargetStatus.RATING_FAILED,
                PipelinePhase.RATING,
                pipeline_run_id=pipeline_run_id,
                reason="rating failed",
                error_message=str(exc),
            )
            counts.error_count += 1
            return counts

        if saved_rating.recommended_action != RecommendedAction.DRAFT:
            self._set_rating_review_status(
                target=target,
                rating=saved_rating,
                pipeline_run_id=pipeline_run_id,
            )
            counts.review_target_count += 1
            return counts

        if PipelinePhase.DRAFT not in request.phases:
            self.store.set_target_status(
                target.id,
                TargetStatus.DRAFT_PENDING,
                PipelinePhase.RATING,
                pipeline_run_id=pipeline_run_id,
                reason="rating recommended draft; draft phase not requested",
                metadata=_rating_metadata(saved_rating),
            )
            counts.review_target_count += 1
            return counts

        counts.add(
            self._create_draft(
                target=target,
                rating=saved_rating,
                evidence=evidence,
                language=request.search_profile.draft_language,
                pipeline_run_id=pipeline_run_id,
                draft_policy=use_case.draft_policy if use_case is not None else None,
            )
        )
        return counts

    def _create_draft(
        self,
        *,
        target: Target,
        rating: RatingResult,
        evidence: list[Evidence],
        language: str | None,
        pipeline_run_id: int | None,
        draft_policy: DraftPolicy | None = None,
        regenerated_from_draft_id: int | None = None,
    ) -> _PipelineCounts:
        counts = _PipelineCounts()
        if target.id is None:
            return counts

        if self.draft_engine is None or self.profile is None:
            self.store.set_target_status(
                target.id,
                TargetStatus.DRAFT_PENDING,
                PipelinePhase.DRAFT,
                pipeline_run_id=pipeline_run_id,
                reason="draft recommended but draft engine or profile is missing",
                metadata=_rating_metadata(rating),
            )
            counts.review_target_count += 1
            return counts

        self.store.set_target_status(
            target.id,
            TargetStatus.DRAFT_PENDING,
            PipelinePhase.DRAFT,
            pipeline_run_id=pipeline_run_id,
            reason="draft queued",
            metadata=_rating_metadata(rating),
        )
        try:
            persisted_target = self.store.get_target(target.id)
            draft = self.draft_engine.create_draft(
                profile=self.profile,
                target=persisted_target,
                rating=rating,
                evidence=evidence,
                draft_policy=draft_policy,
                language=language,
                regenerated_from_draft_id=regenerated_from_draft_id,
            )
            saved_draft = self.store.save_draft(draft)
            self.store.set_target_status(
                target.id,
                TargetStatus.NEEDS_REVIEW,
                PipelinePhase.REVIEW,
                pipeline_run_id=pipeline_run_id,
                reason="draft generated for manual review",
                metadata={
                    **_rating_metadata(rating),
                    "draft_id": saved_draft.id,
                    "draft_status": saved_draft.status.value,
                },
            )
            counts.drafted_count += 1
            counts.review_target_count += 1
            return counts
        except Exception as exc:
            self.store.set_target_status(
                target.id,
                TargetStatus.DRAFT_FAILED,
                PipelinePhase.DRAFT,
                pipeline_run_id=pipeline_run_id,
                reason="draft generation failed",
                error_message=str(exc),
                metadata=_rating_metadata(rating),
            )
            counts.error_count += 1
            counts.review_target_count += 1
            return counts

    def _use_case_for_search_profile(
        self,
        search_profile: SearchProfile,
    ) -> UseCaseConfig | None:
        use_case_id = search_profile.use_case_id
        if use_case_id is None and search_profile.id is not None:
            use_case_id = self.store.get_search_profile(search_profile.id).use_case_id
        if use_case_id is None:
            return None
        return self.store.get_use_case(use_case_id)

    def _set_rating_review_status(
        self,
        *,
        target: Target,
        rating: RatingResult,
        pipeline_run_id: int | None,
    ) -> None:
        if target.id is None:
            return
        status = (
            TargetStatus.RATING_PARTIAL
            if rating.rating_status == TargetStatus.RATING_PARTIAL.value
            else TargetStatus.NEEDS_REVIEW
        )
        self.store.set_target_status(
            target.id,
            status,
            PipelinePhase.RATING,
            pipeline_run_id=pipeline_run_id,
            reason=f"rating recommended {rating.recommended_action.value}",
            metadata=_rating_metadata(rating),
        )

    def _handoff_for_review(
        self,
        *,
        target: Target,
        phase: PipelinePhase,
        pipeline_run_id: int | None,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if target.id is None:
            return
        self.store.set_target_status(
            target.id,
            TargetStatus.NEEDS_REVIEW,
            phase,
            pipeline_run_id=pipeline_run_id,
            reason=reason,
            metadata=metadata,
        )

    def _record_target_error(
        self,
        *,
        target_id: int,
        pipeline_run_id: int | None,
        error: Exception,
    ) -> None:
        self.store.set_target_status(
            target_id,
            TargetStatus.RATING_FAILED,
            PipelinePhase.REPROCESS,
            pipeline_run_id=pipeline_run_id,
            reason="target processing failed",
            error_message=str(error),
        )


class PipelineExecutionError(RuntimeError):
    def __init__(self, message: str, run: PipelineRun) -> None:
        super().__init__(message)
        self.run = run


@dataclass(slots=True)
class _PipelineCounts:
    review_target_count: int = 0
    fetched_count: int = 0
    evidence_count: int = 0
    rated_count: int = 0
    drafted_count: int = 0
    error_count: int = 0

    def add(self, other: _PipelineCounts) -> None:
        self.review_target_count += other.review_target_count
        self.fetched_count += other.fetched_count
        self.evidence_count += other.evidence_count
        self.rated_count += other.rated_count
        self.drafted_count += other.drafted_count
        self.error_count += other.error_count


def _has_processing_phase(phases: tuple[PipelinePhase, ...]) -> bool:
    return any(
        phase in phases
        for phase in (
            PipelinePhase.FETCH,
            PipelinePhase.EXTRACT,
            PipelinePhase.RATING,
            PipelinePhase.DRAFT,
        )
    )


def _import_metadata(result: TargetImportResult) -> dict[str, object]:
    return {
        "import_status": result.status.value,
        "candidate_url": result.candidate.url,
    }


def _candidate_status_counts(candidates: list[TargetCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.status.value] = counts.get(candidate.status.value, 0) + 1
    return counts


def _import_status_counts(import_results: list[TargetImportResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in import_results:
        counts[result.status.value] = counts.get(result.status.value, 0) + 1
    return counts


def _source_type_counts(import_results: list[TargetImportResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in import_results:
        source_quality = result.candidate.metadata.get("source_quality")
        source_type = "unknown"
        if isinstance(source_quality, dict):
            source_type = str(source_quality.get("source_type") or source_type)
        counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def _existing_target_import_result(target: Target) -> TargetImportResult:
    return TargetImportResult(
        candidate=TargetCandidate(
            url=target.base_url,
            source=target.source,
            domain=target.domain,
        ),
        status=ImportStatus.EXISTING,
        target=target,
    )


def _relevant_links(
    *,
    base_url: str,
    links: tuple[str, ...],
    seen: set[str],
    pending: list[str],
    remaining: int,
) -> list[str]:
    if remaining <= 0:
        return []

    base_domain = _netloc(base_url)
    selected: list[str] = []
    queued = set(pending)
    for link in links:
        if link in seen or link in queued or link in selected:
            continue
        if _netloc(link) != base_domain:
            continue
        if not _is_relevant_link(link):
            continue
        selected.append(link)
        if len(selected) >= remaining:
            break
    return selected


def _netloc(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or parsed.path.split("/", 1)[0]).lower().removeprefix("www.")


def _is_relevant_link(url: str) -> bool:
    haystack = urlparse(url).path.lower()
    return any(
        token in haystack
        for token in (
            "career",
            "karriere",
            "jobs",
            "stellen",
            "kontakt",
            "contact",
            "impressum",
            "about",
            "ueber",
            "uber",
        )
    )


def _fetch_metadata(fetched: FetchedPage) -> dict[str, object]:
    metadata = dict(fetched.metadata)
    if fetched.content_type:
        metadata["content_type"] = fetched.content_type
    return metadata


def _page_metadata(
    fetched: FetchedPage,
    extracted: ExtractedPage | None,
) -> dict[str, object]:
    metadata = _fetch_metadata(fetched)
    if extracted is not None:
        metadata.update(
            {
                "description": extracted.description,
                "emails": list(extracted.emails),
                "links": list(extracted.links[:20]),
                "link_count": len(extracted.links),
            }
        )
    return metadata


def _evidence_metadata(extracted: ExtractedPage | None) -> dict[str, object]:
    if extracted is None:
        return {}
    return {
        "title": extracted.title,
        "description": extracted.description,
        "emails": list(extracted.emails),
    }


def _evidence_text(extracted: ExtractedPage | None, fallback_text: str | None) -> str:
    if extracted is None:
        return _clip(fallback_text or "", 5000)
    parts = [extracted.description or "", extracted.text]
    return _clip(" ".join(part for part in parts if part.strip()), 5000)


def _clip(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "."


def _rating_metadata(rating: RatingResult) -> dict[str, object]:
    return {
        "score_id": rating.id,
        "recommended_action": rating.recommended_action.value,
        "rating_status": rating.rating_status,
        "rule_score": rating.rule_score,
        "ai_score": rating.ai_score,
        "confidence": rating.confidence,
    }
