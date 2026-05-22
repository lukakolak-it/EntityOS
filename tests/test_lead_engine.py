from __future__ import annotations

import unittest

from target_radar.domain import LeadResultStatus, Profile, SearchProfile
from target_radar.engines.lead import (
    BraveSearchProvider,
    FakeSearchProvider,
    LeadEngine,
    LeadEngineConfig,
    QueryBuilder,
    SearchResult,
    SourceImportAction,
    SourceQualityClassifier,
    SourceType,
    create_search_provider,
)
from target_radar.storage import SQLiteStore


class LeadEngineTests(unittest.TestCase):
    def test_query_builder_deduplicates_and_respects_budget(self) -> None:
        search_profile = SearchProfile(
            profile_id=1,
            name="Werkstudent IT Essen",
            roles=("Werkstudent IT", "Werkstudent IT"),
            regions=("Essen",),
            tech_keywords=("Python",),
        )

        queries = QueryBuilder().build(search_profile, limit=2)

        self.assertEqual(len(queries), 2)
        self.assertEqual(len({query.query_hash for query in queries}), 2)
        self.assertEqual(queries[0].template_set, "application_student")
        self.assertIn("Werkstudent IT Python Essen", queries[0].text)

    def test_lead_engine_filters_dedupes_and_stores_serp_results(self) -> None:
        store = SQLiteStore.open(":memory:")
        try:
            profile = store.create_profile(Profile(name="Lead Profile"))
            search_profile = store.create_search_profile(
                SearchProfile(
                    profile_id=profile.id,
                    name="Werkstudent IT Essen",
                    roles=("Werkstudent IT",),
                    regions=("Essen",),
                    tech_keywords=("Python",),
                )
            )
            provider = FakeSearchProvider(
                results_by_query={
                    "Werkstudent IT Python Essen": [
                        SearchResult(
                            url="https://alpha.example/jobs",
                            title="Alpha Jobs",
                        ),
                        SearchResult(
                            url="https://alpha.example/careers",
                            title="Alpha Careers",
                        ),
                        SearchResult(
                            url="https://blocked.example/jobs",
                            title="Blocked Jobs",
                        ),
                    ]
                }
            )
            engine = LeadEngine(
                provider=provider,
                config=LeadEngineConfig(request_budget=1, results_per_query=10),
                blocked_domains={"blocked.example"},
                store=store,
            )

            candidates = engine.discover(search_profile)
            source_query_count = store.connection.execute(
                "SELECT COUNT(*) AS count FROM source_queries"
            ).fetchone()["count"]
            serp_result_count = store.connection.execute(
                "SELECT COUNT(*) AS count FROM serp_results"
            ).fetchone()["count"]
            alpha_metadata = store.connection.execute(
                """
                SELECT metadata_json FROM serp_results
                WHERE domain = 'alpha.example'
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()["metadata_json"]
        finally:
            store.close()

        self.assertEqual(
            [candidate.status for candidate in candidates],
            [
                LeadResultStatus.CANDIDATE,
                LeadResultStatus.DUPLICATE_DOMAIN,
                LeadResultStatus.BLOCKED_SOURCE,
            ],
        )
        self.assertEqual(source_query_count, 1)
        self.assertEqual(serp_result_count, 3)
        self.assertIn("source_quality", alpha_metadata)

    def test_source_quality_blocks_job_boards_and_scores_direct_domains(self) -> None:
        classifier = SourceQualityClassifier()

        job_board = classifier.classify(
            SearchResult(
                url="https://www.studentjob.de/stellenangebote/123",
                title="Werkstudent IT Jobs in Essen",
                snippet="Jobsuche und Stellenangebote",
                metadata={"provider_rank": 1},
            )
        )
        company = classifier.classify(
            SearchResult(
                url="https://alpha.example/karriere",
                title="Alpha GmbH Karriere",
                snippet="IT Projekte und Kontakt in Essen",
                metadata={"provider_rank": 2},
            )
        )

        self.assertEqual(job_board.source_type, SourceType.JOB_BOARD)
        self.assertEqual(job_board.recommended_action, SourceImportAction.BLOCK)
        self.assertEqual(company.source_type, SourceType.COMPANY_SITE)
        self.assertEqual(company.recommended_action, SourceImportAction.IMPORT)
        self.assertGreater(company.score, job_board.score)

    def test_source_quality_classifies_official_news_and_configured_sources(self) -> None:
        classifier = SourceQualityClassifier(extra_blocked_domains=("blocked.example",))

        official = classifier.classify(
            SearchResult(
                url="https://service.bund.de/karriere",
                title="Service Bund Karriere",
            )
        )
        news = classifier.classify(
            SearchResult(
                url="https://alpha.example/news/2026/security",
                title="Alpha announces security research",
            )
        )
        blocked = classifier.classify(
            SearchResult(
                url="https://blocked.example/about",
                title="Blocked Example",
            )
        )

        self.assertEqual(official.source_type, SourceType.OFFICIAL_SITE)
        self.assertEqual(news.source_type, SourceType.NEWS)
        self.assertEqual(blocked.recommended_action, SourceImportAction.BLOCK)
        self.assertEqual(blocked.score, 0)

    def test_source_quality_knows_concept_job_boards_and_review_portals(self) -> None:
        classifier = SourceQualityClassifier()

        jooble = classifier.classify(
            SearchResult(url="https://jooble.org/jobs/python", title="Python Jobs")
        )
        kununu = classifier.classify(
            SearchResult(url="https://www.kununu.com/de/example", title="Example Bewertungen")
        )

        self.assertEqual(jooble.source_type, SourceType.JOB_BOARD)
        self.assertEqual(jooble.recommended_action, SourceImportAction.BLOCK)
        self.assertEqual(kununu.source_type, SourceType.DIRECTORY)
        self.assertNotEqual(kununu.recommended_action, SourceImportAction.BLOCK)

    def test_source_quality_uses_domain_tokens_instead_of_substrings(self) -> None:
        classifier = SourceQualityClassifier()

        tokenized = classifier.classify(
            SearchResult(url="https://werkstudent-jobs-essen.example/", title="Jobs")
        )
        substring = classifier.classify(
            SearchResult(
                url="https://projobs-consulting.example/services",
                title="Projobs Consulting",
                snippet="Werkstudent gesucht, Praktikum moeglich",
            )
        )

        self.assertEqual(tokenized.source_type, SourceType.JOB_BOARD)
        self.assertEqual(substring.source_type, SourceType.COMPANY_SITE)
        self.assertNotIn(
            "listing_or_search_page",
            [risk["type"] for risk in substring.risks],
        )

    def test_source_quality_query_and_path_signals_are_precise(self) -> None:
        classifier = SourceQualityClassifier()

        quotient = classifier.classify(
            SearchResult(
                url="https://alpha.example/about?quotient=1",
                title="Alpha About",
            )
        )
        search = classifier.classify(
            SearchResult(
                url="https://alpha.example/about?q=python",
                title="Alpha About",
            )
        )
        blocked_relevant_path = classifier.classify(
            SearchResult(
                url="https://studentjob.de/karriere",
                title="StudentJob Karriere",
            )
        )

        self.assertNotIn(
            "listing_or_search_page",
            [risk["type"] for risk in quotient.risks],
        )
        self.assertIn(
            "listing_or_search_page",
            [risk["type"] for risk in search.risks],
        )
        self.assertNotIn(
            "relevant_path",
            [signal["type"] for signal in blocked_relevant_path.signals],
        )

    def test_source_quality_uses_rank_gradient_and_deep_url_risk(self) -> None:
        classifier = SourceQualityClassifier()

        rank_one = classifier.classify(
            SearchResult(
                url="https://alpha.example/about",
                title="Alpha About",
                metadata={"provider_rank": 1},
            )
        )
        rank_seven = classifier.classify(
            SearchResult(
                url="https://beta.example/about",
                title="Beta About",
                metadata={"provider_rank": 7},
            )
        )
        deep_url = classifier.classify(
            SearchResult(
                url="https://gamma.example/karriere/jobs/software/werkstudent",
                title="Gamma Karriere",
            )
        )

        self.assertEqual(_signal_points(rank_one, "provider_rank"), 8)
        self.assertEqual(_signal_points(rank_seven, "provider_rank"), 2)
        self.assertIn("deep_url", [risk["type"] for risk in deep_url.risks])

    def test_lead_engine_prioritizes_direct_domains_before_portals(self) -> None:
        search_profile = SearchProfile(
            profile_id=1,
            name="Werkstudent IT Essen",
            roles=("Werkstudent IT",),
            regions=("Essen",),
            tech_keywords=("Python",),
        )
        provider = FakeSearchProvider(
            results_by_query={
                "Werkstudent IT Python Essen": [
                    SearchResult(
                        url="https://www.studentjob.de/stellenangebote/123",
                        title="Werkstudent IT Jobs in Essen",
                        metadata={"provider_rank": 1},
                    ),
                    SearchResult(
                        url="https://alpha.example/karriere",
                        title="Alpha GmbH Karriere",
                        metadata={"provider_rank": 2},
                    ),
                ]
            }
        )
        engine = LeadEngine(
            provider=provider,
            config=LeadEngineConfig(request_budget=1, results_per_query=2),
        )

        candidates = engine.discover(search_profile)

        self.assertEqual(candidates[0].domain, "alpha.example")
        self.assertEqual(candidates[0].status, LeadResultStatus.CANDIDATE)
        self.assertEqual(candidates[1].domain, "studentjob.de")
        self.assertEqual(candidates[1].status, LeadResultStatus.BLOCKED_SOURCE)

    def test_search_provider_factory_uses_configured_provider(self) -> None:
        from target_radar.config import SearchProviderSettings

        fake = create_search_provider(SearchProviderSettings(provider="mock"))
        brave = create_search_provider(
            SearchProviderSettings(provider="brave", brave_api_key="bv")
        )

        self.assertIsInstance(fake, FakeSearchProvider)
        self.assertIsInstance(brave, BraveSearchProvider)

    def test_search_provider_factory_requires_brave_key(self) -> None:
        from target_radar.config import SearchProviderSettings

        with self.assertRaises(ValueError):
            create_search_provider(SearchProviderSettings(provider="brave"))


def _signal_points(result, signal_type: str) -> int | None:
    for signal in result.signals:
        if signal["type"] == signal_type:
            return signal["points"]
    return None


if __name__ == "__main__":
    unittest.main()
