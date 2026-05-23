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
from target_radar.engines.draft.context import DraftContextBuilder
from target_radar.storage import SQLiteStore
from target_radar.use_cases import get_default_use_case


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

    def test_draft_policy_creates_research_summary(self) -> None:
        rating = self.store.save_rating(RatingResult(
            target_id=self.target.id,
            recommended_action=RecommendedAction.DRAFT,
            rule_score=82,
            ai_score=90,
            confidence=0.88,
            rating_status="use_case_rated",
            rating_version="rules-v1+usecase-v1",
            risks=[{"type": "source_quality", "value": "check manually"}],
        ))

        draft = DraftEngine().create_draft(
            profile=self.profile,
            target=self.target,
            rating=rating,
            evidence=self.evidence,
            draft_policy=get_default_use_case("company_osint").draft_policy,
        )

        self.assertEqual(draft.draft_type, "research_summary")
        self.assertEqual(draft.draft_version, "research-summary-v1")
        self.assertIn("Research Summary: example.com", draft.subject)
        self.assertIn("Key Findings", draft.body)
        self.assertIn("E1:", draft.body)
        self.assertIn("Risks Or Uncertainties", draft.body)
        self.assertEqual(draft.used_context["draft_policy"]["draft_type"], "research_summary")

    def test_research_summary_context_is_budgeted_and_does_not_exceed_policy(self) -> None:
        rating = self.store.save_rating(RatingResult(
            target_id=self.target.id,
            recommended_action=RecommendedAction.DRAFT,
            rule_score=83,
            ai_score=72,
            confidence=0.68,
            rating_status="use_case_rated",
            rating_version="rules-v1+usecase-v1",
        ))
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/contact",
                text="Kontakt und Solar Services Essen. " * 220,
                context_type="contact",
                priority=80,
                metadata={"evidence_type": "target_contact"},
            ),
            Evidence(
                id=2,
                target_id=self.target.id,
                source_url="https://directory.example/company",
                text="Branchenverzeichnis bestaetigt Solar Services in Essen. " * 160,
                context_type="context_source",
                priority=60,
                metadata={
                    "evidence_type": "context_directory",
                    "provenance": "context_source",
                },
            ),
        ]

        draft = DraftEngine().create_draft(
            profile=self.profile,
            target=self.target,
            rating=rating,
            evidence=evidence,
            draft_policy=get_default_use_case("company_osint").draft_policy,
        )

        self.assertLessEqual(len(draft.body), 2500)
        self.assertEqual(draft.draft_type, "research_summary")
        self.assertTrue(draft.used_context["evidence_truncated"])
        self.assertLessEqual(draft.used_context["evidence_total_chars"], 1250)
        self.assertEqual(draft.used_context["evidence"][0]["ref"], "E1")
        self.assertIn("context_directory", draft.body)
        self.assertIn("https://directory.example/company", draft.body)

    def test_validator_requires_research_summary_sources_and_refs(self) -> None:
        validator = DraftValidator()

        result = validator.validate(
            subject="Research Summary",
            body="Title\nResearch Summary\n\nEvidence\n- E1: https://example.com",
            evidence_snippets=("Beleg",),
            required_source_urls=("https://example.com", "https://missing.example"),
            required_evidence_refs=("E1", "E2"),
        )

        self.assertFalse(result.valid)
        self.assertIn("missing evidence source: https://missing.example", result.errors)
        self.assertIn("missing evidence reference: E2", result.errors)

    def test_draft_context_prioritizes_typed_context_sources(self) -> None:
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/page",
                text="Allgemeiner Seitentext.",
                context_type="page",
                priority=10,
                metadata={"evidence_type": "target_page"},
            ),
            Evidence(
                id=2,
                target_id=self.target.id,
                source_url="https://directory.example/company",
                text="Kontextquelle mit Branchenhinweis.",
                context_type="context_source",
                priority=60,
                metadata={"evidence_type": "context_directory"},
            ),
        ]

        context = DraftContextBuilder().build(
            profile=self.profile,
            target=self.target,
            rating=RatingResult(
                target_id=self.target.id,
                recommended_action=RecommendedAction.DRAFT,
            ),
            evidence=evidence,
        )

        self.assertEqual(context.evidence_items[0].evidence_type, "context_directory")
        self.assertEqual(
            context.evidence_items[0].source_url,
            "https://directory.example/company",
        )


if __name__ == "__main__":
    unittest.main()
