from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from target_radar.config import load_app_config


class ConfigTests(unittest.TestCase):
    def test_defaults_are_usable_without_env_file(self) -> None:
        config = load_app_config(env_file=None, environ={})

        self.assertEqual(config.infrastructure.environment, "local")
        self.assertEqual(
            config.infrastructure.database_url,
            "sqlite:///data/target-radar.local.sqlite3",
        )
        self.assertEqual(config.rating.hard_stop_action, "skip")
        self.assertEqual(config.lead_budget.request_budget, 100)
        self.assertEqual(config.review_queue.page_size, 50)

    def test_environment_overrides_defaults(self) -> None:
        config = load_app_config(
            env_file=None,
            environ={
                "DATABASE_URL": "sqlite:///:memory:",
                "TARGET_RADAR_REQUEST_BUDGET": "25",
                "TARGET_RADAR_MIN_CONFIDENCE_FOR_DRAFT": "0.75",
            },
        )

        self.assertEqual(config.infrastructure.database_url, "sqlite:///:memory:")
        self.assertEqual(config.lead_budget.request_budget, 25)
        self.assertEqual(config.rating.min_confidence_for_draft, 0.75)

    def test_env_file_overrides_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "DATABASE_URL=sqlite:///from-file.sqlite3",
                        "TARGET_RADAR_REQUEST_BUDGET=10",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_app_config(
                env_file=env_file,
                environ={
                    "DATABASE_URL": "sqlite:///from-process.sqlite3",
                    "TARGET_RADAR_REQUEST_BUDGET": "99",
                },
            )

        self.assertEqual(config.infrastructure.database_url, "sqlite:///from-file.sqlite3")
        self.assertEqual(config.lead_budget.request_budget, 10)


if __name__ == "__main__":
    unittest.main()
