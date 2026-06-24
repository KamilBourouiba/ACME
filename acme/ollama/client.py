"""Backward-compatible re-export — prefer acme.llm.factory.llm_client."""

from acme.llm.base import BaseLLMClient
from acme.llm.factory import get_llm_client, llm_client

OllamaClient = BaseLLMClient  # legacy alias used in type hints

__all__ = ["OllamaClient", "get_llm_client", "llm_client", "ollama_client"]

ollama_client = llm_client
