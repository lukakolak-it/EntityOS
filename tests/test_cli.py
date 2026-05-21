from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from target_radar.cli import main


class CliTests(unittest.TestCase):
    def test_init_run_and_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"

            init_payload = _run_cli("--database-url", database_url, "init-db")
            run_payload = _run_cli(
                "--database-url",
                database_url,
                "run-fake",
                "--role",
                "Werkstudent IT",
                "--region",
                "Essen",
                "--tech",
                "Python",
            )
            review_payload = _run_cli(
                "--database-url",
                database_url,
                "review-queue",
            )

        self.assertEqual(init_payload["status"], "initialized")
        self.assertEqual(run_payload["status"], "completed")
        self.assertGreaterEqual(run_payload["review_target_count"], 1)
        self.assertGreaterEqual(len(review_payload["targets"]), 1)


def _run_cli(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(args)
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}")
    return json.loads(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
