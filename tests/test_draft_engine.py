from __future__ import annotations

import unittest

from target_radar.domain import (
    DraftStatus,
    Evidence,
    Profile,
    RatingResult,
    RecommendedAction,
    Target,
    TargetStatus,
)
from target_radar.engines.draft import (
    DraftEngine,
    DraftSkippedError,
    DraftValidationError,
    DraftValidator,
)
from target_radar.storage import SQLiteStore


class DraftEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")
        self.profile = self.store.create_profile(Profile(name="Luka", draft_language="de"))
        self.target = self.store.create_target(
            Target(
                domain="example.com",
                base_url="https://example.com",
                status=TargetStatus.DRAFT_PENDING,
            )
        )
        self.evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python und Softwareentwicklung",
                context_type="career",
            )
        ]

    def tearDown(self) -> None:
        self.store.close()

    def test_draft_engine_creates_needs_review_draft(self) -> None:
        rating = self.store.save_rating(RatingResult(
            target_id=self.target.id,
            recommended_action=RecommendedAction.DRAFT,
            rule_score=80,
            ai_score=76,
            confidence=0.82,
            rating_status="ai_passed",
            rating_version="rules-v1+ai-v1",
        ))

        draft = DraftEngine().create_draft(
            profile=self.profile,
            target=self.target,
            rating=rating,
            evidence=self.evidence,
        )
        saved = self.store.save_draft(draft)

        self.assertEqual(saved.status, DraftStatus.NEEDS_REVIEW)
        self.assertEqual(saved.draft_version, "application-email-v1")
        self.assertEqual(saved.score_id, rating.id)
        self.assertIn("example.com", saved.subject)

    def test_non_draft_rating_skips_generation(self) -> None:
        rating = RatingResult(
            target_id=self.target.id,
            recommended_action=RecommendedAction.REVIEW,
            rating_status="rating_partial",
        )

        with self.assertRaises(DraftSkippedError):
            DraftEngine().create_draft(
                profile=self.profile,
                target=self.target,
                rating=rating,
                evidence=self.evidence,
            )

    def test_validator_requires_evidence_and_blocks_banned_phrases(self) -> None:
        validator = DraftValidator()

        result = validator.validate(
            subject="Hallo",
            body="Wie besprochen sende ich automatisch versendet diesen Text.",
            evidence_snippets=(),
        )

        self.assertFalse(result.valid)
        self.assertIn("at least one evidence snippet is required", result.errors)
        self.assertTrue(any(error.startswith("banned phrase") for error in result.errors))

    def test_missing_evidence_raises_validation_error(self) -> None:
        rating = RatingResult(
            target_id=self.target.id,
            recommended_action=RecommendedAction.DRAFT,
            rating_status="ai_passed",
        )

        with self.assertRaises(DraftValidationError):
            DraftEngine().create_draft(
                profile=self.profile,
                target=self.target,
                rating=rating,
                evidence=[],
            )


if __name__ == "__main__":
    unittest.main()
