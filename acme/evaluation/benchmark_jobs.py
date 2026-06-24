"""Background benchmark jobs — avoid ingress timeout on long compare runs."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from acme.config import settings
from acme.db.session import SessionLocal
from acme.evaluation.compare_mutex import CompareAlreadyRunningError, is_compare_running
from acme.evaluation.comparison import run_benchmark_comparison
from acme.graph.neo4j_client import neo4j_client
from acme.llm.factory import llm_client
from acme.observability.runtime_stats import record_compare_job
from acme.orchestrator import ACMEOrchestrator

_jobs: dict[str, dict[str, Any]] = {}


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    items = sorted(
        _jobs.values(),
        key=lambda j: j.get("started_at", ""),
        reverse=True,
    )
    return items[:limit]


async def start_compare_job(*, tenant_id: str | None = None) -> str:
    tid = tenant_id or settings.default_tenant_id
    if is_compare_running(tid):
        raise CompareAlreadyRunningError(tid)
    job_id = str(uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "type": "benchmark_compare",
        "status": "running",
        "tenant_id": tid,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    asyncio.create_task(_run_compare_job(job_id, tenant_id=tid))
    return job_id


async def _run_compare_job(job_id: str, *, tenant_id: str | None) -> None:
    started = time.monotonic()
    try:
        async with SessionLocal() as session:
            orchestrator = ACMEOrchestrator(
                session=session,
                graph=neo4j_client,
                ollama=llm_client,
                tenant_id=tenant_id or settings.default_tenant_id,
            )
            result = await run_benchmark_comparison(orchestrator, llm_client)
            duration = time.monotonic() - started
            record_compare_job(success=True, duration_sec=duration)
            _jobs[job_id] = {
                **_jobs[job_id],
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_sec": round(duration, 2),
                "result": result.model_dump(),
            }
    except Exception as exc:
        duration = time.monotonic() - started
        record_compare_job(success=False, duration_sec=duration)
        _jobs[job_id] = {
            **_jobs.get(job_id, {"job_id": job_id}),
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_sec": round(duration, 2),
            "error": str(exc),
        }
