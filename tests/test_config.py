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
        self.assertEqual(config.lead_budget.source_block_threshold, 35)
        self.assertEqual(config.lead_budget.blocked_source_domains, ())
        self.assertEqual(config.review_queue.page_size, 50)
        self.assertEqual(config.infrastructure.host, "127.0.0.1")
        self.assertEqual(config.infrastructure.port, 8765)
        self.assertEqual(config.llm.provider, "local")
        self.assertEqual(config.llm.openai_base_url, "https://api.openai.com/v1")
        self.assertEqual(config.llm.local_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.llm.heavy_provider, "openai")
        self.assertEqual(config.llm.heavy_model, "gpt-5.5")
        self.assertEqual(config.llm.light_provider, "ollama")
        self.assertEqual(config.llm.light_model, "qwen3:30b-a3b-q4_K_M")
        self.assertEqual(config.search_provider.provider, "mock")

    def test_environment_overrides_defaults(self) -> None:
        config = load_app_config(
            env_file=None,
            environ={
                "DATABASE_URL": "sqlite:///:memory:",
                "TARGET_RADAR_HOST": "127.0.0.2",
                "TARGET_RADAR_PORT": "9000",
                "TARGET_RADAR_REQUEST_BUDGET": "25",
                "TARGET_RADAR_SOURCE_BLOCK_THRESHOLD": "45",
                "TARGET_RADAR_BLOCKED_SOURCE_DOMAINS": "jobs.example, social.example",
                "TARGET_RADAR_MIN_CONFIDENCE_FOR_DRAFT": "0.75",
                "GITHUB_TOKEN": "ghp",
                "LLM_PROVIDER": "openai",
                "LLM_HEAVY_PROVIDER": "openai",
                "LLM_HEAVY_MODEL": "gpt-5.5",
                "LLM_LIGHT_PROVIDER": "ollama",
                "LLM_LIGHT_MODEL": "qwen-test",
                "OPENAI_API_KEY": "sk",
                "SEARCH_PROVIDER": "brave",
                "BRAVE_API_KEY": "bv",
            },
        )

        self.assertEqual(config.infrastructure.database_url, "sqlite:///:memory:")
        self.assertEqual(config.infrastructure.host, "127.0.0.2")
        self.assertEqual(config.infrastructure.port, 9000)
        self.assertEqual(config.lead_budget.request_budget, 25)
        self.assertEqual(config.lead_budget.source_block_threshold, 45)
        self.assertEqual(
            config.lead_budget.blocked_source_domains,
            ("jobs.example", "social.example"),
        )
        self.assertEqual(config.rating.min_confidence_for_draft, 0.75)
        self.assertEqual(config.github.token, "ghp")
        self.assertEqual(config.llm.provider, "openai")
        self.assertEqual(config.llm.heavy_provider, "openai")
        self.assertEqual(config.llm.heavy_model, "gpt-5.5")
        self.assertEqual(config.llm.light_provider, "ollama")
        self.assertEqual(config.llm.light_model, "qwen-test")
        self.assertEqual(config.llm.openai_api_key, "sk")
        self.assertEqual(config.search_provider.provider, "brave")
        self.assertEqual(config.search_provider.brave_api_key, "bv")

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
