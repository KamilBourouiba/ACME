"""Azure OpenAI inference layer (GPT-4.1, etc.)."""

from typing import Any

import httpx

from acme.config import settings
from acme.llm.base import BaseLLMClient


class AzureOpenAIClient(BaseLLMClient):
    provider_name = "azure_openai"

    def __init__(self) -> None:
        self.endpoint = settings.azure_openai_endpoint.rstrip("/")
        self.api_key = settings.azure_openai_api_key
        self.api_version = settings.azure_openai_api_version

    def _deployment(self, model: str | None) -> str:
        return model or settings.azure_openai_deployment

    async def ping(self) -> bool:
        if not self.endpoint or not self.api_key:
            return False
        try:
            await self.generate("Reply with OK", temperature=0.0, timeout=30.0)
            return True
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.2,
        timeout: float = 300.0,
        json_mode: bool = False,
    ) -> str:
        deployment = self._deployment(model)
        url = (
            f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": settings.azure_openai_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
