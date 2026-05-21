from __future__ import annotations

import unittest

from target_radar.domain import LeadResultStatus, Profile, SearchProfile
from target_radar.engines.lead import (
    FakeSearchProvider,
    LeadEngine,
    LeadEngineConfig,
    QueryBuilder,
    SearchResult,
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


if __name__ == "__main__":
    unittest.main()
