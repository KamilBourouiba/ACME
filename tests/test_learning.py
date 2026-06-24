import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from acme.engines.learning import LearningEngine
from acme.schemas import LearningRequest


@pytest.mark.asyncio
async def test_learning_run_generates_hypotheses():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    cycle = MagicMock()
    cycle.id = uuid.uuid4()
    cycle.started_at = datetime.now(timezone.utc)

    graph = AsyncMock()
    graph.upsert_entity = AsyncMock(return_value="Hypothesis: test")
    graph.upsert_relation = AsyncMock()

    ollama = AsyncMock()
    ollama.generate_hypotheses = AsyncMock(
        return_value=[
            {
                "statement": "Latency drives checkout failures",
                "rationale": "Repeated pattern in episodes",
                "testable_prediction": "Fixing latency reduces churn",
                "confidence": 0.75,
            }
        ]
    )

    engine = LearningEngine(session, graph, ollama)
    engine.events = AsyncMock()
    engine.events.append = AsyncMock(return_value=uuid.uuid4())
    engine.compression = AsyncMock()
    engine.compression.compress = AsyncMock(
        return_value=MagicMock(abstractions_created=1, episodes_compressed=3)
    )
    engine.forgetting = AsyncMock()
    engine.forgetting.run = AsyncMock(
        return_value=MagicMock(tier_changes={"warm": 2}, archived=0, deleted=0)
    )
    engine.beliefs = AsyncMock()
    engine.beliefs.sync_from_relation = AsyncMock()
    engine.beliefs.consolidate_lifecycle = AsyncMock(return_value=(1, 0))
    engine.predictions = AsyncMock()
    engine.predictions.create = AsyncMock()
    engine._build_learning_context = AsyncMock(return_value="context")

    def capture_add(obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)

    session.add = MagicMock(side_effect=capture_add)

    result = await engine.run(
        LearningRequest(consolidate=True, generate_hypotheses=True, forget_dry_run=True)
    )

    assert result.hypotheses_generated == 1
    assert result.abstractions_created == 1
    assert result.beliefs_promoted == 1
    ollama.generate_hypotheses.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_learning_hypotheses_only():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    graph = AsyncMock()
    graph.upsert_entity = AsyncMock(return_value="Hypothesis: x")
    ollama = AsyncMock()
    ollama.generate_hypotheses = AsyncMock(return_value=[])

    engine = LearningEngine(session, graph, ollama)
    engine.events = AsyncMock()
    engine.events.append = AsyncMock(return_value=uuid.uuid4())
    engine._build_learning_context = AsyncMock(return_value="ctx")

    def capture_add(obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    session.add = MagicMock(side_effect=capture_add)

    result = await engine.run(
        LearningRequest(consolidate=False, generate_hypotheses=True)
    )

    assert result.hypotheses_generated == 0
    ollama.generate_hypotheses.assert_called_once()
