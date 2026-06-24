from acme.config import settings
from acme.llm.azure_openai import AzureOpenAIClient
from acme.llm.base import BaseLLMClient
from acme.llm.ollama import OllamaClient


def get_llm_client() -> BaseLLMClient:
    provider = settings.llm_provider.lower().strip()
    if provider == "azure_openai":
        return AzureOpenAIClient()
    if provider == "ollama":
        return OllamaClient()
    raise ValueError(f"Unsupported LLM provider: {provider}")


llm_client = get_llm_client()
