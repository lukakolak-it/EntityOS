"""Pipeline orchestration for the offline MVP skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from target_radar.domain import (
    ImportStatus,
    PipelinePhase,
    PipelineRun,
    PipelineRunStatus,
    SearchProfile,
    TargetCandidate,
    TargetStatus,
)
from target_radar.pipeline.importer import TargetImportResult, TargetImporter
from target_radar.storage import SQLiteStore


class LeadEngine(Protocol):
    def discover(
        self,
        search_profile: SearchProfile,
        *,
        limit: int | None = None,
    ) -> list[TargetCandidate]:
        """Discover target candidates."""


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


class PipelineOrchestrator:
    """Coordinate LeadEngine discovery, import and initial review handoff."""

    def __init__(
        self,
        store: SQLiteStore,
        lead_engine: LeadEngine,
        importer: TargetImporter | None = None,
    ) -> None:
        self.store = store
        self.lead_engine = lead_engine
        self.importer = importer or TargetImporter(store)

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
            if hasattr(self.lead_engine, "pipeline_run_id"):
                self.lead_engine.pipeline_run_id = run.id
            candidates = self.lead_engine.discover(
                request.search_profile,
                limit=request.request_budget,
            )
            import_results = self.importer.import_candidates(candidates)

            review_count = 0
            for result in import_results:
                if result.status not in {ImportStatus.IMPORTED, ImportStatus.EXISTING}:
                    continue
                if result.target is None or result.target.id is None:
                    continue
                self.store.set_target_status(
                    result.target.id,
                    TargetStatus.NEEDS_REVIEW,
                    PipelinePhase.IMPORT,
                    pipeline_run_id=run.id,
                    reason="pipeline skeleton imported target for review",
                    metadata={
                        "import_status": result.status.value,
                        "candidate_url": result.candidate.url,
                    },
                )
                review_count += 1

            completed = self.store.update_pipeline_run_status(
                run.id,
                PipelineRunStatus.COMPLETED,
                stats={
                    "candidate_count": len(candidates),
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
                    "review_target_count": review_count,
                },
                finished_at=datetime.now(UTC),
            )
            return PipelineRunResult(
                run=completed,
                import_results=import_results,
                review_target_count=review_count,
            )
        except Exception as exc:
            failed = self.store.update_pipeline_run_status(
                run.id,
                PipelineRunStatus.FAILED,
                error_message=str(exc),
                finished_at=datetime.now(UTC),
            )
            raise PipelineExecutionError(str(exc), failed) from exc


class PipelineExecutionError(RuntimeError):
    def __init__(self, message: str, run: PipelineRun) -> None:
        super().__init__(message)
        self.run = run
