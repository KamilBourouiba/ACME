import pytest
from unittest.mock import AsyncMock, MagicMock

from acme.evaluation.sandbox import benchmark_source_id, benchmark_tags


def test_benchmark_tags():
    tags = benchmark_tags("retention_latency_churn")
    assert "memorybench" in tags
    assert "bench:retention_latency_churn" in tags


def test_benchmark_source_id_unique():
    a = benchmark_source_id("scenario_a", "crm-1")
    b = benchmark_source_id("scenario_b", "crm-1")
    assert a != b


@pytest.mark.asyncio
async def test_cleanup_benchmark_state():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    from acme.evaluation.sandbox import cleanup_benchmark_state

    await cleanup_benchmark_state(session)
    assert session.execute.await_count == 3
    session.commit.assert_awaited_once()
