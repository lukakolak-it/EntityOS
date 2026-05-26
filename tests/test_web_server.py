from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from target_radar.domain import (
    ImportStatus,
    LeadResultStatus,
    PipelinePhase,
    PipelineRun,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
)
from target_radar.storage import SQLiteStore
from target_radar.web.server import create_server


class WebServerTests(unittest.TestCase):
    def test_review_queue_filters_bulk_action_and_undo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            target_id, run_id, use_case_id = _seed_review_queue_item(database_url)
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SEARCH_PROVIDER=mock\n", encoding="utf-8")
            server = create_server(
                database_url=database_url,
                host="127.0.0.1",
                port=0,
                env_file=env_file,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                filtered_payload = _http_json(
                    f"{base_url}/api/review-queue"
                    f"?use_case_id={use_case_id}&pipeline_run_id={run_id}"
                    "&status=needs_review&recommended_action=review"
                    "&source_type=company_site&risk_type=missing_ai_evidence"
                )
                bulk_payload = _http_json(
                    f"{base_url}/api/review-queue/bulk-action",
                    method="POST",
                    payload={"target_ids": [target_id], "action": "reject"},
                )
                rejected_detail = _http_json(f"{base_url}/api/targets/{target_id}")
                undo_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/undo-review",
                    method="POST",
                    payload={},
                )
                restored_detail = _http_json(f"{base_url}/api/targets/{target_id}")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual([item["id"] for item in filtered_payload["items"]], [target_id])
        self.assertEqual(filtered_payload["items"][0]["source_type"], "company_site")
        self.assertEqual(bulk_payload["updated_count"], 1)
        self.assertEqual(bulk_payload["status_logs"][0]["to_status"], "rejected")
        self.assertEqual(
            bulk_payload["status_logs"][0]["metadata"]["trigger"],
            "ui_bulk_action",
        )
        self.assertEqual(rejected_detail["target"]["status"], "rejected")
        self.assertEqual(undo_payload["status_log"]["to_status"], "needs_review")
        self.assertEqual(restored_detail["target"]["status"], "needs_review")

    def test_context_source_can_be_attached_as_target_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            target_id, context_source_id = _seed_context_source(database_url)
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SEARCH_PROVIDER=mock\n", encoding="utf-8")
            server = create_server(
                database_url=database_url,
                host="127.0.0.1",
                port=0,
                env_file=env_file,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                attached_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/attach-context-source",
                    method="POST",
                    payload={"context_source_id": context_source_id},
                )
                duplicate_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/attach-context-source",
                    method="POST",
                    payload={"context_source_id": context_source_id},
                )
                detail_payload = _http_json(f"{base_url}/api/targets/{target_id}")
                sources_payload = _http_json(f"{base_url}/api/context-sources")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(attached_payload["evidence"]["context_type"], "context_source")
        self.assertEqual(
            attached_payload["evidence"]["metadata"]["evidence_type"],
            "context_directory",
        )
        self.assertEqual(
            attached_payload["evidence"]["metadata"]["context_source_id"],
            context_source_id,
        )
        self.assertEqual(duplicate_payload["evidence"]["id"], attached_payload["evidence"]["id"])
        self.assertEqual(len(detail_payload["evidence"]), 1)
        self.assertEqual(sources_payload["context_sources"][0]["target_id"], target_id)

    def test_local_web_server_serves_ui_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SEARCH_PROVIDER=mock\n", encoding="utf-8")
            server = create_server(
                database_url=database_url,
                host="127.0.0.1",
                port=0,
                env_file=env_file,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                index = _http_text(f"{base_url}/")
                provider_status_payload = _http_json(f"{base_url}/api/provider-status")
                preflight_payload = _http_json(f"{base_url}/api/preflight")
                local_settings_payload = _http_json(f"{base_url}/api/local-settings")
                context_sources_payload = _http_json(f"{base_url}/api/context-sources")
                saved_local_settings_payload = _http_json(
                    f"{base_url}/api/local-settings",
                    method="POST",
                    payload={
                        "values": {
                            "SEARCH_PROVIDER": "brave",
                            "BRAVE_API_KEY": "test-secret-value",
                            "LOCAL_AI_BASE_URL": "http://127.0.0.1:11434",
                        }
                    },
                )
                run_payload = _http_json(
                    f"{base_url}/api/pipeline-runs/fake",
                    method="POST",
                    payload={},
                )
                ui_run_payload = _http_json(
                    f"{base_url}/api/pipeline-runs",
                    method="POST",
                    payload={
                        "provider_mode": "fake",
                        "llm_mode": "off",
                        "fetch_mode": "fake",
                        "phase_mode": "full",
                        "draft_enabled": False,
                        "request_budget": 1,
                        "results_per_query": 1,
                        "max_pages_per_target": 1,
                    },
                )
                use_cases_payload = _http_json(f"{base_url}/api/use-cases")
                application_use_case = next(
                    item
                    for item in use_cases_payload["use_cases"]
                    if item["slug"] == "application_student"
                )
                use_case_detail_payload = _http_json(
                    f"{base_url}/api/use-cases/application_student"
                )
                use_case_export_payload = _http_json(
                    f"{base_url}/api/use-cases/application_student/export"
                )
                built_in_patch_status = _http_status(
                    f"{base_url}/api/use-cases/application_student",
                    method="PATCH",
                    payload={"config": use_case_export_payload["use_case"]},
                )
                built_in_overwrite_status = _http_status(
                    f"{base_url}/api/use-cases/import",
                    method="POST",
                    payload={
                        "conflict": "overwrite",
                        "use_case": use_case_export_payload["use_case"],
                    },
                )
                filtered_queue_payload = _http_json(
                    f"{base_url}/api/review-queue?use_case_id={application_use_case['db_id']}"
                )
                search_profiles_payload = _http_json(f"{base_url}/api/search-profiles")
                created_profile_payload = _http_json(
                    f"{base_url}/api/search-profiles",
                    method="POST",
                    payload={
                        "profile_name": "OSINT Profile",
                        "search_name": "OSINT Search",
                        "use_case_id": 2,
                        "attributes": {
                            "topics": ["Solar Services"],
                            "industries": ["IT"],
                            "regions": ["Essen"],
                        },
                        "regions": ["Essen"],
                    },
                )
                preview_payload = _http_json(
                    f"{base_url}/api/run-preview",
                    method="POST",
                    payload={
                        "use_case_id": 2,
                        "request_budget": 2,
                        "results_per_query": 1,
                        "attributes": {
                            "topics": ["Solar Services"],
                            "industries": ["IT"],
                            "regions": ["Essen"],
                        },
                    },
                )
                patched_full_profile_payload = _http_json(
                    f"{base_url}/api/search-profiles/{created_profile_payload['search_profile']['id']}",
                    method="PATCH",
                    payload={
                        "profile_name": "OSINT Edited",
                        "name": "OSINT Search Edited",
                        "use_case_id": 2,
                        "attributes": {
                            "topics": ["Security"],
                            "industries": ["IT"],
                            "regions": ["Essen"],
                        },
                    },
                )
                domain_policy_payload = _http_json(
                    f"{base_url}/api/domain-policies/blacklist",
                    method="POST",
                    payload={"domain": "blocked.example"},
                )
                domain_policies_payload = _http_json(f"{base_url}/api/domain-policies")
                unblocked_domain_payload = _http_json(
                    f"{base_url}/api/domain-policies/unblock",
                    method="POST",
                    payload={"domain": "blocked.example"},
                )
                cloned_use_case_payload = _http_json(
                    f"{base_url}/api/use-cases/application_student/clone",
                    method="POST",
                    payload={"name": "Application Copy", "slug": "application_copy"},
                )
                edited_config = cloned_use_case_payload["use_case"]
                edited_config["name"] = "Application Edited"
                edited_config["query_policy"]["templates"].append("{role} remote {region}")
                updated_use_case_payload = _http_json(
                    f"{base_url}/api/use-cases/application_copy",
                    method="PATCH",
                    payload={"config": edited_config},
                )
                imported_use_case_payload = _http_json(
                    f"{base_url}/api/use-cases/import",
                    method="POST",
                    payload={
                        "conflict": "rename",
                        "use_case": use_case_export_payload["use_case"],
                    },
                )
                import_conflict_status = _http_status(
                    f"{base_url}/api/use-cases/import",
                    method="POST",
                    payload={
                        "conflict": "reject",
                        "use_case": use_case_export_payload["use_case"],
                    },
                )
                patched_profile_payload = _http_json(
                    f"{base_url}/api/search-profiles/{search_profiles_payload['search_profiles'][0]['id']}",
                    method="PATCH",
                    payload={"use_case_id": cloned_use_case_payload["use_case"]["db_id"]},
                )
                queue_payload = _http_json(f"{base_url}/api/review-queue")
                target_id = queue_payload["items"][0]["id"]
                detail_payload = _http_json(f"{base_url}/api/targets/{target_id}")
                rerate_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/rerate",
                    method="POST",
                    payload={},
                )
                draft_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/regenerate-draft",
                    method="POST",
                    payload={},
                )
                action_payload = _http_json(
                    f"{base_url}/api/targets/{target_id}/approve",
                    method="POST",
                    payload={},
                )
                local_data_export_payload = _http_json(
                    f"{base_url}/api/local-data/export",
                    method="POST",
                    payload={},
                )
                local_data_clear_payload = _http_json(
                    f"{base_url}/api/local-data/clear-run-data",
                    method="POST",
                    payload={},
                )
                queue_after_clear_payload = _http_json(f"{base_url}/api/review-queue")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertIn("Target Radar", index)
        self.assertIn("#review", index)
        self.assertIn("#use-cases", index)
        self.assertIn("#secrets", index)
        self.assertIn("Run konfigurieren", index)
        self.assertIn("Provider Status", index)
        self.assertIn("Preflight", index)
        self.assertIn("Local Data", index)
        self.assertIn("Context Sources", index)
        self.assertIn("#dashboard", index)
        self.assertIn("Dashboard", index)
        self.assertIn("Reject selected", index)
        self.assertTrue(provider_status_payload["search"]["mock_ready"])
        self.assertIn("models", provider_status_payload["llm"]["light"])
        self.assertNotIn("api_key", json.dumps(provider_status_payload).lower())
        self.assertIn("checks", preflight_payload)
        self.assertEqual(preflight_payload["database"]["migration_status"], "current")
        self.assertNotIn("test-secret-value", json.dumps(preflight_payload))
        self.assertGreaterEqual(len(local_settings_payload["groups"]), 1)
        self.assertEqual(
            _settings_field(saved_local_settings_payload, "SEARCH_PROVIDER")["value"],
            "brave",
        )
        saved_brave_field = _settings_field(saved_local_settings_payload, "BRAVE_API_KEY")
        self.assertTrue(saved_brave_field["configured"])
        self.assertEqual(saved_brave_field["value"], "")
        self.assertNotIn("test-secret-value", json.dumps(saved_local_settings_payload))
        self.assertEqual(context_sources_payload["context_sources"], [])
        self.assertEqual(run_payload["run"]["status"], "completed")
        self.assertEqual(ui_run_payload["provider_mode"], "fake")
        self.assertEqual(ui_run_payload["llm_mode"], "off")
        self.assertEqual(ui_run_payload["fetch_mode"], "fake")
        self.assertEqual(ui_run_payload["phase_mode"], "full")
        self.assertEqual(ui_run_payload["search_provider"], "mock")
        self.assertGreaterEqual(len(use_cases_payload["use_cases"]), 2)
        self.assertEqual(use_case_detail_payload["use_case"]["slug"], "application_student")
        self.assertTrue(use_case_detail_payload["use_case"]["is_builtin"])
        self.assertFalse(use_case_detail_payload["use_case"]["is_editable"])
        self.assertEqual(use_case_export_payload["format"], "target-radar-use-case-v1")
        self.assertNotIn("db_id", use_case_export_payload["use_case"])
        self.assertEqual(built_in_patch_status, 400)
        self.assertEqual(built_in_overwrite_status, 400)
        self.assertGreaterEqual(len(filtered_queue_payload["items"]), 1)
        self.assertEqual(filtered_queue_payload["items"][0]["use_case_slug"], "application_student")
        self.assertGreaterEqual(len(search_profiles_payload["search_profiles"]), 1)
        self.assertEqual(created_profile_payload["search_profile"]["use_case_id"], 2)
        self.assertEqual(created_profile_payload["search_profile"]["roles"], [])
        self.assertTrue(preview_payload["valid"])
        self.assertGreaterEqual(len(preview_payload["queries"]), 1)
        self.assertGreaterEqual(len(preview_payload["query_packs"]), 1)
        self.assertEqual(preview_payload["queries"][0]["query_pack"], "company_core")
        self.assertEqual(
            patched_full_profile_payload["search_profile"]["attributes"]["topics"],
            ["Security"],
        )
        self.assertEqual(domain_policy_payload["target"]["status"], "blacklisted")
        self.assertEqual(domain_policies_payload["counts"]["blacklisted"], 1)
        self.assertEqual(unblocked_domain_payload["target"]["status"], "rejected")
        self.assertEqual(cloned_use_case_payload["use_case"]["slug"], "application_copy")
        self.assertFalse(cloned_use_case_payload["use_case"]["is_builtin"])
        self.assertTrue(cloned_use_case_payload["use_case"]["is_editable"])
        self.assertEqual(updated_use_case_payload["use_case"]["name"], "Application Edited")
        self.assertIn(
            "{role} remote {region}",
            updated_use_case_payload["use_case"]["query_policy"]["templates"],
        )
        self.assertEqual(imported_use_case_payload["import_status"], "renamed")
        self.assertEqual(
            imported_use_case_payload["use_case"]["created_from_template"],
            "application_student",
        )
        self.assertEqual(import_conflict_status, 409)
        self.assertEqual(
            patched_profile_payload["search_profile"]["use_case_id"],
            cloned_use_case_payload["use_case"]["db_id"],
        )
        self.assertGreaterEqual(len(queue_payload["items"]), 1)
        self.assertEqual(detail_payload["target"]["id"], target_id)
        self.assertEqual(rerate_payload["reprocess"]["rated_count"], 1)
        self.assertEqual(draft_payload["reprocess"]["drafted_count"], 1)
        self.assertEqual(action_payload["status_log"]["to_status"], "approved")
        self.assertFalse(local_data_export_payload["secrets_included"])
        self.assertGreaterEqual(local_data_export_payload["counts"]["pipeline_runs"], 1)
        self.assertFalse(local_data_clear_payload["export"]["secrets_included"])
        self.assertGreaterEqual(local_data_clear_payload["clear"]["counts_before"]["targets"], 1)
        self.assertEqual(queue_after_clear_payload["items"], [])


