import os

import pytest

from acme.ollama.client import OllamaClient

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 to run Ollama live tests",
)


@pytest.mark.asyncio
async def test_ollama_ping():
    client = OllamaClient()
    if not await client.ping():
        pytest.skip("Ollama not running")

    assert await client.ping()


@pytest.mark.asyncio
async def test_ollama_compress_episodes_live():
    client = OllamaClient()
    if not await client.ping():
        pytest.skip("Ollama not running")

    result = await client.compress_episodes(
        [
            "Customer A failed checkout due to API latency",
            "Customer B failed checkout due to API latency",
            "Customer C failed checkout due to API latency",
        ],
        cluster_key="latency",
    )

    assert result.get("abstraction")
    assert float(result.get("confidence", 0)) > 0
