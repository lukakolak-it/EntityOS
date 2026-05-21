from __future__ import annotations

import unittest

from target_radar.domain import (
    Evidence,
    Profile,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
)
from target_radar.engines.rating import (
    AIRatingResponse,
    FakeAIRatingProvider,
    RatingEngine,
    RuleRater,
)
from target_radar.storage import SQLiteStore


class RatingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")
        profile = self.store.create_profile(Profile(name="Rating Profile"))
        self.search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Werkstudent IT Essen",
                roles=("Werkstudent IT",),
                regions=("Essen",),
                tech_keywords=("Python",),
                exclude_keywords=("Zeitarbeit",),
            )
        )
        self.target = self.store.create_target(
            Target(
                domain="example.com",
                base_url="https://example.com",
                status=TargetStatus.RATING_PENDING,
            )
        )

    def tearDown(self) -> None:
        self.store.close()

    def test_rule_rating_scores_matching_evidence(self) -> None:
        evidence = [
            Evidence(
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python und Kontakt jobs@example.com",
                context_type="career",
            )
        ]

        result = RuleRater().rate(self.target, self.search_profile, evidence)

        self.assertGreaterEqual(result.score, 70)
        self.assertFalse(result.hard_stop)
        self.assertTrue(result.reasons)

    def test_rating_engine_drafts_when_ai_score_and_confidence_pass(self) -> None:
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python und Kontakt jobs@example.com",
                context_type="career",
            )
        ]
        engine = RatingEngine(
            ai_provider=FakeAIRatingProvider(
                AIRatingResponse(
                    ai_score=76,
                    confidence=0.82,
                    recommended_action=RecommendedAction.DRAFT,
                    reasons=[
                        {
                            "text": "Passender Werkstudenten-Kontext.",
                            "source_url": "https://example.com/jobs",
                            "evidence": "Werkstudent IT in Essen",
                        }
                    ],
                )
            )
        )

        rating = engine.rate(self.target, self.search_profile, evidence)

        self.assertEqual(rating.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(rating.rating_status, "ai_passed")
        self.assertEqual(rating.rating_version, "rules-v1+ai-v1")

    def test_missing_ai_evidence_downgrades_to_review(self) -> None:
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python",
                context_type="career",
            )
        ]
        engine = RatingEngine(
            ai_provider=FakeAIRatingProvider(
                AIRatingResponse(
                    ai_score=90,
                    confidence=0.9,
                    recommended_action=RecommendedAction.DRAFT,
                    reasons=[{"text": "Strong fit without source."}],
                )
            )
        )

        rating = engine.rate(self.target, self.search_profile, evidence)

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertLessEqual(rating.confidence, 0.4)

    def test_hard_stopper_forces_skip(self) -> None:
        evidence = [
            Evidence(
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python bei Zeitarbeit",
                context_type="career",
            )
        ]
        engine = RatingEngine(ai_provider=FakeAIRatingProvider())

        rating = engine.rate(self.target, self.search_profile, evidence)

        self.assertEqual(rating.recommended_action, RecommendedAction.SKIP)
        self.assertEqual(rating.rating_status, "rule_skipped")

    def test_evidence_can_be_loaded_for_rating(self) -> None:
        saved = self.store.add_evidence(
            Evidence(
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python",
                context_type="career",
                priority=10,
            )
        )

        loaded = self.store.list_evidence(self.target.id)

        self.assertEqual(loaded[0].id, saved.id)
        self.assertEqual(loaded[0].context_type, "career")


if __name__ == "__main__":
    unittest.main()