def _seed_review_queue_item(database_url: str) -> tuple[int, int, int]:
    store = SQLiteStore.open(database_url)
    try:
        profile = store.create_profile(Profile(name="Queue API Profile"))
        use_case_id = store.get_use_case_id_by_slug("application_student")
        search_profile = store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Queue API Search",
                use_case_id=use_case_id,
            )
        )
        run = store.create_pipeline_run(PipelineRun(search_profile_id=search_profile.id))
        target = store.create_target(
            Target(
                domain="queue-api.example",
                base_url="https://queue-api.example/jobs/python",
                status=TargetStatus.NEEDS_REVIEW,
                metadata={
                    "lead_metadata": {
                        "source_quality": {
                            "source_type": "company_site",
                            "source_quality_score": 82,
                            "source_risks": [
                                {"type": "deep_url", "value": 3},
                            ],
                        }
                    }
                },
            )
        )
        store.set_target_status(
            target.id,
            TargetStatus.NEEDS_REVIEW,
            PipelinePhase.REVIEW,
            pipeline_run_id=run.id,
            reason="seed queue item",
        )
        store.save_rating(
            RatingResult(
                target_id=target.id,
                pipeline_run_id=run.id,
                recommended_action=RecommendedAction.REVIEW,
                rule_score=75,
                confidence=0.82,
                rating_status="use_case_rated",
                reasons=[{"type": "role", "value": "Python"}],
                risks=[{"type": "missing_ai_evidence", "value": "source"}],
            )
        )
        return target.id, run.id, use_case_id
    finally:
        store.close()


