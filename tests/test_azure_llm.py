from acme.config import settings
from acme.llm.azure_openai import AzureOpenAIClient


def test_azure_deployment_resolver():
    client = AzureOpenAIClient()
    assert client._deployment(None) == settings.azure_openai_deployment
    assert client._deployment("custom") == "custom"


def test_azure_ping_without_credentials():
    client = AzureOpenAIClient()
    client.endpoint = ""
    client.api_key = ""

    import asyncio

    assert asyncio.run(client.ping()) is False
