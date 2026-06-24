"""Operational metrics for ACME runtime health."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord, Episode, QuerySession
from acme.schemas import BeliefStatus


async def collect_metrics(session: AsyncSession, *, tenant_id: str = "default") -> dict:
    belief_stmt = select(
        func.count(BeliefRecord.id),
        func.avg(BeliefRecord.crs),
        func.avg(BeliefRecord.confidence),
    ).where(BeliefRecord.tenant_id == tenant_id)
    belief_row = (await session.execute(belief_stmt)).one()

    status_stmt = (
        select(BeliefRecord.status, func.count(BeliefRecord.id))
        .where(BeliefRecord.tenant_id == tenant_id)
        .group_by(BeliefRecord.status)
    )
    status_counts = {row[0]: row[1] for row in (await session.execute(status_stmt)).all()}

    episode_stmt = select(
        func.count(Episode.id),
        func.avg(Episode.importance_score),
    ).where(Episode.tenant_id == tenant_id)
    episode_row = (await session.execute(episode_stmt)).one()

    tier_stmt = (
        select(Episode.memory_tier, func.count(Episode.id))
        .where(Episode.tenant_id == tenant_id)
        .group_by(Episode.memory_tier)
    )
    tier_counts = {row[0]: row[1] for row in (await session.execute(tier_stmt)).all()}

    query_stmt = select(func.count(QuerySession.id)).where(QuerySession.tenant_id == tenant_id)
    query_count = (await session.execute(query_stmt)).scalar_one()

    demoted = status_counts.get(BeliefStatus.DEPRECATED.value, 0) + status_counts.get(
        BeliefStatus.ARCHIVED.value, 0
    )
    promoted = status_counts.get(BeliefStatus.BELIEF.value, 0)

    return {
        "tenant_id": tenant_id,
        "beliefs": {
            "total": belief_row[0] or 0,
            "avg_crs": round(float(belief_row[1] or 0.0), 4),
            "avg_confidence": round(float(belief_row[2] or 0.0), 4),
            "by_status": status_counts,
            "promoted_beliefs": promoted,
            "demoted_beliefs": demoted,
        },
        "episodes": {
            "total": episode_row[0] or 0,
            "avg_importance": round(float(episode_row[1] or 0.0), 4),
            "by_tier": tier_counts,
        },
        "queries": {"total": query_count or 0},
    }
