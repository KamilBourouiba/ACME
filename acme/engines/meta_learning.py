"""Meta-learning — ACME learns about its own learning process."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord, MetaLearningRecord


class MetaLearningEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, metric_name: str, value: float) -> MetaLearningRecord:
        stmt = select(MetaLearningRecord).where(MetaLearningRecord.metric_name == metric_name)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = MetaLearningRecord(metric_name=metric_name, metric_value=value, sample_count=1)
            self.session.add(row)
        else:
            n = row.sample_count
            row.metric_value = (row.metric_value * n + value) / (n + 1)
            row.sample_count = n + 1
        await self.session.flush()
        return row

    async def snapshot(self) -> dict[str, float]:
        stmt = select(MetaLearningRecord)
        result = await self.session.execute(stmt)
        return {r.metric_name: round(r.metric_value, 4) for r in result.scalars().all()}

    async def analyze_belief_outcomes(self) -> dict[str, float]:
        stmt = select(BeliefRecord)
        beliefs = list((await self.session.execute(stmt)).scalars().all())
        if not beliefs:
            return {}

        deprecated = sum(1 for b in beliefs if b.status in ("deprecated", "archived"))
        promoted = sum(1 for b in beliefs if b.status == "belief")
        avg_crs = sum(b.crs or 0 for b in beliefs) / len(beliefs)

        await self.record("belief_deprecation_rate", deprecated / len(beliefs))
        await self.record("belief_promotion_rate", promoted / len(beliefs))
        await self.record("avg_crs", avg_crs)

        return {
            "belief_deprecation_rate": deprecated / len(beliefs),
            "belief_promotion_rate": promoted / len(beliefs),
            "avg_crs": round(avg_crs, 4),
        }
