"""Azure OpenAI inference layer (GPT-4.1, etc.)."""

import asyncio
from typing import Any

import httpx

from acme.config import settings
from acme.llm.base import BaseLLMClient


class AzureOpenAIClient(BaseLLMClient):
    provider_name = "azure_openai"
    _max_retries = 6

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

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 429:
                return response
            retry_after = response.headers.get("retry-after")
            wait = float(retry_after) if retry_after else delay
            if attempt < self._max_retries - 1:
                await asyncio.sleep(wait)
                delay = min(delay * 2, 60.0)
                continue
            last_exc = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=response.request,
                response=response,
            )
        raise last_exc or RuntimeError("Azure OpenAI request failed")

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
            response = await self._post_with_retry(client, url, headers=headers, payload=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
