from __future__ import annotations

import unittest

from target_radar.domain import (
    ImportStatus,
    LeadResultStatus,
    PipelineRunStatus,
    Profile,
    SearchProfile,
    TargetCandidate,
    TargetStatus,
)
from target_radar.engines.lead import FakeLeadEngine
from target_radar.engines.lead import FakeSearchProvider, LeadEngine, LeadEngineConfig, SearchResult
from target_radar.pipeline import PipelineOrchestrator, PipelineRunRequest, TargetImporter
from target_radar.storage import SQLiteStore


class PipelineSkeletonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SQLiteStore.open(":memory:")
        profile = self.store.create_profile(Profile(name="Pipeline Profile"))
        self.search_profile = self.store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
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


if __name__ == "__main__":
    unittest.main()
