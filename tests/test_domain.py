from __future__ import annotations

import unittest

from target_radar.domain import (
    LeadResultStatus,
    RatingResult,
    RecommendedAction,
    Target,
    TargetCandidate,
    TargetStatus,
    domain_from_url,
)


class DomainModelTests(unittest.TestCase):
    def test_target_candidate_derives_normalized_domain(self) -> None:
        candidate = TargetCandidate(
            url="https://www.Example.COM/jobs?x=1",
            source="serp:mock",
        )

        self.assertEqual(candidate.domain, "example.com")
        self.assertEqual(candidate.status, LeadResultStatus.CANDIDATE)

    def test_target_normalizes_domain(self) -> None:
        target = Target(
            domain="https://www.Example.COM/path",
            base_url="https://example.com",
            status=TargetStatus.IMPORTED,
        )

        self.assertEqual(target.domain, "example.com")
        self.assertEqual(target.status, TargetStatus.IMPORTED)

    def test_recommended_actions_match_rating_concept(self) -> None:
        self.assertEqual(
            {action.value for action in RecommendedAction},
            {"skip", "review", "draft"},
        )

    def test_rating_scores_are_range_checked(self) -> None:
        with self.assertRaises(ValueError):
            RatingResult(
                target_id=1,
                recommended_action=RecommendedAction.REVIEW,
                rule_score=101,
            )

        with self.assertRaises(ValueError):
            RatingResult(
                target_id=1,
                recommended_action=RecommendedAction.REVIEW,
                confidence=1.1,
            )

    def test_domain_from_url_rejects_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            domain_from_url("")


if __name__ == "__main__":
    unittest.main()
