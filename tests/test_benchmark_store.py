import pytest
from unittest.mock import AsyncMock, MagicMock

from acme.evaluation.benchmark_store import record_to_dict, save_memorybench_run
from acme.schemas import MemoryBenchResult


@pytest.mark.asyncio
async def test_save_memorybench_run():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda r: setattr(r, "id", "00000000-0000-0000-0000-000000000001"))

    result = MemoryBenchResult(
        retention_score=0.9,
        feedback_correction_score=1.0,
        hallucination_resistance_score=1.0,
        belief_quality_score=0.7,
        overall_score=0.88,
        details={"scenarios_run": 10, "failures": []},
    )
    record = await save_memorybench_run(session, result, tenant_id="default")
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert record.overall_score == 0.88


def test_record_to_dict_shape():
    from datetime import datetime, timezone
    from uuid import uuid4

    from acme.db.models import BenchmarkRunRecord

    rec = BenchmarkRunRecord(
        id=uuid4(),
        run_type="compare",
        tenant_id="default",
        overall_score=0.88,
        retention_score=0.9,
        feedback_score=1.0,
        groundedness_score=1.0,
        belief_quality_score=0.7,
        scenarios_run=10,
        failures=[],
        payload={"export": {"timestamp": "2026-01-01"}},
        created_at=datetime.now(timezone.utc),
    )
    data = record_to_dict(rec)
    assert data["run_type"] == "compare"
    assert data["overall_score"] == 0.88
    assert "payload" in data
