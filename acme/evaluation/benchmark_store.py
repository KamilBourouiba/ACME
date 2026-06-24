"""Persist benchmark runs to PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme import __version__
from acme.db.models import BenchmarkRunRecord
from acme.schemas import BenchmarkComparisonResult, MemoryBenchResult


async def save_memorybench_run(
    session: AsyncSession,
    result: MemoryBenchResult,
    *,
    tenant_id: str = "default",
    run_type: str = "memorybench",
    revision: str | None = None,
) -> BenchmarkRunRecord:
    record = BenchmarkRunRecord(
        run_type=run_type,
        tenant_id=tenant_id,
        version=__version__,
        revision=revision,
        overall_score=result.overall_score,
        retention_score=result.retention_score,
        feedback_score=result.feedback_correction_score,
        groundedness_score=result.hallucination_resistance_score,
        belief_quality_score=result.belief_quality_score,
        scenarios_run=result.details.get("scenarios_run", 0),
        failures=result.details.get("failures", []),
        payload=result.model_dump(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def save_compare_run(
    session: AsyncSession,
    result: BenchmarkComparisonResult,
    *,
    tenant_id: str = "default",
    revision: str | None = None,
) -> BenchmarkRunRecord:
    acme = result.acme
    record = BenchmarkRunRecord(
        run_type="compare",
        tenant_id=tenant_id,
        version=__version__,
        revision=revision,
        overall_score=acme.overall_score,
        retention_score=acme.retention_score,
        feedback_score=acme.feedback_correction_score,
        groundedness_score=acme.hallucination_resistance_score,
        belief_quality_score=acme.belief_quality_score,
        scenarios_run=acme.details.get("scenarios_run", 0),
        failures=acme.details.get("failures", []),
        payload=result.model_dump(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_latest_run(
    session: AsyncSession,
    *,
    run_type: str | None = None,
    tenant_id: str = "default",
) -> BenchmarkRunRecord | None:
    stmt = (
        select(BenchmarkRunRecord)
        .where(BenchmarkRunRecord.tenant_id == tenant_id)
        .order_by(BenchmarkRunRecord.created_at.desc())
        .limit(1)
    )
    if run_type:
        stmt = stmt.where(BenchmarkRunRecord.run_type == run_type)
    return (await session.execute(stmt)).scalar_one_or_none()


def record_to_dict(record: BenchmarkRunRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "run_type": record.run_type,
        "tenant_id": record.tenant_id,
        "version": record.version,
        "revision": record.revision,
        "overall_score": record.overall_score,
        "retention_score": record.retention_score,
        "feedback_score": record.feedback_score,
        "groundedness_score": record.groundedness_score,
        "belief_quality_score": record.belief_quality_score,
        "scenarios_run": record.scenarios_run,
        "failures": record.failures,
        "created_at": record.created_at.isoformat(),
        "payload": record.payload,
    }
