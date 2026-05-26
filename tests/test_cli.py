from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import target_radar.cli as cli
from target_radar.config import load_app_config
from target_radar.cli import main
from target_radar.engines.lead import LeadEngineConfig


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
        self.assertIn("checks", diagnose_payload)
        self.assertEqual(diagnose_payload["database"]["migration_status"], "current")
        self.assertGreaterEqual(diagnose_payload["database"]["schema_version"], 1)
        self.assertIn("providers", diagnose_payload)
        self.assertTrue(privacy_payload["ok"])

    def test_evaluate_command_runs_engine_baseline(self) -> None:
        payload = _run_cli("evaluate")

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["total"], 51)
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

    def test_run_configured_preserves_source_block_threshold(self) -> None:
        captured = {}
        config = load_app_config(
            env_file=None,
            environ={
                "TARGET_RADAR_SOURCE_BLOCK_THRESHOLD": "72",
                "SEARCH_PROVIDER": "mock",
                "LLM_HEAVY_PROVIDER": "fake",
                "LLM_LIGHT_PROVIDER": "fake",
            },
        )
        fake_lead_engine = SimpleNamespace(
            provider=SimpleNamespace(name="mock"),
            config=LeadEngineConfig(
                request_budget=100,
                results_per_query=10,
                template_set="application_student",
                source_block_threshold=72,
            ),
        )

        class StubPipelineOrchestrator:
            def __init__(self, _store, lead_engine, **_kwargs) -> None:
                captured["lead_config"] = lead_engine.config

            def run(self, _request):
                return SimpleNamespace(
                    run=SimpleNamespace(id=1, status=SimpleNamespace(value="completed")),
                    review_target_count=0,
                    fetched_count=0,
                    evidence_count=0,
                    rated_count=0,
                    drafted_count=0,
                    error_count=0,
                    import_results=[],
                )

        args = SimpleNamespace(
            profile_name="Configured",
            search_name="Configured Search",
            role=["Werkstudent IT"],
            region=["Essen"],
            tech=["Python"],
            request_budget=3,
            results_per_query=2,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            with patch.object(cli, "create_lead_engine", return_value=fake_lead_engine):
                with patch.object(cli, "create_rating_engine", return_value=object()):
                    with patch.object(cli, "PipelineOrchestrator", StubPipelineOrchestrator):
                        buffer = io.StringIO()
                        with redirect_stdout(buffer):
                            exit_code = cli._run_configured(args, database_url, config)

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["lead_config"].request_budget, 3)
        self.assertEqual(captured["lead_config"].results_per_query, 2)
        self.assertEqual(captured["lead_config"].template_set, "application_student")
        self.assertEqual(captured["lead_config"].source_block_threshold, 72)


def _run_cli(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(args)
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}")
    return json.loads(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
