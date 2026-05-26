"""Heavy/light LLM routing."""

from __future__ import annotations

from dataclasses import dataclass

from target_radar.config import AppConfig
from target_radar.config.settings import (
    SUPPORTED_LLM_PROVIDERS,
    UNIMPLEMENTED_LLM_PROVIDERS,
)
from target_radar.llm.clients import (
    FakeLLMClient,
    LLMClient,
    LLMRequest,
    LLMResponse,
    OllamaGenerateClient,
    OpenAIResponsesClient,
    UnavailableLLMClient,
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


def create_llm_router(
    config: AppConfig,
    *,
    enabled_tasks: tuple[str, ...] = ("heavy", "light"),
) -> LLMRouter:
    enabled = {task.strip().lower() for task in enabled_tasks}
    return LLMRouter(
        heavy=(
            _create_client(
                provider=config.llm.heavy_provider,
                model=config.llm.heavy_model,
                config=config,
            )
            if "heavy" in enabled
            else UnavailableLLMClient(
                model=config.llm.heavy_model,
                reason="heavy LLM task is disabled for this router",
            )
        ),
        light=(
            _create_client(
                provider=config.llm.light_provider,
                model=config.llm.light_model,
                config=config,
            )
            if "light" in enabled
            else UnavailableLLMClient(
                model=config.llm.light_model,
                reason="light LLM task is disabled for this router",
            )
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
    if normalized in UNIMPLEMENTED_LLM_PROVIDERS:
        raise ValueError(
            f"LLM provider {normalized!r} is configured, but it is not implemented yet. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}."
        )
    raise ValueError(
        f"unsupported LLM provider: {provider}. Supported providers: "
        f"{', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}."
    )
