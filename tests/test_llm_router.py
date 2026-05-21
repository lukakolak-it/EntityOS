from __future__ import annotations

import unittest

from target_radar.config import load_app_config
from target_radar.domain import RecommendedAction
from target_radar.engines.rating import AIRatingRequest, LLMAIRatingProvider
from target_radar.llm import FakeLLMClient, LLMRouter, create_llm_router


class LLMRouterTests(unittest.TestCase):
    def test_router_selects_heavy_and_light_clients(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="heavy", provider="fake", model="heavy-model"),
            light=FakeLLMClient(text="light", provider="fake", model="light-model"),
        )

        heavy = router.complete("prompt", task="heavy")
        light = router.complete("prompt", task="light")

        self.assertEqual(heavy.text, "heavy")
        self.assertEqual(heavy.model, "heavy-model")
        self.assertEqual(light.text, "light")
        self.assertEqual(light.model, "light-model")

    def test_create_router_can_use_fake_profiles_without_network(self) -> None:
        config = load_app_config(
            env_file=None,
            environ={
                "LLM_HEAVY_PROVIDER": "fake",
                "LLM_HEAVY_MODEL": "fake-heavy",
                "LLM_LIGHT_PROVIDER": "fake",
                "LLM_LIGHT_MODEL": "fake-light",
            },
        )

        router = create_llm_router(config)

        self.assertEqual(router.client_for("heavy").model, "fake-heavy")
        self.assertEqual(router.client_for("light").model, "fake-light")

    def test_llm_ai_rating_provider_parses_json_response(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(
                text=(
                    '{"ai_score": 82, "confidence": 0.77, '
                    '"recommended_action": "draft", '
                    '"reasons": [{"text": "fit", "source_url": "https://example.com", '
                    '"evidence": "Werkstudent IT"}], "risks": []}'
                ),
                model="fake-heavy",
            ),
            light=FakeLLMClient(text="{}"),
        )
        provider = LLMAIRatingProvider(router=router, task="heavy")

        response = provider.rate(
            AIRatingRequest(
                target_domain="example.com",
                search_terms=("Werkstudent IT",),
                context_text="Werkstudent IT",
                rule_score=80,
            )
        )

        self.assertEqual(response.ai_score, 82)
        self.assertEqual(response.confidence, 0.77)
        self.assertEqual(response.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(response.model_name, "fake-heavy")


if __name__ == "__main__":
    unittest.main()
