import pytest
from unittest.mock import AsyncMock

from acme.evaluation.baseline_langgraph import LangGraphBaselineRunner
from acme.evaluation.baseline_memgpt import MemGPTBaselineRunner
from acme.evaluation.memorybench import MemoryBenchScenario
from acme.schemas import GraphEntity, ExtractionResult


@pytest.mark.asyncio
async def test_memgpt_baseline_scenario():
    llm = AsyncMock()
    llm.reason = AsyncMock(return_value={"answer": "Latency causes churn."})
    llm.evaluate_answer_quality = AsyncMock(
        return_value={"retention_score": 0.8, "groundedness_score": 0.9, "reasoning": "ok", "judge": "llm"}
    )
    runner = MemGPTBaselineRunner(llm)
    scenario = MemoryBenchScenario(
        name="t",
        episodes=[{"content": "Latency causes churn.", "source_type": "user"}],
        query="Why?",
        expected_concepts=["latency"],
    )
    result = await runner._run_scenario(scenario)
    assert result["retention_score"] == 0.8


@pytest.mark.asyncio
async def test_langgraph_baseline_scenario():
    llm = AsyncMock()
    llm.extract_knowledge = AsyncMock(
        return_value=ExtractionResult(
            entities=[GraphEntity(name="latency", entity_type="metric")],
            relations=[],
        )
    )
    llm.reason = AsyncMock(return_value={"answer": "Latency drives churn."})
    llm.evaluate_answer_quality = AsyncMock(
        return_value={"retention_score": 0.7, "groundedness_score": 0.8, "reasoning": "ok", "judge": "llm"}
    )
    runner = LangGraphBaselineRunner(llm)
    scenario = MemoryBenchScenario(
        name="t",
        episodes=[{"content": "Latency causes churn.", "source_type": "user"}],
        query="Why?",
        expected_concepts=["latency"],
    )
    result = await runner._run_scenario(scenario)
    assert result["retention_score"] == 0.7
