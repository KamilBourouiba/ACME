"""Benchmark sandbox — isolate MemoryBench scenarios on shared infrastructure."""

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord, Episode, QuerySession
from acme.graph.neo4j_client import Neo4jClient

BENCHMARK_TAG = "memorybench"
LONGMEMEVAL_TAG = "longmemeval"


async def cleanup_benchmark_state(
    session: AsyncSession,
    graph: Neo4jClient | None = None,
    *,
    tenant_id: str = "default",
) -> dict[str, int | str]:
    """Remove prior benchmark data so each scenario starts clean."""
    stats: dict[str, int | str] = {"tenant_id": tenant_id}

    await session.execute(
        text("DELETE FROM episodes WHERE tags @> :tag AND tenant_id = :tenant_id"),
        {"tag": f'["{BENCHMARK_TAG}"]', "tenant_id": tenant_id},
    )
    await session.execute(
        delete(BeliefRecord).where(BeliefRecord.tenant_id == tenant_id)
    )
    await session.execute(
        text(
            "DELETE FROM query_sessions WHERE question LIKE :prefix AND tenant_id = :tenant_id"
        ),
        {"prefix": "[MemoryBench:%", "tenant_id": tenant_id},
    )
    await session.commit()

    if graph is not None:
        graph_stats = await graph.delete_benchmark_graph(BENCHMARK_TAG, tenant_id=tenant_id)
        stats.update(graph_stats)
        stats["orphans_pruned"] = await graph.prune_orphan_entities(tenant_id=tenant_id)

    return stats


async def cleanup_longmemeval_state(
    session: AsyncSession,
    graph: Neo4jClient | None = None,
    *,
    tenant_id: str = "default",
) -> dict[str, int | str]:
    """Remove prior LongMemEval ingest data before each question."""
    stats: dict[str, int | str] = {"tenant_id": tenant_id}

    try:
        await session.rollback()
    except Exception:
        pass

    await session.execute(
        text("DELETE FROM episodes WHERE tags @> :tag AND tenant_id = :tenant_id"),
        {"tag": f'["{LONGMEMEVAL_TAG}"]', "tenant_id": tenant_id},
    )
    await session.execute(
        delete(BeliefRecord).where(BeliefRecord.tenant_id == tenant_id)
    )
    await session.execute(
        text(
            "DELETE FROM query_sessions WHERE question LIKE :prefix AND tenant_id = :tenant_id"
        ),
        {"prefix": "[LongMemEval:%", "tenant_id": tenant_id},
    )
    await session.commit()

    if graph is not None:
        graph_stats = await graph.delete_benchmark_graph(LONGMEMEVAL_TAG, tenant_id=tenant_id)
        stats.update(graph_stats)
        stats["orphans_pruned"] = await graph.prune_orphan_entities(tenant_id=tenant_id)

    return stats


def benchmark_tags(scenario_name: str) -> list[str]:
    return [BENCHMARK_TAG, f"bench:{scenario_name}"]


def benchmark_source_id(scenario_name: str, source_id: str | None) -> str:
    base = source_id or "default"
    return f"{scenario_name}:{base}"


def longmemeval_tags(question_id: str) -> list[str]:
    return [LONGMEMEVAL_TAG, f"lme:{question_id}"]


def longmemeval_source_id(question_id: str, session_id: str) -> str:
    return f"{question_id}:{session_id}"
