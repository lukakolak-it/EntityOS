from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from target_radar.domain import (
    PipelinePhase,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
)
from target_radar.evaluation import (
    DEFAULT_EVALUATION_FIXTURE,
    export_pipeline_run_report,
    export_review_feedback_fixture,
    run_evaluation,
)
from target_radar.storage import SQLiteStore


class EvaluationTests(unittest.TestCase):
    def test_engine_eval_baseline_passes(self) -> None:
        result = run_evaluation(DEFAULT_EVALUATION_FIXTURE)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["total"], 29)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["sections"]["source_quality"]["total"], 12)
        self.assertEqual(result["sections"]["rating"]["total"], 12)
        self.assertEqual(result["sections"]["draft"]["total"], 5)

    def test_review_feedback_export_and_eval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'eval.sqlite3'}"
            output_path = Path(tmpdir) / "review-eval.json"
            store = SQLiteStore.open(database_url)
            try:
                profile = store.create_profile(Profile(name="Eval User"))
                use_case_id = store.get_use_case_id_by_slug("application_student")
                search_profile = store.create_search_profile(
                    SearchProfile(
                        profile_id=profile.id,
                        use_case_id=use_case_id,
                        name="Eval Search",
                    )
                )
                run = store.create_pipeline_run(
                    _pipeline_run(search_profile.id, use_case_id)
                )
                target = store.create_target(
                    Target(
                        domain="approved.example",
                        base_url="https://approved.example/jobs",
                        status=TargetStatus.NEEDS_REVIEW,
                    )
                )
                store.save_rating(
                    RatingResult(
                        target_id=target.id,
                        pipeline_run_id=run.id,
                        recommended_action=RecommendedAction.DRAFT,
                        rating_status="use_case_rated",
                        rule_score=80,
                        ai_score=75,
                        confidence=0.7,
                    )
                )
                store.set_target_status(
                    target.id,
                    TargetStatus.APPROVED,
                    PipelinePhase.REVIEW,
                    pipeline_run_id=run.id,
                    reason="test approval",
                )
            finally:
                store.close()

            fixture = export_review_feedback_fixture(
                database_url,
                output_path=output_path,
            )
            result = run_evaluation(output_path)

        self.assertEqual(fixture["summary"]["approved"], 1)
        self.assertEqual(fixture["review_feedback"][0]["expected_action"], "draft")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["sections"]["review_feedback"]["total"], 1)

    def test_review_feedback_conflicts_are_triaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "review-conflict.json"
            fixture_path.write_text(
                """
                {
                  "name": "review_conflict",
                  "review_feedback": [
                    {
                      "id": "local_review_blacklist",
                      "domain": "blocked.example",
                      "review_status": "blacklisted",
                      "actual_action": "draft",
                      "expected_action": "skip",
                      "rating_status": "use_case_rated",
                      "rule_score": 100,
                      "ai_score": null,
                      "confidence": 0.6,
                      "risk_types": [],
                      "evidence_count": 2,
                      "draft_count": 1,
                      "source": "fake",
                      "use_case": "application_student"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            result = run_evaluation(fixture_path)

        review = result["sections"]["review_feedback"]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(review["failed"], 1)
        self.assertEqual(review["conflict_summary"]["by_type"]["blacklist_miss"], 1)
        self.assertEqual(review["action_items"][0]["severity"], "high")
        self.assertIn("source policy", review["action_items"][0]["suggested_action"])

    def test_pipeline_run_report_exports_review_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'report.sqlite3'}"
            output_path = Path(tmpdir) / "run-report.json"
            store = SQLiteStore.open(database_url)
            try:
                profile = store.create_profile(Profile(name="Report User"))
                use_case_id = store.get_use_case_id_by_slug("company_osint")
                search_profile = store.create_search_profile(
                    SearchProfile(
                        profile_id=profile.id,
                        use_case_id=use_case_id,
                        name="Report Search",
                    )
                )
                run = store.create_pipeline_run(
                    _pipeline_run(search_profile.id, use_case_id)
                )
                target = store.create_target(
                    Target(
                        domain="review.example",
                        base_url="https://review.example",
                        status=TargetStatus.NEEDS_REVIEW,
                    )
                )
                store.save_rating(
                    RatingResult(
                        target_id=target.id,
                        pipeline_run_id=run.id,
                        recommended_action=RecommendedAction.REVIEW,
                        rating_status="rating_partial",
                        rule_score=55,
                        ai_score=45,
                        confidence=0.5,
                    )
                )
                store.set_target_status(
                    target.id,
                    TargetStatus.APPROVED,
                    PipelinePhase.REVIEW,
                    reason="previous review",
                )
                store.set_target_status(
                    target.id,
                    TargetStatus.NEEDS_REVIEW,
                    PipelinePhase.RATING,
                    pipeline_run_id=run.id,
                    reason="rerun requires review",
                )
            finally:
                store.close()

            report = export_pipeline_run_report(
                database_url,
                run_id=run.id,
                output_path=output_path,
            )
            output_exists = output_path.exists()

        self.assertEqual(report["run"]["id"], run.id)
        self.assertEqual(report["run"]["use_case_slug"], "company_osint")
        self.assertEqual(report["review_backlog"]["total"], 1)
        self.assertEqual(report["review_backlog"]["domains"], ["review.example"])
        self.assertEqual(report["targets"][0]["recommended_action"], "review")
        self.assertEqual(report["output_path"], str(output_path))
        self.assertTrue(output_exists)


def _pipeline_run(search_profile_id: int, use_case_id: int):
    from target_radar.domain import PipelineRun, PipelineRunStatus

    return PipelineRun(
        search_profile_id=search_profile_id,
        use_case_id=use_case_id,
        status=PipelineRunStatus.COMPLETED,
    )


if __name__ == "__main__":
    unittest.main()
