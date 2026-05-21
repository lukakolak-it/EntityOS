"""Heavy/light LLM routing."""

from __future__ import annotations

from dataclasses import dataclass

from target_radar.config import AppConfig
from target_radar.llm.clients import (
    FakeLLMClient,
    LLMClient,
    LLMRequest,
    LLMResponse,
    OllamaGenerateClient,
    OpenAIResponsesClient,
)


@dataclass(frozen=True, slots=True)
class LLMRouter:
    heavy: LLMClient
    light: LLMClient
    default_task: str = "light"

    def complete(
        self,
        prompt: str,
        *,
        task: str | None = None,
        instructions: str | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        selected = self.client_for(task or self.default_task)
        return selected.complete(
            LLMRequest(
                prompt=prompt,
                instructions=instructions,
                temperature=temperature,
            )
        )

    def client_for(self, task: str) -> LLMClient:
        normalized = task.strip().lower()
        if normalized == "heavy":
            return self.heavy
        if normalized == "light":
            return self.light
        raise ValueError(f"unsupported LLM task: {task}")


def create_llm_router(config: AppConfig) -> LLMRouter:
    return LLMRouter(
        heavy=_create_client(
            provider=config.llm.heavy_provider,
            model=config.llm.heavy_model,
            config=config,
        ),
        light=_create_client(
            provider=config.llm.light_provider,
            model=config.llm.light_model,
            config=config,
        ),
        default_task="light",
    )


def _create_client(*, provider: str, model: str, config: AppConfig) -> LLMClient:
    normalized = provider.strip().lower()
    if normalized in {"fake", "mock"}:
        return FakeLLMClient(text="{}", provider="fake", model=model)
    if normalized == "openai":
        if not config.llm.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI LLM provider")
        return OpenAIResponsesClient(
            api_key=config.llm.openai_api_key,
            model=model,
            base_url=config.llm.openai_base_url,
        )
    if normalized in {"ollama", "local"}:
        return OllamaGenerateClient(
            model=model,
            base_url=config.llm.local_base_url,
            api_key=config.llm.local_api_key,
        )
    raise ValueError(f"unsupported LLM provider: {provider}")
