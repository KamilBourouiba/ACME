from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from acme.evaluation.memorybench import (
    MemoryBenchScenario,
    _run_scenario,
    run_memorybench_with_orchestrator,
)
from acme.schemas import QueryResponse


@pytest.mark.asyncio
async def test_run_scenario_one_score_per_scenario():
    orchestrator = MagicMock()
    orchestrator.session = AsyncMock()
    orchestrator.graph = AsyncMock()
    orchestrator.graph.delete_benchmark_graph = AsyncMock(return_value={"entities_deleted": 0, "relations_deleted": 0})
    orchestrator.graph.prune_orphan_entities = AsyncMock(return_value=0)
    orchestrator.tenant_id = "default"
    orchestrator.session.execute = AsyncMock()
    orchestrator.session.commit = AsyncMock()
    orchestrator.ingest_experience = AsyncMock()
    orchestrator.query = AsyncMock(
        return_value=QueryResponse(
            answer="Customers churn due to API latency and slow checkout.",
            confidence=0.9,
            reasoning="pattern in memory",
            session_id=uuid4(),
        )
    )
    orchestrator.feedback = AsyncMock()
    orchestrator.ollama = AsyncMock()
    orchestrator.ollama.evaluate_answer_quality = AsyncMock(
        return_value={
            "retention_score": 0.9,
            "groundedness_score": 0.85,
            "reasoning": "Captures latency-churn link.",
            "judge": "llm",
        }
    )

    belief = MagicMock()
    belief.crs = 0.5
    belief.entity_or_relation_id = "rel:1"
    belief.contradicting_evidence = 0
    belief.status = "hypothesis"
    belief.confidence = 0.6
    orchestrator.beliefs = MagicMock()
    orchestrator.beliefs.list_beliefs = AsyncMock(return_value=[belief])

    scenario = MemoryBenchScenario(
        name="test",
        episodes=[{"content": "Customer churned after latency.", "source_type": "user"}],
        query="Why churn?",
        expected_concepts=["latency", "churn"],
    )

    result = await _run_scenario(orchestrator, scenario)
    assert result["retention_score"] == 0.9
    assert result["ingestion_ok"] is True
    assert orchestrator.ingest_experience.await_count == 1


@pytest.mark.asyncio
async def test_memorybench_overall_averages_four_metrics():
    orchestrator = MagicMock()
    orchestrator.session = AsyncMock()
    orchestrator.graph = AsyncMock()
    orchestrator.graph.delete_benchmark_graph = AsyncMock(return_value={"entities_deleted": 0, "relations_deleted": 0})
    orchestrator.graph.prune_orphan_entities = AsyncMock(return_value=0)
    orchestrator.tenant_id = "default"
    orchestrator.session.execute = AsyncMock()
    orchestrator.session.commit = AsyncMock()
    orchestrator.ingest_experience = AsyncMock()
    orchestrator.query = AsyncMock(
        return_value=QueryResponse(
            answer="Latency drives churn.",
            confidence=0.8,
            reasoning="ok",
            session_id=uuid4(),
        )
    )
    orchestrator.feedback = AsyncMock()
    orchestrator.ollama = AsyncMock()
    orchestrator.ollama.evaluate_answer_quality = AsyncMock(
        return_value={
            "retention_score": 0.8,
            "groundedness_score": 0.8,
            "reasoning": "ok",
            "judge": "llm",
        }
    )
    belief = MagicMock()
    belief.crs = 0.4
    belief.entity_or_relation_id = "rel:1"
    belief.contradicting_evidence = 0
    belief.status = "hypothesis"
    belief.confidence = 0.5
    orchestrator.beliefs = MagicMock()
    orchestrator.beliefs.list_beliefs = AsyncMock(return_value=[belief])

    single = MemoryBenchScenario(
        name="solo",
        episodes=[{"content": "Latency causes churn.", "source_type": "user"}],
        query="Why?",
        expected_concepts=["latency"],
    )
    result = await run_memorybench_with_orchestrator(orchestrator, scenarios=[single])
    assert result.overall_score == round(
        (
            result.retention_score
            + result.feedback_correction_score
            + result.hallucination_resistance_score
            + result.belief_quality_score
        )
        / 4,
        4,
    )
    assert result.details["scoring_method"] == "semantic_llm_judge"
