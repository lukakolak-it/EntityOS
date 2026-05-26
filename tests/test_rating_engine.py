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
from target_radar.use_cases import get_default_use_case


class RatingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")
        self.profile = self.store.create_profile(Profile(name="Rating Profile"))
        self.search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=self.profile.id,
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

    def test_ungrounded_ai_evidence_downgrades_to_review(self) -> None:
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
                    reasons=[
                        {
                            "text": "Quote is not grounded.",
                            "source_url": "https://example.com/jobs",
                            "evidence": "Dieser Satz steht nicht in der Evidence",
                        }
                    ],
                )
            )
        )

        rating = engine.rate(self.target, self.search_profile, evidence)

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertTrue(
            any(risk.get("type") == "missing_ai_evidence" for risk in rating.risks)
        )

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

    def test_ai_provider_error_becomes_partial_review_rating(self) -> None:
        evidence = [
            Evidence(
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python und Kontakt jobs@example.com",
                context_type="career",
            )
        ]
        engine = RatingEngine(ai_provider=_BrokenAIRatingProvider())

        rating = engine.rate(self.target, self.search_profile, evidence)

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertEqual(rating.error_type, "ValueError")
        self.assertIn("invalid ai json", rating.error_message)

    def test_use_case_rules_rating_can_draft_without_ai(self) -> None:
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python und Kontakt jobs@example.com",
                context_type="career",
            )
        ]

        rating = RatingEngine().rate(
            self.target,
            self.search_profile,
            evidence,
            use_case=get_default_use_case("application_student"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(rating.rating_status, "use_case_rated")
        self.assertEqual(rating.rating_version, "rules-v1+usecase-v1")
        self.assertEqual(rating.rule_score, 100)
        self.assertIsNone(rating.ai_score)
        self.assertEqual(rating.input_snapshot["use_case_id"], "application_student")
        self.assertTrue(
            any(reason.get("criterion") == "role_fit" for reason in rating.reasons)
        )

    def test_use_case_rating_requires_configured_evidence_types(self) -> None:
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/kontakt",
                text="Werkstudent IT in Essen mit Python und Kontakt jobs@example.com",
                context_type="contact",
            )
        ]

        rating = RatingEngine().rate(
            self.target,
            self.search_profile,
            evidence,
            use_case=get_default_use_case("application_student"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertTrue(
            any(risk.get("type") == "missing_required_evidence" for risk in rating.risks)
        )
        role_score = next(
            reason for reason in rating.reasons if reason.get("criterion") == "role_fit"
        )
        self.assertEqual(role_score["score"], 0)
        self.assertEqual(role_score["evidence_count"], 0)

    def test_use_case_llm_rating_uses_ai_criteria_and_source_quality(self) -> None:
        osint_profile = SearchProfile(
            profile_id=self.profile.id,
            name="Company OSINT",
            attributes={"topics": ["Solar"], "regions": ["Essen"]},
        )
        self.target.metadata["lead_metadata"] = {
            "source_quality": {
                "source_type": "company_site",
                "source_quality_score": 82,
            }
        }
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/about",
                text="Example GmbH bietet Solar Services in Essen mit Impressum und Kontakt.",
                context_type="about",
            )
        ]
        engine = RatingEngine(
            ai_provider=FakeAIRatingProvider(
                AIRatingResponse(
                    ai_score=90,
                    confidence=0.88,
                    recommended_action=RecommendedAction.DRAFT,
                    reasons=[
                        {
                            "text": "Relevante OSINT-Evidence.",
                            "source_url": "https://example.com/about",
                            "evidence": "Solar Services in Essen",
                        }
                    ],
                )
            )
        )

        rating = engine.rate(
            self.target,
            osint_profile,
            evidence,
            use_case=get_default_use_case("company_osint"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(rating.rating_status, "use_case_rated")
        self.assertEqual(rating.ai_score, 90)
        self.assertEqual(rating.input_snapshot["use_case_id"], "company_osint")
        self.assertTrue(
            any(reason.get("criterion") == "credibility" for reason in rating.reasons)
        )
        self.assertTrue(
            any(reason.get("type") == "topic_match" for reason in rating.reasons)
        )

    def test_company_osint_missing_topic_match_prevents_draft(self) -> None:
        osint_profile = SearchProfile(
            profile_id=self.profile.id,
            name="Company OSINT",
            attributes={"topics": ["Solar"], "industries": ["IT"], "regions": ["Essen"]},
        )
        self.target.metadata["lead_metadata"] = {
            "source_quality": {
                "source_type": "company_site",
                "source_quality_score": 90,
            }
        }
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/about",
                text=(
                    "Example GmbH ist ein IT-Dienstleister in Essen mit Kontakt "
                    "und belastbaren Firmeninformationen."
                ),
                context_type="about",
            )
        ]
        engine = RatingEngine(
            ai_provider=FakeAIRatingProvider(
                AIRatingResponse(
                    ai_score=92,
                    confidence=0.91,
                    recommended_action=RecommendedAction.DRAFT,
                    reasons=[
                        {
                            "text": "Gute allgemeine Firmen-Evidence.",
                            "source_url": "https://example.com/about",
                            "evidence": "IT-Dienstleister in Essen",
                        }
                    ],
                )
            )
        )

        rating = engine.rate(
            self.target,
            osint_profile,
            evidence,
            use_case=get_default_use_case("company_osint"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertLessEqual(rating.confidence, 0.4)
        self.assertTrue(
            any(risk.get("type") == "missing_topic_match" for risk in rating.risks)
        )

    def test_use_case_llm_context_is_scoped_to_evidence_types(self) -> None:
        osint_profile = SearchProfile(
            profile_id=self.profile.id,
            name="Company OSINT",
            attributes={"topics": ["Solar"], "regions": ["Essen"]},
        )
        self.target.metadata["lead_metadata"] = {
            "source_quality": {
                "source_type": "company_site",
                "source_quality_score": 82,
            }
        }
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/jobs",
                text="Werkstudent IT in Essen mit Python.",
                context_type="career",
            ),
            Evidence(
                id=2,
                target_id=self.target.id,
                source_url="https://directory.example/solar",
                text="Solar Services in Essen laut Branchenverzeichnis.",
                context_type="context_source",
                metadata={
                    "evidence_type": "context_directory",
                    "provenance": "context_source",
                    "source_type": "directory",
                    "context_source_id": 22,
                },
            ),
        ]
        provider = _RecordingAIRatingProvider()

        rating = RatingEngine(ai_provider=provider).rate(
            self.target,
            osint_profile,
            evidence,
            use_case=get_default_use_case("company_osint"),
        )

        self.assertEqual(rating.rating_status, "use_case_rated")
        self.assertGreaterEqual(len(provider.requests), 1)
        for request in provider.requests:
            self.assertIn("Solar Services", request.context_text)
            self.assertNotIn("Werkstudent IT", request.context_text)
        self.assertEqual(rating.evidence[1]["evidence_type"], "context_directory")

    def test_use_case_ungrounded_llm_reason_becomes_partial_review(self) -> None:
        osint_profile = SearchProfile(
            profile_id=self.profile.id,
            name="Company OSINT",
            attributes={"topics": ["Solar"], "regions": ["Essen"]},
        )
        self.target.metadata["lead_metadata"] = {
            "source_quality": {
                "source_type": "company_site",
                "source_quality_score": 82,
            }
        }
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/about",
                text="Example GmbH bietet Solar Services in Essen mit Impressum.",
                context_type="about",
            )
        ]
        engine = RatingEngine(
            ai_provider=FakeAIRatingProvider(
                AIRatingResponse(
                    ai_score=92,
                    confidence=0.9,
                    recommended_action=RecommendedAction.DRAFT,
                    reasons=[
                        {
                            "text": "Ungrounded reason.",
                            "source_url": "https://example.com/about",
                            "evidence": "nicht gespeicherter Satz",
                        }
                    ],
                )
            )
        )

        rating = engine.rate(
            self.target,
            osint_profile,
            evidence,
            use_case=get_default_use_case("company_osint"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertTrue(
            any(risk.get("type") == "missing_ai_evidence" for risk in rating.risks)
        )

    def test_use_case_missing_required_llm_becomes_partial_review(self) -> None:
        osint_profile = SearchProfile(
            profile_id=self.profile.id,
            name="Company OSINT",
            attributes={"topics": ["Solar"], "regions": ["Essen"]},
        )
        evidence = [
            Evidence(
                id=1,
                target_id=self.target.id,
                source_url="https://example.com/about",
                text="Example GmbH bietet Solar Services in Essen mit Kontakt.",
                context_type="about",
            )
        ]

        rating = RatingEngine().rate(
            self.target,
            osint_profile,
            evidence,
            use_case=get_default_use_case("company_osint"),
        )

        self.assertEqual(rating.recommended_action, RecommendedAction.REVIEW)
        self.assertEqual(rating.rating_status, "rating_partial")
        self.assertTrue(
            any(risk.get("type") == "missing_ai_provider" for risk in rating.risks)
        )

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


class _BrokenAIRatingProvider:
    def rate(self, request):
        raise ValueError("invalid ai json")


class _RecordingAIRatingProvider:
    def __init__(self) -> None:
        self.requests = []

    def rate(self, request):
        self.requests.append(request)
        return AIRatingResponse(
            ai_score=88,
            confidence=0.84,
            recommended_action=RecommendedAction.DRAFT,
            reasons=[
                {
                    "text": "Scoped OSINT context passt.",
                    "source_url": "https://directory.example/solar",
                    "evidence": "Solar Services in Essen",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
