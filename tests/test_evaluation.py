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
    export_review_feedback_fixture,
    run_evaluation,
)
from target_radar.storage import SQLiteStore


class EvaluationTests(unittest.TestCase):
    def test_engine_eval_baseline_passes(self) -> None:
        result = run_evaluation(DEFAULT_EVALUATION_FIXTURE)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["total"], 24)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["sections"]["source_quality"]["total"], 12)
        self.assertEqual(result["sections"]["rating"]["total"], 8)
        self.assertEqual(result["sections"]["draft"]["total"], 4)

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


def _pipeline_run(search_profile_id: int, use_case_id: int):
    from target_radar.domain import PipelineRun, PipelineRunStatus

    return PipelineRun(
        search_profile_id=search_profile_id,
        use_case_id=use_case_id,
        status=PipelineRunStatus.COMPLETED,
    )


if __name__ == "__main__":
    unittest.main()
