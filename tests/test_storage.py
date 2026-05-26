from __future__ import annotations

import sqlite3
import unittest

from target_radar.domain import (
    Draft,
    Evidence,
    ImportStatus,
    LeadResultStatus,
    PipelinePhase,
    PipelineRun,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
)
from target_radar.storage import NotFoundError, SCHEMA_VERSION, SQLiteStore, init_db, schema_status
from target_radar.use_cases import UseCaseConfig, UseCaseStatus, get_default_use_case


class SQLiteStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_schema_contains_core_tables(self) -> None:
        rows = self.store.connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        table_names = {row["name"] for row in rows}

        self.assertTrue(
            {
                "profiles",
                "search_profiles",
                "pipeline_runs",
                "targets",
                "use_cases",
                "source_queries",
                "serp_results",
                "target_status_log",
                "target_scores",
                "action_drafts",
                "evidence",
                "local_operations",
            }.issubset(table_names)
        )
        self.assertEqual(schema_status(self.store.connection)["current_version"], SCHEMA_VERSION)

    def test_default_use_cases_are_seeded(self) -> None:
        use_cases = self.store.list_use_cases(status=UseCaseStatus.TEMPLATE)
        application_id = self.store.get_use_case_id_by_slug("application_student")
        company_osint = self.store.get_use_case_by_slug("company_osint")

        self.assertEqual(
            [use_case.id for use_case in use_cases],
            ["application_student", "company_osint"],
        )
        self.assertGreater(application_id, 0)
        self.assertEqual(company_osint.draft_policy.draft_type, "research_summary")

    def test_search_profile_defaults_to_application_use_case(self) -> None:
        profile = self.store.create_profile(Profile(name="Default Use Case Profile"))

        search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Werkstudent IT Essen",
                attributes={"topics": ["Fallback Topic"]},
            )
        )

        self.assertEqual(
            search_profile.use_case_id,
            self.store.get_use_case_id_by_slug("application_student"),
        )
        self.assertEqual(
            self.store.get_search_profile(search_profile.id).use_case_id,
            search_profile.use_case_id,
        )
        self.assertEqual(
            self.store.get_search_profile(search_profile.id).attributes,
            {"topics": ["Fallback Topic"]},
        )

    def test_search_profile_can_be_updated_and_deleted(self) -> None:
        profile = self.store.create_profile(Profile(name="Editable Profile"))
        search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Editable Search",
                roles=("Werkstudent IT",),
            )
        )
        osint_use_case_id = self.store.get_use_case_id_by_slug("company_osint")

        updated = self.store.update_search_profile(
            search_profile.id,
            profile_name="Edited Profile",
            name="Edited Search",
            use_case_id=osint_use_case_id,
            roles=(),
            regions=("Essen",),
            attributes={"topics": ["Security"]},
        )

        self.assertEqual(updated.name, "Edited Search")
        self.assertEqual(updated.use_case_id, osint_use_case_id)
        self.assertEqual(updated.attributes, {"topics": ["Security"]})
        self.assertEqual(self.store.get_profile(profile.id).name, "Edited Profile")

        self.store.delete_search_profile(search_profile.id)

        with self.assertRaises(NotFoundError):
            self.store.get_search_profile(search_profile.id)

    def test_pipeline_run_stores_use_case_snapshot(self) -> None:
        profile = self.store.create_profile(Profile(name="OSINT Profile"))
        osint_use_case_id = self.store.get_use_case_id_by_slug("company_osint")
        search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Company OSINT",
                use_case_id=osint_use_case_id,
            )
        )

        run = self.store.create_pipeline_run(PipelineRun(search_profile_id=search_profile.id))

        self.assertEqual(run.use_case_id, osint_use_case_id)
        self.assertEqual(run.use_case_version, 1)
        self.assertEqual(run.use_case_snapshot["id"], "company_osint")
        self.assertEqual(
            run.use_case_snapshot["draft_policy"]["draft_type"],
            "research_summary",
        )

    def test_use_case_can_be_saved_as_local_instance(self) -> None:
        payload = get_default_use_case("company_osint").to_dict()
        payload["id"] = "custom_osint"
        payload["name"] = "Custom OSINT"
        payload["status"] = "active"
        payload["created_from_template"] = "company_osint"

        row_id = self.store.save_use_case(UseCaseConfig.from_dict(payload))
        saved = self.store.get_use_case(row_id)

        self.assertEqual(saved.id, "custom_osint")
        self.assertEqual(saved.status, UseCaseStatus.ACTIVE)
        self.assertEqual(saved.created_from_template, "company_osint")

    def test_init_db_migrates_legacy_use_case_columns(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    preset TEXT NOT NULL,
                    draft_language TEXT NOT NULL,
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE search_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    roles_json TEXT NOT NULL DEFAULT '[]',
                    regions_json TEXT NOT NULL DEFAULT '[]',
                    tech_keywords_json TEXT NOT NULL DEFAULT '[]',
                    industry_keywords_json TEXT NOT NULL DEFAULT '[]',
                    exclude_keywords_json TEXT NOT NULL DEFAULT '[]',
                    manual_query TEXT,
                    draft_language TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_profile_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phases_json TEXT NOT NULL DEFAULT '[]',
                    request_budget INTEGER,
                    results_per_query INTEGER,
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL
                );
                INSERT INTO profiles (
                    name, preset, draft_language, attributes_json, created_at
                )
                VALUES ('Legacy', 'application', 'de', '{}', '2026-01-01T00:00:00+00:00');
                INSERT INTO search_profiles (
                    profile_id, name, roles_json, regions_json, tech_keywords_json,
                    industry_keywords_json, exclude_keywords_json, created_at
                )
                VALUES (1, 'Legacy Search', '[]', '[]', '[]', '[]', '[]',
                    '2026-01-01T00:00:00+00:00');
                """
            )

            init_db(connection)

            search_columns = _column_names(connection, "search_profiles")
            run_columns = _column_names(connection, "pipeline_runs")
            schema = schema_status(connection)
            migrated_search_profile = connection.execute(
                "SELECT use_case_id FROM search_profiles WHERE id = 1"
            ).fetchone()
        finally:
            connection.close()

        self.assertIn("use_case_id", search_columns)
        self.assertIn("attributes_json", search_columns)
        self.assertIn("use_case_snapshot_json", run_columns)
        self.assertIsNotNone(migrated_search_profile["use_case_id"])
        self.assertEqual(schema["current_version"], SCHEMA_VERSION)

    def test_file_database_is_backed_up_before_schema_migration(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.sqlite3"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("CREATE TABLE legacy_table (id INTEGER PRIMARY KEY)")
                connection.commit()
                init_db(connection)
                backups = list((db_path.parent / "backups").glob("legacy.schema-v*.sqlite3"))
            finally:
                connection.close()

        self.assertEqual(len(backups), 1)

    def test_local_data_can_be_exported_and_run_data_cleared(self) -> None:
        profile = self.store.create_profile(Profile(name="Runtime Data Profile"))
        search_profile = self.store.create_search_profile(
            SearchProfile(profile_id=profile.id, name="Runtime Search")
        )
        run = self.store.create_pipeline_run(PipelineRun(search_profile_id=search_profile.id))
        target = self.store.create_target(
            Target(
                domain="runtime.example",
                base_url="https://runtime.example",
                status=TargetStatus.NEEDS_REVIEW,
            )
        )

        export = self.store.export_local_data()
        cleared = self.store.clear_run_data(export_path="exports/test.json")
        operations = self.store.list_local_operations()

        self.assertFalse(export["secrets_included"])
        self.assertEqual(export["counts"]["pipeline_runs"], 1)
        self.assertEqual(cleared["counts_before"]["targets"], 1)
        self.assertEqual(cleared["counts_after"]["targets"], 0)
        self.assertEqual(cleared["counts_after"]["pipeline_runs"], 0)
        self.assertEqual(self.store.get_search_profile(search_profile.id).id, search_profile.id)
        self.assertEqual(operations[0]["operation"], "clear_run_data")

    def test_status_log_allows_null_pipeline_run_for_api_actions(self) -> None:
        target = self.store.create_target(
            Target(
                domain="example.com",
                base_url="https://example.com",
                status=TargetStatus.IMPORTED,
            )
        )

        log = self.store.set_target_status(
            target.id,
            TargetStatus.NEEDS_REVIEW,
            PipelinePhase.RATING,
            reason="manual rerate requested",
            metadata={"trigger": "api_rerate", "endpoint": "POST /targets/1/rerate"},
        )
        current_target = self.store.get_target(target.id)
        logs = self.store.list_status_logs(target.id)

        self.assertIsNone(log.pipeline_run_id)
        self.assertEqual(log.from_status, TargetStatus.IMPORTED)
        self.assertEqual(current_target.status, TargetStatus.NEEDS_REVIEW)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].metadata["trigger"], "api_rerate")

    def test_pipeline_run_and_append_only_results_can_be_saved(self) -> None:
        profile = self.store.create_profile(Profile(name="Student Profile"))
        search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Werkstudent IT Essen",
                roles=("Werkstudent IT",),
                regions=("Essen",),
                tech_keywords=("Python",),
            )
        )
        run = self.store.create_pipeline_run(
            PipelineRun(
                search_profile_id=search_profile.id,
                request_budget=10,
                results_per_query=5,
            )
        )
        target = self.store.create_target(
            Target(
                domain="example.org",
                base_url="https://example.org",
                status=TargetStatus.RATING_PENDING,
            )
        )
        evidence = self.store.add_evidence(
            Evidence(
                target_id=target.id,
                source_url="https://example.org/jobs",
                text="Werkstudent IT im Bereich Softwareentwicklung",
                context_type="jobs",
            )
        )
        rating = self.store.save_rating(
            RatingResult(
                target_id=target.id,
                pipeline_run_id=run.id,
                rule_score=80,
                ai_score=76,
                confidence=0.82,
                recommended_action=RecommendedAction.DRAFT,
                rating_status="ai_passed",
                rating_version="rules-v1+ai-v1",
                evidence=[{"evidence_id": evidence.id}],
            )
        )
        draft = self.store.save_draft(
            Draft(
                target_id=target.id,
                score_id=rating.id,
                draft_type="application_email",
                draft_version="application-email-v1",
                language="de",
                subject="Bewerbung als Werkstudent IT",
                body="Guten Tag, ich interessiere mich fuer Ihre IT-Rolle.",
            )
        )

        self.assertIsNotNone(run.id)
        self.assertIsNotNone(evidence.id)
        self.assertIsNotNone(rating.id)
        self.assertIsNotNone(draft.id)
        self.assertEqual(rating.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(self.store.get_profile(profile.id).name, profile.name)
        self.assertEqual(
            self.store.get_search_profile(search_profile.id).name,
            search_profile.name,
        )
        self.assertEqual(
            self.store.get_latest_pipeline_run_for_target(target.id).id,
            run.id,
        )

    def test_context_sources_are_listed_from_serp_results(self) -> None:
        profile = self.store.create_profile(Profile(name="Context Profile"))
        osint_use_case_id = self.store.get_use_case_id_by_slug("company_osint")
        search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Context Search",
                use_case_id=osint_use_case_id,
            )
        )
        run = self.store.create_pipeline_run(
            PipelineRun(search_profile_id=search_profile.id)
        )
        source_query_id = self.store.create_source_query(
            provider="brave",
            query_text="IT Anbieter Essen",
            query_hash="hash-context",
            pipeline_run_id=run.id,
            query_template="{industry} Anbieter {region}",
            template_set="company_osint",
            query_score=95,
        )
        self.store.create_serp_result(
            source_query_id=source_query_id,
            url="https://www.regiomanager.de/ranking/digital/it-dienstleister/essen/",
            domain="regiomanager.de",
            title="Die groessten IT-Dienstleister in Essen",
            snippet="Ranking mit mehreren Unternehmen.",
            status=LeadResultStatus.REVIEW_SOURCE,
            import_status=ImportStatus.REVIEW_SOURCE,
            metadata={
                "source_quality": {
                    "source_type": "directory",
                    "source_quality_score": 40,
                    "recommended_import_action": "review_source",
                    "source_risks": [{"type": "context_source", "value": "directory"}],
                }
            },
        )
        target = self.store.create_target(
            Target(
                domain="alpha.example",
                base_url="https://alpha.example",
                status=TargetStatus.NEEDS_REVIEW,
            )
        )

        sources = self.store.list_context_sources(pipeline_run_id=run.id)
        assigned = self.store.assign_context_source_to_target(sources[0]["id"], target.id)
        source = self.store.get_context_source(sources[0]["id"])

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["domain"], "regiomanager.de")
        self.assertEqual(sources[0]["query_text"], "IT Anbieter Essen")
        self.assertEqual(sources[0]["use_case_slug"], "company_osint")
        self.assertEqual(
            sources[0]["metadata"]["source_quality"]["source_type"],
            "directory",
        )
        self.assertEqual(assigned["target_id"], target.id)
        self.assertEqual(source["target_id"], target.id)

    def test_review_queue_returns_actionable_targets(self) -> None:
        self.store.create_target(
            Target(
                domain="review.example",
                base_url="https://review.example",
                status=TargetStatus.NEEDS_REVIEW,
            )
        )
        self.store.create_target(
            Target(
                domain="skip.example",
                base_url="https://skip.example",
                status=TargetStatus.REJECTED,
            )
        )

        targets = self.store.list_review_targets()

        self.assertEqual([target.domain for target in targets], ["review.example"])

    def test_domains_can_be_listed_by_status_for_feedback(self) -> None:
        self.store.create_target(
            Target(
                domain="blacklisted.example",
                base_url="https://blacklisted.example",
                status=TargetStatus.BLACKLISTED,
            )
        )
        self.store.create_target(
            Target(
                domain="approved.example",
                base_url="https://approved.example",
                status=TargetStatus.APPROVED,
            )
        )

        domains = self.store.list_domains_by_status(TargetStatus.BLACKLISTED)

        self.assertEqual(domains, {"blacklisted.example"})


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


if __name__ == "__main__":
    unittest.main()
