"""Text embeddings — Azure OpenAI or deterministic fallback."""

import hashlib
import math
import re

import httpx

from acme.config import settings
from acme.observability.runtime_stats import record_embedding

_DIM = 256


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def deterministic_embed(text: str, dim: int = _DIM) -> list[float]:
    """Hash-based embedding for local/tests — no external API required."""
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode()).digest()
        for i in range(min(8, dim)):
            idx = digest[i] % dim
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class EmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        if settings.azure_openai_embedding_deployment and settings.azure_openai_api_key:
            try:
                vec = await self._azure_embed(text)
                record_embedding(provider="azure_openai", success=True)
                return vec
            except Exception:
                record_embedding(provider="azure_openai", success=False)
        record_embedding(provider="deterministic", success=True)
        return deterministic_embed(text)

    async def _azure_embed(self, text: str, *, dim: int = _DIM) -> list[float]:
        deployment = settings.azure_openai_embedding_deployment
        url = (
            f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings"
            f"?api-version={settings.azure_openai_api_version}"
        )
        headers = {"api-key": settings.azure_openai_api_key, "Content-Type": "application/json"}
        payload: dict = {"input": text}
        if "text-embedding-3" in deployment:
            payload["dimensions"] = dim
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()["data"][0]["embedding"]
            vec = [float(x) for x in data]
            if len(vec) != dim:
                return deterministic_embed(text, dim=dim)
            return vec
