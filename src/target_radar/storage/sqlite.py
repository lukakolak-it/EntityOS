"""SQLite repository layer for the local MVP."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from target_radar.domain import (
    Draft,
    DraftStatus,
    Evidence,
    ImportStatus,
    LeadResultStatus,
    PipelinePhase,
    PipelineRun,
    PipelineRunStatus,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    StatusLog,
    Target,
    TargetPage,
    TargetStatus,
)
from target_radar.storage.schema import init_db
from target_radar.use_cases import (
    UseCaseConfig,
    UseCaseStatus,
    validate_use_case_config,
)


class StorageError(RuntimeError):
    """Base storage error."""


class NotFoundError(StorageError):
    """Raised when a requested row does not exist."""


def sqlite_path_from_url(database_url: str) -> str:
    """Convert a sqlite URL or plain path into a sqlite3 path."""

    if database_url == ":memory:":
        return database_url
    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
        return path or ":memory:"
    if database_url.startswith("sqlite://"):
        raise ValueError(f"unsupported sqlite URL: {database_url}")
    return database_url


def connect_sqlite(database_url: str) -> sqlite3.Connection:
    """Open a SQLite connection for a URL or path."""

    path = sqlite_path_from_url(database_url)
    if path != ":memory:":
        parent = Path(path).expanduser().resolve().parent
        parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class SQLiteStore:
    """Small repository facade around the local SQLite database."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def open(cls, database_url: str, *, initialize: bool = True) -> "SQLiteStore":
        connection = connect_sqlite(database_url)
        store = cls(connection)
        if initialize:
            store.initialize()
        return store

    def initialize(self) -> None:
        init_db(self.connection)

    def close(self) -> None:
        self.connection.close()

    def save_use_case(self, use_case: UseCaseConfig) -> int:
        validated = validate_use_case_config(use_case)
        existing = self.connection.execute(
            "SELECT id, created_at FROM use_cases WHERE slug = ?",
            (validated.id,),
        ).fetchone()
        now = datetime.now(UTC)
        if existing is None:
            cursor = self.connection.execute(
                """
                INSERT INTO use_cases (
                    slug, name, description, version, status, config_json,
                    created_from_template, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _use_case_values(validated, created_at=now, updated_at=now),
            )
            self.connection.commit()
            return int(cursor.lastrowid)

        self.connection.execute(
            """
            UPDATE use_cases
            SET name = ?, description = ?, version = ?, status = ?,
                config_json = ?, created_from_template = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                validated.name,
                validated.description,
                validated.version,
                validated.status.value,
                _json_dumps(validated.to_dict()),
                validated.created_from_template,
                _format_dt(now),
                int(existing["id"]),
            ),
        )
        self.connection.commit()
        return int(existing["id"])

    def get_use_case(self, use_case_id: int) -> UseCaseConfig:
        row = self.connection.execute(
            "SELECT * FROM use_cases WHERE id = ?",
            (use_case_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"use case not found: {use_case_id}")
        return _use_case_from_row(row)

    def get_use_case_by_slug(self, slug: str) -> UseCaseConfig:
        row = self.connection.execute(
            "SELECT * FROM use_cases WHERE slug = ?",
            (slug,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"use case not found: {slug}")
        return _use_case_from_row(row)

    def get_use_case_id_by_slug(self, slug: str) -> int:
        row = self.connection.execute(
            "SELECT id FROM use_cases WHERE slug = ?",
            (slug,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"use case not found: {slug}")
        return int(row["id"])

    def list_use_cases(
        self,
        *,
        status: UseCaseStatus | str | None = None,
    ) -> list[UseCaseConfig]:
        if status is None:
            rows = self.connection.execute(
                "SELECT * FROM use_cases ORDER BY slug ASC",
            ).fetchall()
            return [_use_case_from_row(row) for row in rows]

        selected_status = UseCaseStatus(status).value
        rows = self.connection.execute(
            """
            SELECT * FROM use_cases
            WHERE status = ?
            ORDER BY slug ASC
            """,
            (selected_status,),
        ).fetchall()
        return [_use_case_from_row(row) for row in rows]

    def create_profile(self, profile: Profile) -> Profile:
        cursor = self.connection.execute(
            """
            INSERT INTO profiles (
                name, preset, draft_language, attributes_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                profile.name,
                profile.preset,
                profile.draft_language,
                _json_dumps(profile.attributes),
                _format_dt(profile.created_at),
            ),
        )
        self.connection.commit()
        return Profile(
            id=cursor.lastrowid,
            name=profile.name,
            preset=profile.preset,
            draft_language=profile.draft_language,
            attributes=dict(profile.attributes),
            created_at=profile.created_at,
        )

    def get_profile(self, profile_id: int) -> Profile:
        row = self.connection.execute(
            "SELECT * FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"profile not found: {profile_id}")
        return _profile_from_row(row)

    def create_search_profile(self, search_profile: SearchProfile) -> SearchProfile:
        use_case_id = search_profile.use_case_id or self.get_use_case_id_by_slug(
            "application_student"
        )
        cursor = self.connection.execute(
            """
            INSERT INTO search_profiles (
                profile_id, use_case_id, name, roles_json, regions_json,
                tech_keywords_json, industry_keywords_json,
                exclude_keywords_json, attributes_json, manual_query,
                draft_language, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                search_profile.profile_id,
                use_case_id,
                search_profile.name,
                _json_dumps(list(search_profile.roles)),
                _json_dumps(list(search_profile.regions)),
                _json_dumps(list(search_profile.tech_keywords)),
                _json_dumps(list(search_profile.industry_keywords)),
                _json_dumps(list(search_profile.exclude_keywords)),
                _json_dumps(search_profile.attributes),
                search_profile.manual_query,
                search_profile.draft_language,
                _format_dt(search_profile.created_at),
            ),
        )
        self.connection.commit()
        return SearchProfile(
            id=cursor.lastrowid,
            profile_id=search_profile.profile_id,
            use_case_id=use_case_id,
            name=search_profile.name,
            roles=search_profile.roles,
            regions=search_profile.regions,
            tech_keywords=search_profile.tech_keywords,
            industry_keywords=search_profile.industry_keywords,
            exclude_keywords=search_profile.exclude_keywords,
            attributes=dict(search_profile.attributes),
            manual_query=search_profile.manual_query,
            draft_language=search_profile.draft_language,
            created_at=search_profile.created_at,
        )

    def get_search_profile(self, search_profile_id: int) -> SearchProfile:
        row = self.connection.execute(
            "SELECT * FROM search_profiles WHERE id = ?",
            (search_profile_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"search profile not found: {search_profile_id}")
        return _search_profile_from_row(row)

    def list_search_profiles(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                search_profiles.*,
                profiles.name AS profile_name,
                use_cases.slug AS use_case_slug,
                use_cases.name AS use_case_name
            FROM search_profiles
            INNER JOIN profiles
                ON profiles.id = search_profiles.profile_id
            LEFT JOIN use_cases
                ON use_cases.id = search_profiles.use_case_id
            ORDER BY search_profiles.created_at DESC, search_profiles.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_search_profile_payload_from_row(row) for row in rows]

    def update_search_profile_use_case(
        self,
        search_profile_id: int,
        use_case_id: int,
    ) -> SearchProfile:
        self.get_use_case(use_case_id)
        cursor = self.connection.execute(
            """
            UPDATE search_profiles
            SET use_case_id = ?
            WHERE id = ?
            """,
            (use_case_id, search_profile_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"search profile not found: {search_profile_id}")
        self.connection.commit()
        return self.get_search_profile(search_profile_id)

    def create_pipeline_run(self, run: PipelineRun) -> PipelineRun:
        use_case_id, use_case_version, use_case_snapshot = self._pipeline_use_case_context(run)
        cursor = self.connection.execute(
            """
            INSERT INTO pipeline_runs (
                search_profile_id, use_case_id, use_case_version, use_case_snapshot_json,
                mode, status, phases_json, request_budget, results_per_query,
                stats_json, error_message, started_at, finished_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.search_profile_id,
                use_case_id,
                use_case_version,
                _json_dumps(use_case_snapshot) if use_case_snapshot else None,
                run.mode,
                run.status.value,
                _json_dumps([phase.value for phase in run.phases]),
                run.request_budget,
                run.results_per_query,
                _json_dumps(run.stats),
                run.error_message,
                _format_optional_dt(run.started_at),
                _format_optional_dt(run.finished_at),
                _format_dt(run.created_at),
            ),
        )
        self.connection.commit()
        return self.get_pipeline_run(int(cursor.lastrowid))

    def _pipeline_use_case_context(
        self,
        run: PipelineRun,
    ) -> tuple[int | None, int | None, dict[str, Any]]:
        use_case_id = run.use_case_id
        if use_case_id is None:
            row = self.connection.execute(
                "SELECT use_case_id FROM search_profiles WHERE id = ?",
                (run.search_profile_id,),
            ).fetchone()
            if row is not None:
                use_case_id = row["use_case_id"]

        use_case_snapshot = dict(run.use_case_snapshot)
        use_case_version = run.use_case_version
        if use_case_id is not None and (not use_case_snapshot or use_case_version is None):
            use_case = self.get_use_case(int(use_case_id))
            if not use_case_snapshot:
                use_case_snapshot = use_case.to_dict()
            if use_case_version is None:
                use_case_version = use_case.version

        return (
            int(use_case_id) if use_case_id is not None else None,
            use_case_version,
            use_case_snapshot,
        )

    def get_pipeline_run(self, run_id: int) -> PipelineRun:
        row = self.connection.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"pipeline run not found: {run_id}")
        return _pipeline_run_from_row(row)

    def update_pipeline_run_status(
        self,
        run_id: int | None,
        status: PipelineRunStatus,
        *,
        stats: dict[str, Any] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> PipelineRun:
        if run_id is None:
            raise ValueError("run_id must be set")

        existing = self.get_pipeline_run(run_id)
        next_stats = stats if stats is not None else existing.stats
        next_started_at = started_at if started_at is not None else existing.started_at
        next_finished_at = (
            finished_at if finished_at is not None else existing.finished_at
        )

        self.connection.execute(
            """
            UPDATE pipeline_runs
            SET status = ?, stats_json = ?, error_message = ?,
                started_at = ?, finished_at = ?
            WHERE id = ?
            """,
            (
                status.value,
                _json_dumps(next_stats),
                error_message,
                _format_optional_dt(next_started_at),
                _format_optional_dt(next_finished_at),
                run_id,
            ),
        )
        self.connection.commit()
        return self.get_pipeline_run(run_id)

    def create_target(self, target: Target) -> Target:
        cursor = self.connection.execute(
            """
            INSERT INTO targets (
                domain, base_url, source, status, metadata_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.domain,
                target.base_url,
                target.source,
                target.status.value,
                _json_dumps(target.metadata),
                _format_dt(target.created_at),
                _format_dt(target.updated_at),
            ),
        )
        self.connection.commit()
        return self.get_target(int(cursor.lastrowid))

    def create_source_query(
        self,
        *,
        provider: str,
        query_text: str,
        query_hash: str,
        pipeline_run_id: int | None = None,
        query_template: str | None = None,
        template_set: str | None = None,
        query_score: int | None = None,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO source_queries (
                pipeline_run_id, provider, query_text, query_hash,
                query_template, template_set, query_score, status,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pipeline_run_id,
                provider,
                query_text,
                query_hash,
                query_template,
                template_set,
                query_score,
                status,
                _json_dumps(metadata or {}),
                _format_dt(datetime.now(UTC)),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_serp_result(
        self,
        *,
        source_query_id: int,
        url: str,
        domain: str,
        status: LeadResultStatus,
        target_id: int | None = None,
        title: str | None = None,
        snippet: str | None = None,
        import_status: ImportStatus | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO serp_results (
                source_query_id, target_id, url, domain, title, snippet,
                status, import_status, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_query_id,
                target_id,
                url,
                domain,
                title,
                snippet,
                status.value,
                import_status.value if import_status is not None else None,
                _json_dumps(metadata or {}),
                _format_dt(datetime.now(UTC)),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get_target(self, target_id: int) -> Target:
        row = self.connection.execute(
            "SELECT * FROM targets WHERE id = ?",
            (target_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"target not found: {target_id}")
        return _target_from_row(row)

    def get_target_by_domain(self, domain: str) -> Target | None:
        row = self.connection.execute(
            "SELECT * FROM targets WHERE domain = ?",
            (domain,),
        ).fetchone()
        return _target_from_row(row) if row is not None else None

    def set_target_status(
        self,
        target_id: int,
        to_status: TargetStatus,
        phase: PipelinePhase,
        *,
        pipeline_run_id: int | None = None,
        reason: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StatusLog:
        now = datetime.now(UTC)
        with self.connection:
            row = self.connection.execute(
                "SELECT status FROM targets WHERE id = ?",
                (target_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError(f"target not found: {target_id}")
            from_status = TargetStatus(row["status"])

            self.connection.execute(
                "UPDATE targets SET status = ?, updated_at = ? WHERE id = ?",
                (to_status.value, _format_dt(now), target_id),
            )
            cursor = self.connection.execute(
                """
                INSERT INTO target_status_log (
                    target_id, pipeline_run_id, from_status, to_status, phase,
                    reason, error_message, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    pipeline_run_id,
                    from_status.value,
                    to_status.value,
                    phase.value,
                    reason,
                    error_message,
                    _json_dumps(metadata or {}),
                    _format_dt(now),
                ),
            )

        return StatusLog(
            id=int(cursor.lastrowid),
            target_id=target_id,
            pipeline_run_id=pipeline_run_id,
            from_status=from_status,
            to_status=to_status,
            phase=phase,
            reason=reason,
            error_message=error_message,
            metadata=metadata or {},
            created_at=now,
        )

    def list_status_logs(self, target_id: int) -> list[StatusLog]:
        rows = self.connection.execute(
            """
            SELECT * FROM target_status_log
            WHERE target_id = ?
            ORDER BY id ASC
            """,
            (target_id,),
        ).fetchall()
        return [_status_log_from_row(row) for row in rows]

    def list_pipeline_runs(self, *, limit: int = 20) -> list[PipelineRun]:
        rows = self.connection.execute(
            """
            SELECT * FROM pipeline_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_pipeline_run_from_row(row) for row in rows]

    def get_latest_pipeline_run_for_target(self, target_id: int) -> PipelineRun | None:
        row = self.connection.execute(
            """
            SELECT pipeline_runs.*
            FROM pipeline_runs
            INNER JOIN target_scores
                ON target_scores.pipeline_run_id = pipeline_runs.id
            WHERE target_scores.target_id = ?
            ORDER BY target_scores.id DESC
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        if row is not None:
            return _pipeline_run_from_row(row)

        row = self.connection.execute(
            """
            SELECT pipeline_runs.*
            FROM pipeline_runs
            INNER JOIN target_status_log
                ON target_status_log.pipeline_run_id = pipeline_runs.id
            WHERE target_status_log.target_id = ?
            ORDER BY target_status_log.id DESC
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        return _pipeline_run_from_row(row) if row is not None else None

    def add_evidence(self, evidence: Evidence) -> Evidence:
        cursor = self.connection.execute(
            """
            INSERT INTO evidence (
                target_id, page_id, source_url, text, context_type,
                priority, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.target_id,
                evidence.page_id,
                evidence.source_url,
                evidence.text,
                evidence.context_type,
                evidence.priority,
                _json_dumps(evidence.metadata),
                _format_dt(evidence.created_at),
            ),
        )
        self.connection.commit()
        return Evidence(
            id=int(cursor.lastrowid),
            target_id=evidence.target_id,
            page_id=evidence.page_id,
            source_url=evidence.source_url,
            text=evidence.text,
            context_type=evidence.context_type,
            priority=evidence.priority,
            metadata=dict(evidence.metadata),
            created_at=evidence.created_at,
        )

    def list_evidence(self, target_id: int) -> list[Evidence]:
        rows = self.connection.execute(
            """
            SELECT * FROM evidence
            WHERE target_id = ?
            ORDER BY priority DESC, id ASC
            """,
            (target_id,),
        ).fetchall()
        return [_evidence_from_row(row) for row in rows]

    def create_target_page(self, page: TargetPage) -> TargetPage:
        cursor = self.connection.execute(
            """
            INSERT INTO target_pages (
                target_id, url, page_type, http_status, title, text,
                error_message, metadata_json, fetched_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page.target_id,
                page.url,
                page.page_type,
                page.http_status,
                page.title,
                page.text,
                page.error_message,
                _json_dumps(page.metadata),
                _format_optional_dt(page.fetched_at),
                _format_dt(page.created_at),
            ),
        )
        self.connection.commit()
        return TargetPage(
            id=int(cursor.lastrowid),
            target_id=page.target_id,
            url=page.url,
            page_type=page.page_type,
            http_status=page.http_status,
            title=page.title,
            text=page.text,
            error_message=page.error_message,
            metadata=dict(page.metadata),
            fetched_at=page.fetched_at,
            created_at=page.created_at,
        )

    def list_target_pages(self, target_id: int) -> list[TargetPage]:
        rows = self.connection.execute(
            """
            SELECT * FROM target_pages
            WHERE target_id = ?
            ORDER BY id ASC
            """,
            (target_id,),
        ).fetchall()
        return [_target_page_from_row(row) for row in rows]

    def save_rating(self, rating: RatingResult) -> RatingResult:
        cursor = self.connection.execute(
            """
            INSERT INTO target_scores (
                target_id, pipeline_run_id, rule_score, ai_score,
                raw_confidence, confidence, recommended_action, rating_status,
                source_quality, rating_version, reasons_json, risks_json,
                evidence_json, input_snapshot_json, error_type, error_message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rating.target_id,
                rating.pipeline_run_id,
                rating.rule_score,
                rating.ai_score,
                rating.raw_confidence,
                rating.confidence,
                rating.recommended_action.value,
                rating.rating_status,
                rating.source_quality,
                rating.rating_version,
                _json_dumps(rating.reasons),
                _json_dumps(rating.risks),
                _json_dumps(rating.evidence),
                _json_dumps(rating.input_snapshot),
                rating.error_type,
                rating.error_message,
                _format_dt(rating.created_at),
            ),
        )
        self.connection.commit()
        return RatingResult(
            id=int(cursor.lastrowid),
            target_id=rating.target_id,
            pipeline_run_id=rating.pipeline_run_id,
            rule_score=rating.rule_score,
            ai_score=rating.ai_score,
            raw_confidence=rating.raw_confidence,
            confidence=rating.confidence,
            recommended_action=rating.recommended_action,
            rating_status=rating.rating_status,
            source_quality=rating.source_quality,
            rating_version=rating.rating_version,
            reasons=list(rating.reasons),
            risks=list(rating.risks),
            evidence=list(rating.evidence),
            input_snapshot=dict(rating.input_snapshot),
            error_type=rating.error_type,
            error_message=rating.error_message,
            created_at=rating.created_at,
        )

    def list_ratings(self, target_id: int) -> list[RatingResult]:
        rows = self.connection.execute(
            """
            SELECT * FROM target_scores
            WHERE target_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (target_id,),
        ).fetchall()
        return [_rating_from_row(row) for row in rows]

    def save_draft(self, draft: Draft) -> Draft:
        cursor = self.connection.execute(
            """
            INSERT INTO action_drafts (
                target_id, score_id, draft_type, draft_version, language,
                subject, body, status, used_context_json,
                regenerated_from_draft_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft.target_id,
                draft.score_id,
                draft.draft_type,
                draft.draft_version,
                draft.language,
                draft.subject,
                draft.body,
                draft.status.value,
                _json_dumps(draft.used_context),
                draft.regenerated_from_draft_id,
                _format_dt(draft.created_at),
                _format_dt(draft.updated_at),
            ),
        )
        self.connection.commit()
        return Draft(
            id=int(cursor.lastrowid),
            target_id=draft.target_id,
            score_id=draft.score_id,
            draft_type=draft.draft_type,
            draft_version=draft.draft_version,
            language=draft.language,
            subject=draft.subject,
            body=draft.body,
            status=draft.status,
            used_context=dict(draft.used_context),
            regenerated_from_draft_id=draft.regenerated_from_draft_id,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    def list_drafts(self, target_id: int) -> list[Draft]:
        rows = self.connection.execute(
            """
            SELECT * FROM action_drafts
            WHERE target_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (target_id,),
        ).fetchall()
        return [_draft_from_row(row) for row in rows]

    def update_draft(
        self,
        draft_id: int,
        *,
        subject: str | None = None,
        body: str | None = None,
        status: DraftStatus | None = None,
    ) -> Draft:
        row = self.connection.execute(
            "SELECT * FROM action_drafts WHERE id = ?",
            (draft_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"draft not found: {draft_id}")

        current = _draft_from_row(row)
        next_subject = subject if subject is not None else current.subject
        next_body = body if body is not None else current.body
        next_status = status if status is not None else current.status
        updated_at = datetime.now(UTC)

        self.connection.execute(
            """
            UPDATE action_drafts
            SET subject = ?, body = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_subject,
                next_body,
                next_status.value,
                _format_dt(updated_at),
                draft_id,
            ),
        )
        self.connection.commit()

        return Draft(
            id=current.id,
            target_id=current.target_id,
            score_id=current.score_id,
            draft_type=current.draft_type,
            draft_version=current.draft_version,
            language=current.language,
            subject=next_subject,
            body=next_body,
            status=next_status,
            used_context=dict(current.used_context),
            regenerated_from_draft_id=current.regenerated_from_draft_id,
            created_at=current.created_at,
            updated_at=updated_at,
        )

    def list_review_targets(self, *, limit: int = 50, offset: int = 0) -> list[Target]:
        rows = self.connection.execute(
            """
            SELECT * FROM targets
            WHERE status IN (?, ?, ?, ?)
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (
                TargetStatus.NEEDS_REVIEW.value,
                TargetStatus.RATING_PARTIAL.value,
                TargetStatus.DRAFT_PENDING.value,
                TargetStatus.DRAFT_FAILED.value,
                limit,
                offset,
            ),
        ).fetchall()
        return [_target_from_row(row) for row in rows]

    def list_domains_by_status(self, *statuses: TargetStatus) -> set[str]:
        if not statuses:
            return set()
        placeholders = ", ".join("?" for _ in statuses)
        rows = self.connection.execute(
            f"""
            SELECT domain FROM targets
            WHERE status IN ({placeholders})
            """,
            tuple(status.value for status in statuses),
        ).fetchall()
        return {str(row["domain"]) for row in rows}

    def list_review_queue_items(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        use_case_id: int | None = None,
    ) -> list[dict[str, Any]]:
        use_case_filter = ""
        params: list[object] = [
            TargetStatus.NEEDS_REVIEW.value,
            TargetStatus.RATING_PARTIAL.value,
            TargetStatus.DRAFT_PENDING.value,
            TargetStatus.DRAFT_FAILED.value,
        ]
        if use_case_id is not None:
            use_case_filter = "AND pipeline_runs.use_case_id = ?"
            params.append(use_case_id)
        params.extend([limit, offset])
        rows = self.connection.execute(
            f"""
            SELECT
                targets.id,
                targets.domain,
                targets.base_url,
                targets.source,
                targets.status,
                targets.updated_at,
                latest_score.pipeline_run_id AS score_pipeline_run_id,
                latest_score.rule_score,
                latest_score.ai_score,
                latest_score.confidence,
                latest_score.recommended_action,
                latest_score.rating_status,
                pipeline_runs.id AS pipeline_run_id,
                pipeline_runs.search_profile_id,
                pipeline_runs.use_case_id,
                use_cases.slug AS use_case_slug,
                use_cases.name AS use_case_name
            FROM targets
            LEFT JOIN (
                SELECT target_scores.*
                FROM target_scores
                INNER JOIN (
                    SELECT target_id, MAX(id) AS max_id
                    FROM target_scores
                    GROUP BY target_id
                ) latest
                    ON latest.target_id = target_scores.target_id
                    AND latest.max_id = target_scores.id
            ) latest_score
                ON latest_score.target_id = targets.id
            LEFT JOIN (
                SELECT target_status_log.target_id, target_status_log.pipeline_run_id
                FROM target_status_log
                INNER JOIN (
                    SELECT target_id, MAX(id) AS max_id
                    FROM target_status_log
                    WHERE pipeline_run_id IS NOT NULL
                    GROUP BY target_id
                ) latest_log
                    ON latest_log.target_id = target_status_log.target_id
                    AND latest_log.max_id = target_status_log.id
            ) latest_status_log
                ON latest_status_log.target_id = targets.id
            LEFT JOIN pipeline_runs
                ON pipeline_runs.id = COALESCE(
                    latest_score.pipeline_run_id,
                    latest_status_log.pipeline_run_id
                )
            LEFT JOIN use_cases
                ON use_cases.id = pipeline_runs.use_case_id
            WHERE targets.status IN (?, ?, ?, ?)
            {use_case_filter}
            ORDER BY
                CASE latest_score.recommended_action
                    WHEN 'draft' THEN 0
                    WHEN 'review' THEN 1
                    WHEN 'skip' THEN 2
                    ELSE 3
                END,
                COALESCE(latest_score.ai_score, latest_score.rule_score, 0) DESC,
                COALESCE(latest_score.confidence, 0) DESC,
                targets.updated_at DESC,
                targets.id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _use_case_values(
    use_case: UseCaseConfig,
    *,
    created_at: datetime,
    updated_at: datetime,
) -> tuple[object, ...]:
    return (
        use_case.id,
        use_case.name,
        use_case.description,
        use_case.version,
        use_case.status.value,
        _json_dumps(use_case.to_dict()),
        use_case.created_from_template,
        _format_dt(created_at),
        _format_dt(updated_at),
    )


def _use_case_from_row(row: sqlite3.Row) -> UseCaseConfig:
    return UseCaseConfig.from_dict(_json_loads(row["config_json"], {}))


def _format_dt(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _format_optional_dt(value: datetime | None) -> str | None:
    return _format_dt(value) if value is not None else None


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _parse_optional_dt(value: str | None) -> datetime | None:
    return _parse_dt(value) if value is not None else None


def _tuple_enum(values: Iterable[str]) -> tuple[PipelinePhase, ...]:
    return tuple(PipelinePhase(value) for value in values)


def _profile_from_row(row: sqlite3.Row) -> Profile:
    return Profile(
        id=int(row["id"]),
        name=row["name"],
        preset=row["preset"],
        draft_language=row["draft_language"],
        attributes=_json_loads(row["attributes_json"], {}),
        created_at=_parse_dt(row["created_at"]),
    )


def _search_profile_from_row(row: sqlite3.Row) -> SearchProfile:
    return SearchProfile(
        id=int(row["id"]),
        profile_id=int(row["profile_id"]),
        use_case_id=row["use_case_id"],
        name=row["name"],
        roles=tuple(_json_loads(row["roles_json"], [])),
        regions=tuple(_json_loads(row["regions_json"], [])),
        tech_keywords=tuple(_json_loads(row["tech_keywords_json"], [])),
        industry_keywords=tuple(_json_loads(row["industry_keywords_json"], [])),
        exclude_keywords=tuple(_json_loads(row["exclude_keywords_json"], [])),
        attributes=_json_loads(row["attributes_json"], {}),
        manual_query=row["manual_query"],
        draft_language=row["draft_language"],
        created_at=_parse_dt(row["created_at"]),
    )


def _search_profile_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "profile_id": int(row["profile_id"]),
        "profile_name": row["profile_name"],
        "use_case_id": row["use_case_id"],
        "use_case_slug": row["use_case_slug"],
        "use_case_name": row["use_case_name"],
        "name": row["name"],
        "roles": _json_loads(row["roles_json"], []),
        "regions": _json_loads(row["regions_json"], []),
        "tech_keywords": _json_loads(row["tech_keywords_json"], []),
        "industry_keywords": _json_loads(row["industry_keywords_json"], []),
        "exclude_keywords": _json_loads(row["exclude_keywords_json"], []),
        "attributes": _json_loads(row["attributes_json"], {}),
        "manual_query": row["manual_query"],
        "draft_language": row["draft_language"],
        "created_at": row["created_at"],
    }


def _target_from_row(row: sqlite3.Row) -> Target:
    return Target(
        id=int(row["id"]),
        domain=row["domain"],
        base_url=row["base_url"],
        source=row["source"],
        status=TargetStatus(row["status"]),
        metadata=_json_loads(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _target_page_from_row(row: sqlite3.Row) -> TargetPage:
    return TargetPage(
        id=int(row["id"]),
        target_id=int(row["target_id"]),
        url=row["url"],
        page_type=row["page_type"],
        http_status=row["http_status"],
        title=row["title"],
        text=row["text"],
        error_message=row["error_message"],
        metadata=_json_loads(row["metadata_json"], {}),
        fetched_at=_parse_optional_dt(row["fetched_at"]),
        created_at=_parse_dt(row["created_at"]),
    )


def _evidence_from_row(row: sqlite3.Row) -> Evidence:
    return Evidence(
        id=int(row["id"]),
        target_id=int(row["target_id"]),
        page_id=row["page_id"],
        source_url=row["source_url"],
        text=row["text"],
        context_type=row["context_type"],
        priority=int(row["priority"]),
        metadata=_json_loads(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]),
    )


def _pipeline_run_from_row(row: sqlite3.Row) -> PipelineRun:
    return PipelineRun(
        id=int(row["id"]),
        search_profile_id=int(row["search_profile_id"]),
        use_case_id=row["use_case_id"],
        use_case_version=row["use_case_version"],
        use_case_snapshot=_json_loads(row["use_case_snapshot_json"], {}),
        mode=row["mode"],
        status=PipelineRunStatus(row["status"]),
        phases=_tuple_enum(_json_loads(row["phases_json"], [])),
        request_budget=row["request_budget"],
        results_per_query=row["results_per_query"],
        stats=_json_loads(row["stats_json"], {}),
        error_message=row["error_message"],
        started_at=_parse_optional_dt(row["started_at"]),
        finished_at=_parse_optional_dt(row["finished_at"]),
        created_at=_parse_dt(row["created_at"]),
    )


def _status_log_from_row(row: sqlite3.Row) -> StatusLog:
    from_status = row["from_status"]
    return StatusLog(
        id=int(row["id"]),
        target_id=int(row["target_id"]),
        pipeline_run_id=row["pipeline_run_id"],
        from_status=TargetStatus(from_status) if from_status else None,
        to_status=TargetStatus(row["to_status"]),
        phase=PipelinePhase(row["phase"]),
        reason=row["reason"],
        error_message=row["error_message"],
        metadata=_json_loads(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]),
    )


def _rating_from_row(row: sqlite3.Row) -> RatingResult:
    return RatingResult(
        id=int(row["id"]),
        target_id=int(row["target_id"]),
        pipeline_run_id=row["pipeline_run_id"],
        rule_score=row["rule_score"],
        ai_score=row["ai_score"],
        raw_confidence=row["raw_confidence"],
        confidence=row["confidence"],
        recommended_action=RecommendedAction(row["recommended_action"]),
        rating_status=row["rating_status"],
        source_quality=row["source_quality"],
        rating_version=row["rating_version"],
        reasons=_json_loads(row["reasons_json"], []),
        risks=_json_loads(row["risks_json"], []),
        evidence=_json_loads(row["evidence_json"], []),
        input_snapshot=_json_loads(row["input_snapshot_json"], {}),
        error_type=row["error_type"],
        error_message=row["error_message"],
        created_at=_parse_dt(row["created_at"]),
    )


def _draft_from_row(row: sqlite3.Row) -> Draft:
    return Draft(
        id=int(row["id"]),
        target_id=int(row["target_id"]),
        score_id=row["score_id"],
        draft_type=row["draft_type"],
        draft_version=row["draft_version"],
        language=row["language"],
        subject=row["subject"],
        body=row["body"],
        status=DraftStatus(row["status"]),
        used_context=_json_loads(row["used_context_json"], {}),
        regenerated_from_draft_id=row["regenerated_from_draft_id"],
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )
