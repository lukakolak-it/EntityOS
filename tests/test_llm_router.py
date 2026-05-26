from __future__ import annotations

import unittest

from target_radar.config import load_app_config
from target_radar.domain import RecommendedAction
from target_radar.engines.rating import (
    AIRatingRequest,
    LLMAIRatingProvider,
    create_rating_engine,
)
from target_radar.llm import (
    FakeLLMClient,
    LLMRequest,
    LLMRouter,
    OllamaGenerateClient,
    OpenAIResponsesClient,
    create_llm_router,
)
import target_radar.llm.clients as clients


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

    def test_light_only_router_does_not_require_heavy_credentials(self) -> None:
        config = load_app_config(
            env_file=None,
            environ={
                "LLM_HEAVY_PROVIDER": "openai",
                "LLM_HEAVY_MODEL": "gpt-5.5",
                "LLM_LIGHT_PROVIDER": "fake",
                "LLM_LIGHT_MODEL": "fake-light",
            },
        )

        router = create_llm_router(config, enabled_tasks=("light",))

        self.assertEqual(router.client_for("light").model, "fake-light")
        self.assertEqual(router.client_for("heavy").provider, "unavailable")

    def test_llm_ai_rating_provider_parses_json_response(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="{}", model="fake-heavy"),
            light=FakeLLMClient(
                text=(
                    '{"ai_score": 82, "confidence": 0.77, '
                    '"recommended_action": "draft", '
                    '"reasons": [{"text": "fit", "source_url": "https://example.com", '
                    '"evidence": "Werkstudent IT"}], "risks": []}'
                ),
                model="fake-light",
            ),
        )
        provider = LLMAIRatingProvider(router=router)

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
        self.assertEqual(response.model_name, "fake-light")

    def test_llm_ai_rating_provider_normalizes_label_and_percent_scores(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="{}"),
            light=FakeLLMClient(
                text=(
                    '{"score": "88/100", "confidence": "high", '
                    '"recommended_action": "recommended", '
                    '"reasons": [{"text": "fit", "source_url": "https://example.com", '
                    '"evidence": "Solar Services"}], "risks": []}'
                )
            ),
        )
        provider = LLMAIRatingProvider(router=router)

        response = provider.rate(
            AIRatingRequest(
                target_domain="example.com",
                search_terms=("Solar",),
                context_text="Solar Services",
                rule_score=80,
            )
        )

        self.assertEqual(response.ai_score, 88)
        self.assertEqual(response.confidence, 0.85)
        self.assertEqual(response.recommended_action, RecommendedAction.DRAFT)

    def test_llm_ai_rating_provider_normalizes_comma_and_percentage_confidence(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="{}"),
            light=FakeLLMClient(
                text=(
                    '{"ai_score": "0,82", "confidence": "76%", '
                    '"recommended_action": "needs_review", '
                    '"reasons": [], "risks": []}'
                )
            ),
        )
        provider = LLMAIRatingProvider(router=router)

        response = provider.rate(
            AIRatingRequest(
                target_domain="example.com",
                search_terms=("Solar",),
                context_text="Solar Services",
                rule_score=80,
            )
        )

        self.assertEqual(response.ai_score, 82)
        self.assertEqual(response.confidence, 0.76)
        self.assertEqual(response.recommended_action, RecommendedAction.REVIEW)

    def test_llm_ai_rating_provider_normalizes_small_scale_and_string_reasons(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="{}"),
            light=FakeLLMClient(
                text=(
                    '{"ai_score": 4, "confidence": "high", '
                    '"recommended_action": "Include in OSINT collection", '
                    '"reasons": ["Solar Services in Essen are relevant."], '
                    '"risks": ["Potentially outdated information."]}'
                )
            ),
        )
        provider = LLMAIRatingProvider(router=router)

        response = provider.rate(
            AIRatingRequest(
                target_domain="example.com",
                search_terms=("Solar",),
                context_text=(
                    "Source: https://example.com\n"
                    "Evidence: Example GmbH bietet Solar Services in Essen mit Kontakt."
                ),
                rule_score=80,
            )
        )

        self.assertEqual(response.ai_score, 80)
        self.assertEqual(response.confidence, 0.85)
        self.assertEqual(response.recommended_action, RecommendedAction.DRAFT)
        self.assertEqual(response.reasons[0]["source_url"], "https://example.com")
        self.assertIn("Solar Services in Essen", response.reasons[0]["evidence"])
        self.assertEqual(response.risks[0]["type"], "llm_risk")

    def test_llm_ai_rating_provider_normalizes_invalid_action(self) -> None:
        router = LLMRouter(
            heavy=FakeLLMClient(text="{}"),
            light=FakeLLMClient(
                text=(
                    '{"ai_score": 51, "confidence": 0.62, '
                    '"recommended_action": "proceed with caution", '
                    '"reasons": [], "risks": []}'
                )
            ),
        )
        provider = LLMAIRatingProvider(router=router)

        response = provider.rate(
            AIRatingRequest(
                target_domain="example.com",
                search_terms=("Werkstudent IT",),
                context_text="Werkstudent IT",
                rule_score=55,
            )
        )

        self.assertEqual(response.recommended_action, RecommendedAction.REVIEW)

    def test_rating_engine_factory_defaults_to_light_task(self) -> None:
        config = load_app_config(
            env_file=None,
            environ={
                "LLM_HEAVY_PROVIDER": "openai",
                "LLM_HEAVY_MODEL": "gpt-5.5",
                "LLM_LIGHT_PROVIDER": "fake",
                "LLM_LIGHT_MODEL": "fake-light",
            },
        )

        engine = create_rating_engine(config)

        self.assertIsNotNone(engine.ai_provider)

    def test_openai_gpt5_request_omits_temperature(self) -> None:
        captured_payloads = []
        original_post_json = clients._post_json

        def fake_post_json(url, payload, *, headers=None, timeout=60):
            captured_payloads.append(payload)
            return {"output_text": "{}"}

        clients._post_json = fake_post_json
        try:
            client = OpenAIResponsesClient(api_key="test", model="gpt-5.5")
            client.complete(LLMRequest(prompt="{}", temperature=0.1))
        finally:
            clients._post_json = original_post_json

        self.assertNotIn("temperature", captured_payloads[0])

    def test_ollama_client_uses_extended_timeout(self) -> None:
        captured_timeouts = []
        captured_payloads = []
        original_post_json = clients._post_json

        def fake_post_json(url, payload, *, headers=None, timeout=60):
            captured_timeouts.append(timeout)
            captured_payloads.append(payload)
            return {"response": "<think>notes</think>{}"}

        clients._post_json = fake_post_json
        try:
            client = OllamaGenerateClient(model="qwen3:30b-a3b-q4_K_M")
            response = client.complete(LLMRequest(prompt="{}"))
        finally:
            clients._post_json = original_post_json

        self.assertEqual(captured_timeouts[0], 300)
        self.assertEqual(captured_payloads[0]["format"], "json")
        self.assertEqual(response.text, "{}")


if __name__ == "__main__":
    unittest.main()
