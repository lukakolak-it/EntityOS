"""LLM client implementations with no mandatory third-party dependencies."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMRequest:
    prompt: str
    instructions: str | None = None
    temperature: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    raw: dict[str, object] = field(default_factory=dict)


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate text for the request."""


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


@dataclass(frozen=True, slots=True)
class FakeLLMClient:
    text: str = "{}"
    provider: str = "fake"
    model: str = "fake-model"

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=self.text, provider=self.provider, model=self.model)


@dataclass(frozen=True, slots=True)
class OpenAIResponsesClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    provider: str = "openai"

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMError("OpenAI API key is required")

        payload: dict[str, object] = {
            "model": self.model,
            "input": request.prompt,
            "store": False,
        }
        if request.instructions:
            payload["instructions"] = request.instructions
        if request.temperature is not None and _openai_supports_temperature(self.model):
            payload["temperature"] = request.temperature

        response = _post_json(
            f"{self.base_url.rstrip('/')}/responses",
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        text = _extract_openai_text(response)
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            raw=response,
        )


@dataclass(frozen=True, slots=True)
class OllamaGenerateClient:
    model: str
    base_url: str = "http://127.0.0.1:11434"
    api_key: str | None = None
    provider: str = "ollama"

    def complete(self, request: LLMRequest) -> LLMResponse:
        prompt = request.prompt
        if request.instructions:
            prompt = f"{request.instructions}\n\n{request.prompt}"

        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = _post_json(
            f"{self.base_url.rstrip('/')}/api/generate",
            payload,
            headers=headers,
        )
        text = str(response.get("response") or "")
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            raw=response,
        )


def _post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(str(exc.reason)) from exc


def _extract_openai_text(payload: dict[str, object]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") == "output_text":
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(parts).strip()


def _openai_supports_temperature(model: str) -> bool:
    normalized = model.strip().lower()
    return not normalized.startswith(("gpt-5", "o1", "o3", "o4"))
