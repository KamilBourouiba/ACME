"""Wipe demo tenant data so the public loop can restart from a clean slate."""

from __future__ import annotations

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord, Episode, QuerySession
from acme.demo.agents import DEMO_AGENTS
from acme.graph.neo4j_client import Neo4jClient

DEMO_TENANT_IDS = tuple(a.tenant_id for a in DEMO_AGENTS)
LEGACY_DEMO_TENANT_IDS: tuple[str, ...] = tuple(
    f"demo-lumen-{a.id}" for a in DEMO_AGENTS
) + tuple(
    f"demo-nexus-{a.id}" for a in DEMO_AGENTS
)
ALL_DEMO_TENANT_IDS = DEMO_TENANT_IDS + LEGACY_DEMO_TENANT_IDS


async def cleanup_demo_tenant(
    session: AsyncSession,
    graph: Neo4jClient,
    *,
    tenant_id: str,
) -> dict[str, int | str]:
    """Remove all episodic, belief, session, and graph data for one demo tenant."""
    stats: dict[str, int | str] = {"tenant_id": tenant_id}

    await session.execute(
        text(
            """
            DELETE FROM failures
            WHERE session_id IN (
                SELECT id FROM query_sessions WHERE tenant_id = :tenant_id
            )
            """
        ),
        {"tenant_id": tenant_id},
    )
    qs = await session.execute(
        delete(QuerySession).where(QuerySession.tenant_id == tenant_id)
    )
    stats["query_sessions_deleted"] = qs.rowcount or 0

    ep = await session.execute(delete(Episode).where(Episode.tenant_id == tenant_id))
    stats["episodes_deleted"] = ep.rowcount or 0

    bl = await session.execute(delete(BeliefRecord).where(BeliefRecord.tenant_id == tenant_id))
    stats["beliefs_deleted"] = bl.rowcount or 0

    graph_stats = await graph.delete_tenant_graph(tenant_id=tenant_id)
    stats.update(graph_stats)
    stats["orphans_pruned"] = await graph.prune_orphan_entities(tenant_id=tenant_id)
    return stats


async def cleanup_all_demo_tenants(
    session: AsyncSession,
    graph: Neo4jClient,
) -> list[dict[str, int | str]]:
    results: list[dict[str, int | str]] = []
    for tenant_id in ALL_DEMO_TENANT_IDS:
        results.append(await cleanup_demo_tenant(session, graph, tenant_id=tenant_id))
    await session.commit()
    return results
