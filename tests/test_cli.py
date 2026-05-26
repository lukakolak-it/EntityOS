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

    def test_diagnose_and_privacy_check(self) -> None:
        with tempfile.TemporaryDirectory() as db_tmpdir, tempfile.TemporaryDirectory() as privacy_tmpdir:
            root = Path(privacy_tmpdir)
            database_url = f"sqlite:///{Path(db_tmpdir) / 'target-radar.sqlite3'}"
            _run_cli("--database-url", database_url, "init-db")
            diagnose_payload = _run_cli("--database-url", database_url, "diagnose")

            (root / ".gitignore").write_text(
                "\n".join(
                    [
                        ".env",
                        ".env.*",
                        "data/*",
                        "logs/",
                        "*.sqlite",
                        "*.sqlite3",
                        "*.db",
                        "*.log",
                        "exports/",
                        "profiles.local.*",
                    ]
                ),
                encoding="utf-8",
            )
            (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            privacy_payload = _run_cli("privacy-check", "--root", str(root))

        self.assertEqual(diagnose_payload["database"]["status"], "ok")
        self.assertEqual(diagnose_payload["database"]["url"], "[REDACTED]")
        self.assertTrue(privacy_payload["ok"])

    def test_evaluate_command_runs_engine_baseline(self) -> None:
        payload = _run_cli("evaluate")

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["total"], 31)
        self.assertEqual(payload["sections"]["source_quality"]["failed"], 0)
        self.assertEqual(payload["sections"]["rating"]["failed"], 0)
        self.assertEqual(payload["sections"]["draft"]["failed"], 0)

    def test_export_review_eval_command_writes_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            output_path = Path(tmpdir) / "review-eval.json"
            _run_cli("--database-url", database_url, "init-db")
            payload = _run_cli(
                "--database-url",
                database_url,
                "export-review-eval",
                "--output",
                str(output_path),
            )
            output_exists = output_path.exists()

        self.assertEqual(payload["summary"]["total"], 0)
        self.assertEqual(payload["output_path"], str(output_path))
        self.assertTrue(output_exists)

    def test_export_run_report_command_writes_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            output_path = Path(tmpdir) / "run-report.json"
            _run_cli("--database-url", database_url, "init-db")
            run_payload = _run_cli(
                "--database-url",
                database_url,
                "run-fake",
                "--request-budget",
                "1",
                "--results-per-query",
                "1",
            )
            payload = _run_cli(
                "--database-url",
                database_url,
                "export-run-report",
                "--run-id",
                str(run_payload["run_id"]),
                "--output",
                str(output_path),
            )
            output_exists = output_path.exists()

        self.assertEqual(payload["run"]["id"], run_payload["run_id"])
        self.assertEqual(payload["review_backlog"]["total"], 1)
        self.assertEqual(payload["output_path"], str(output_path))
        self.assertTrue(output_exists)


def _run_cli(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(args)
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}")
    return json.loads(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
