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
                queue_payload = _http_json(f"{base_url}/api/review-queue")
                target_id = queue_payload["items"][0]["id"]
                detail_payload = _http_json(f"{base_url}/api/targets/{target_id}")
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
        self.assertGreaterEqual(len(queue_payload["items"]), 1)
        self.assertEqual(detail_payload["target"]["id"], target_id)
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
