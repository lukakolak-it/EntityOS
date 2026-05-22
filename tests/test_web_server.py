from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from target_radar.web.server import create_server


class WebServerTests(unittest.TestCase):
    def test_local_web_server_serves_ui_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            server = create_server(database_url=database_url, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                index = _http_text(f"{base_url}/")
                run_payload = _http_json(
                    f"{base_url}/api/pipeline-runs/fake",
                    method="POST",
                    payload={},
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
                filtered_queue_payload = _http_json(
                    f"{base_url}/api/review-queue?use_case_id={application_use_case['db_id']}"
                )
                search_profiles_payload = _http_json(f"{base_url}/api/search-profiles")
                cloned_use_case_payload = _http_json(
                    f"{base_url}/api/use-cases/application_student/clone",
                    method="POST",
                    payload={"name": "Application Copy", "slug": "application_copy"},
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
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertIn("Target Radar", index)
        self.assertEqual(run_payload["run"]["status"], "completed")
        self.assertGreaterEqual(len(use_cases_payload["use_cases"]), 2)
        self.assertEqual(use_case_detail_payload["use_case"]["slug"], "application_student")
        self.assertGreaterEqual(len(filtered_queue_payload["items"]), 1)
        self.assertEqual(filtered_queue_payload["items"][0]["use_case_slug"], "application_student")
        self.assertGreaterEqual(len(search_profiles_payload["search_profiles"]), 1)
        self.assertEqual(cloned_use_case_payload["use_case"]["slug"], "application_copy")
        self.assertEqual(
            patched_profile_payload["search_profile"]["use_case_id"],
            cloned_use_case_payload["use_case"]["db_id"],
        )
        self.assertGreaterEqual(len(queue_payload["items"]), 1)
        self.assertEqual(detail_payload["target"]["id"], target_id)
        self.assertEqual(rerate_payload["reprocess"]["rated_count"], 1)
        self.assertEqual(draft_payload["reprocess"]["drafted_count"], 1)
        self.assertEqual(action_payload["status_log"]["to_status"], "approved")


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


if __name__ == "__main__":
    unittest.main()
