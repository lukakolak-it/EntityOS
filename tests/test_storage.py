from __future__ import annotations

import unittest

from target_radar.domain import (
    Draft,
    Evidence,
    PipelinePhase,
    PipelineRun,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
)
from target_radar.storage import SQLiteStore


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
                "source_queries",
                "serp_results",
                "target_status_log",
                "target_scores",
                "action_drafts",
                "evidence",
            }.issubset(table_names)
        )

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


if __name__ == "__main__":
    unittest.main()