def _seed_context_source(database_url: str) -> tuple[int, int]:
    store = SQLiteStore.open(database_url)
    try:
        profile = store.create_profile(Profile(name="Context API Profile"))
        use_case_id = store.get_use_case_id_by_slug("company_osint")
        search_profile = store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name="Context API Search",
                use_case_id=use_case_id,
            )
        )
        run = store.create_pipeline_run(PipelineRun(search_profile_id=search_profile.id))
        source_query_id = store.create_source_query(
            provider="brave",
            query_text="Solar Services Unternehmen Essen",
            query_hash="hash-context-api",
            pipeline_run_id=run.id,
            query_template="{topic} Unternehmen {region}",
            template_set="company_osint",
            query_score=110,
        )
        context_source_id = store.create_serp_result(
            source_query_id=source_query_id,
            url="https://www.regiomanager.de/ranking/solar/essen/",
            domain="regiomanager.de",
            title="Solar Dienstleister in Essen",
            snippet="Ranking mit mehreren lokalen Unternehmen.",
            status=LeadResultStatus.REVIEW_SOURCE,
            import_status=ImportStatus.REVIEW_SOURCE,
            metadata={
                "source_quality": {
                    "source_type": "directory",
                    "source_quality_score": 40,
                    "recommended_import_action": "review_source",
                }
            },
        )
        target = store.create_target(
            Target(
                domain="solar-alpha.example",
                base_url="https://solar-alpha.example",
                status=TargetStatus.NEEDS_REVIEW,
            )
        )
        return target.id, context_source_id
    finally:
        store.close()


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


def _http_status(
    url: str,
    *,
    method: str,
    payload: dict[str, object],
) -> int:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        return code


def _settings_field(payload: dict[str, object], key: str) -> dict[str, object]:
    for group in payload["groups"]:
        for field in group["fields"]:
            if field["key"] == key:
                return field
    raise AssertionError(f"settings field not found: {key}")


if __name__ == "__main__":
    unittest.main()
