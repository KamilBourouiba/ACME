"""End-to-end integration tests — requires Docker (Postgres + Neo4j) and Ollama."""

import os

import httpx
import pytest

from acme.llm.factory import get_llm_client
from acme.llm.ollama import OllamaClient

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run E2E tests",
)

pytest_plugins = ["tests.conftest_integration"]


@pytest.mark.asyncio
async def test_health(api_server):
    async with httpx.AsyncClient(base_url=api_server, timeout=30.0) as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["postgres"] is True
    assert data["neo4j"] is True


@pytest.mark.asyncio
async def test_full_cognitive_loop(api_server):
    llm = get_llm_client()
    if not await llm.ping():
        pytest.skip("LLM provider not reachable")

    async with httpx.AsyncClient(base_url=api_server, timeout=300.0) as client:
        experiences = [
            {
                "content": "Customer A complained about API latency during peak hours.",
                "action": "investigate",
                "tags": ["latency", "customer"],
            },
            {
                "content": "Customer B churned after repeated timeout errors on checkout.",
                "action": "analyze churn",
                "tags": ["latency", "churn"],
            },
            {
                "content": "Customer C reported slow dashboard — database bottleneck.",
                "action": "optimize",
                "tags": ["latency", "database"],
            },
        ]

        for exp in experiences:
            r = await client.post("/api/v1/experiences", json=exp)
            assert r.status_code == 201, r.text

        query = await client.post(
            "/api/v1/query",
            json={"question": "What causes customer failures?", "challenge": False},
        )
        assert query.status_code == 200, query.text
        session_id = query.json()["session_id"]

        feedback = await client.post(
            "/api/v1/feedback",
            json={"session_id": session_id, "outcome": "success", "feedback": "Confirmed"},
        )
        assert feedback.status_code == 200

        compress = await client.post(
            "/api/v1/compress",
            json={"tags": ["latency"], "min_episodes": 3, "min_confidence": 0.4},
        )
        assert compress.status_code == 200, compress.text

        forget = await client.post("/api/v1/forget/run", json={"dry_run": True})
        assert forget.status_code == 200

        learn = await client.post(
            "/api/v1/learn/run",
            json={
                "consolidate": False,
                "generate_hypotheses": True,
                "forget_dry_run": True,
            },
        )
        assert learn.status_code == 200, learn.text
        data = learn.json()
        assert "cycle_id" in data

        assert (await client.get("/api/v1/hypotheses")).status_code == 200
        assert (await client.get("/api/v1/beliefs")).status_code == 200
        assert (await client.get("/api/v1/learn/cycles")).status_code == 200
