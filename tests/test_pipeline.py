from __future__ import annotations

import unittest

from target_radar.domain import (
    ImportStatus,
    LeadResultStatus,
    PipelinePhase,
    PipelineRunStatus,
    Profile,
    RecommendedAction,
    SearchProfile,
    TargetCandidate,
    TargetStatus,
)
from target_radar.engines.draft import DraftEngine
from target_radar.engines.lead import FakeLeadEngine
from target_radar.engines.lead import FakeSearchProvider, LeadEngine, LeadEngineConfig, SearchResult
from target_radar.engines.rating import FakeAIRatingProvider, RatingEngine
from target_radar.pipeline import (
    FakeFetcher,
    FetchedPage,
    HtmlExtractor,
    PipelineOrchestrator,
    PipelineRunRequest,
    TargetImporter,
)
from target_radar.storage import SQLiteStore


class PipelineSkeletonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")
        self.profile = self.store.create_profile(Profile(name="Pipeline Profile"))
        self.search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=self.profile.id,
                name="Werkstudent IT Essen",
                roles=("Werkstudent IT",),
                regions=("Essen",),
                tech_keywords=("Python",),
            )
        )

    def tearDown(self) -> None:
        self.store.close()

    def test_pipeline_run_imports_and_moves_targets_to_review(self) -> None:
        lead_engine = FakeLeadEngine(
            candidates=[
                TargetCandidate(url="https://alpha.example/jobs", source="fake"),
                TargetCandidate(url="https://alpha.example/careers", source="fake"),
                TargetCandidate(url="https://blocked.example/jobs", source="fake"),
            ]
        )
        importer = TargetImporter(self.store, blocked_domains={"blocked.example"})
        orchestrator = PipelineOrchestrator(self.store, lead_engine, importer)

        result = orchestrator.run(
            PipelineRunRequest(
                search_profile=self.search_profile,
                request_budget=10,
                results_per_query=5,
            )
        )
        statuses = [item.status for item in result.import_results]
        review_targets = self.store.list_review_targets()
        logs = self.store.list_status_logs(review_targets[0].id)

        self.assertEqual(result.run.status, PipelineRunStatus.COMPLETED)
        self.assertEqual(result.review_target_count, 1)
        self.assertEqual(
            statuses,
            [
                ImportStatus.IMPORTED,
                ImportStatus.DUPLICATE_INPUT,
                ImportStatus.BLOCKED_SOURCE,
            ],
        )
        self.assertEqual(review_targets[0].status, TargetStatus.NEEDS_REVIEW)
        self.assertEqual(logs[0].pipeline_run_id, result.run.id)
        self.assertEqual(logs[0].metadata["import_status"], ImportStatus.IMPORTED.value)

    def test_fake_lead_engine_is_deterministic_from_search_profile(self) -> None:
        lead_engine = FakeLeadEngine()

        first = lead_engine.discover(self.search_profile)
        second = lead_engine.discover(self.search_profile)

        self.assertEqual([item.url for item in first], [item.url for item in second])
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0].status, LeadResultStatus.CANDIDATE)

    def test_orchestrator_links_lead_engine_queries_to_run(self) -> None:
        lead_engine = LeadEngine(
            provider=FakeSearchProvider(
                results_by_query={
                    "Werkstudent IT Python Essen": [
                        SearchResult(url="https://linked.example/jobs")
                    ]
                }
            ),
            config=LeadEngineConfig(request_budget=1, results_per_query=1),
            store=self.store,
        )
        orchestrator = PipelineOrchestrator(self.store, lead_engine)

        result = orchestrator.run(PipelineRunRequest(search_profile=self.search_profile))
        row = self.store.connection.execute(
            "SELECT pipeline_run_id FROM source_queries ORDER BY id DESC LIMIT 1"
        ).fetchone()

        self.assertEqual(row["pipeline_run_id"], result.run.id)

    def test_full_pipeline_fetches_extracts_rates_and_creates_draft(self) -> None:
        url = "https://alpha.example/jobs"
        lead_engine = FakeLeadEngine(
            candidates=[TargetCandidate(url=url, source="fake")]
        )
        fetcher = FakeFetcher(
            {
                url: FetchedPage(
                    url=url,
                    status_code=200,
                    body=(
                        "<html><head><title>Karriere</title></head><body>"
                        "<h1>Werkstudent IT gesucht</h1>"
                        "<p>Python Projekte in Essen mit direktem Kontakt.</p>"
                        "<p>Kontakt: jobs@alpha.example</p>"
                        "</body></html>"
                    ),
                    content_type="text/html; charset=utf-8",
                )
            }
        )
        orchestrator = PipelineOrchestrator(
            self.store,
            lead_engine,
            fetcher=fetcher,
            extractor=HtmlExtractor(),
            rating_engine=RatingEngine(ai_provider=FakeAIRatingProvider()),
            draft_engine=DraftEngine(),
            profile=self.profile,
        )

        result = orchestrator.run(
            PipelineRunRequest(
                search_profile=self.search_profile,
                phases=(
                    PipelinePhase.LEAD,
                    PipelinePhase.IMPORT,
                    PipelinePhase.FETCH,
                    PipelinePhase.EXTRACT,
                    PipelinePhase.RATING,
                    PipelinePhase.DRAFT,
                ),
            )
        )
        target = self.store.list_review_targets()[0]
        pages = self.store.list_target_pages(target.id)
        evidence = self.store.list_evidence(target.id)
        ratings = self.store.list_ratings(target.id)
        drafts = self.store.list_drafts(target.id)

        self.assertEqual(result.run.status, PipelineRunStatus.COMPLETED)
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.evidence_count, 1)
        self.assertEqual(result.rated_count, 1)
        self.assertEqual(result.drafted_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(target.status, TargetStatus.NEEDS_REVIEW)
        self.assertEqual(pages[0].page_type, "career")
        self.assertIn("Werkstudent IT", evidence[0].text)
        self.assertEqual(ratings[0].recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(drafts[0].score_id, ratings[0].id)

    def test_pipeline_fetches_relevant_same_domain_pages(self) -> None:
        base_url = "https://multi.example/"
        contact_url = "https://multi.example/kontakt"
        lead_engine = FakeLeadEngine(
            candidates=[TargetCandidate(url=base_url, source="fake")]
        )
        fetcher = FakeFetcher(
            {
                base_url: FetchedPage(
                    url=base_url,
                    status_code=200,
                    body=(
                        "<html><body>"
                        "<h1>Werkstudent IT</h1>"
                        "<p>Python Projekte</p>"
                        '<a href="/kontakt">Kontakt</a>'
                        "</body></html>"
                    ),
                ),
                contact_url: FetchedPage(
                    url=contact_url,
                    status_code=200,
                    body=(
                        "<html><body>"
                        "<h1>Kontakt</h1>"
                        "<p>Essen jobs@multi.example</p>"
                        "</body></html>"
                    ),
                ),
            }
        )
        orchestrator = PipelineOrchestrator(
            self.store,
            lead_engine,
            fetcher=fetcher,
            extractor=HtmlExtractor(),
            rating_engine=RatingEngine(ai_provider=FakeAIRatingProvider()),
            draft_engine=DraftEngine(),
            profile=self.profile,
            max_pages_per_target=2,
        )

        result = orchestrator.run(
            PipelineRunRequest(
                search_profile=self.search_profile,
                phases=(
                    PipelinePhase.LEAD,
                    PipelinePhase.IMPORT,
                    PipelinePhase.FETCH,
                    PipelinePhase.EXTRACT,
                    PipelinePhase.RATING,
                    PipelinePhase.DRAFT,
                ),
            )
        )
        target = self.store.list_review_targets()[0]
        pages = self.store.list_target_pages(target.id)

        self.assertEqual(result.fetched_count, 2)
        self.assertEqual(result.evidence_count, 2)
        self.assertEqual([page.url for page in pages], [base_url, contact_url])

    def test_target_rerate_runs_without_pipeline_run_id(self) -> None:
        url = "https://rerate.example/jobs"
        lead_engine = FakeLeadEngine(
            candidates=[TargetCandidate(url=url, source="fake")]
        )
        fetcher = FakeFetcher(
            {
                url: FetchedPage(
                    url=url,
                    status_code=200,
                    body=(
                        "<html><body>"
                        "<p>Werkstudent IT Python Essen Kontakt jobs@rerate.example</p>"
                        "</body></html>"
                    ),
                )
            }
        )
        orchestrator = PipelineOrchestrator(
            self.store,
            lead_engine,
            fetcher=fetcher,
            extractor=HtmlExtractor(),
            rating_engine=RatingEngine(ai_provider=FakeAIRatingProvider()),
            draft_engine=DraftEngine(),
            profile=self.profile,
        )
        orchestrator.run(
            PipelineRunRequest(
                search_profile=self.search_profile,
                phases=(
                    PipelinePhase.LEAD,
                    PipelinePhase.IMPORT,
                    PipelinePhase.FETCH,
                    PipelinePhase.EXTRACT,
                    PipelinePhase.RATING,
                    PipelinePhase.DRAFT,
                ),
            )
        )
        target = self.store.list_review_targets()[0]

        result = orchestrator.rerate_target(target.id, self.search_profile)
        ratings = self.store.list_ratings(target.id)

        self.assertEqual(result.rated_count, 1)
        self.assertEqual(len(ratings), 2)
        self.assertIsNone(ratings[0].pipeline_run_id)


if __name__ == "__main__":
    unittest.main()
