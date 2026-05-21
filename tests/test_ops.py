from __future__ import annotations

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from target_radar.ops import (
    JsonLogFormatter,
    collect_diagnostics,
    configure_logging,
    redact_value,
    run_privacy_check,
)
from target_radar.storage import SQLiteStore


class OpsTests(unittest.TestCase):
    def test_redact_value_hides_sensitive_mapping_keys_and_assignments(self) -> None:
        payload = redact_value(
            {
                "BRAVE_API_KEY": "short",
                "nested": {"token": "abc123"},
                "message": "OPENAI_API_KEY=short ok",
            }
        )

        self.assertEqual(payload["BRAVE_API_KEY"], "[REDACTED]")
        self.assertEqual(payload["nested"]["token"], "[REDACTED]")
        self.assertEqual(payload["message"], "OPENAI_API_KEY=[REDACTED] ok")

    def test_json_log_formatter_redacts_extra_context(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())
        logger = logging.getLogger("target_radar.test.ops")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info(
            "provider failed with BRAVE_API_KEY=short",
            extra={"extra": {"openai_api_key": "short", "safe": "value"}},
        )

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["extra"]["openai_api_key"], "[REDACTED]")
        self.assertEqual(payload["extra"]["safe"], "value")
        self.assertIn("[REDACTED]", payload["message"])

    def test_configure_logging_can_write_json_lines_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "target-radar.jsonl"
            configure_logging(level="INFO", log_file=log_file, include_stream=False)
            logging.getLogger("target_radar.test").info(
                "hello",
                extra={"extra": {"token": "short"}},
            )
            logging.shutdown()
            logging.getLogger().handlers.clear()

            payload = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(payload["extra"]["token"], "[REDACTED]")

    def test_collect_diagnostics_returns_secret_safe_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'target-radar.sqlite3'}"
            store = SQLiteStore.open(database_url)
            store.close()

            diagnostics = collect_diagnostics(database_url)

        self.assertEqual(diagnostics["database"]["status"], "ok")
        self.assertEqual(diagnostics["database"]["url"], "[REDACTED]")
        self.assertIn("targets", diagnostics["table_counts"])

    def test_privacy_check_accepts_clean_local_repo_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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
            (root / ".env.example").write_text("BRAVE_API_KEY=\n", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / ".gitkeep").write_text("", encoding="utf-8")

            result = run_privacy_check(root)

        self.assertTrue(result["ok"])

    def test_privacy_check_flags_local_database_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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
            (root / ".env.example").write_text("BRAVE_API_KEY=\n", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / "local.sqlite3").write_text("not a real db", encoding="utf-8")

            result = run_privacy_check(root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["findings"][0]["code"], "tracked_local_data")


if __name__ == "__main__":
    unittest.main()
