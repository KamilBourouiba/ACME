import pytest
from unittest.mock import AsyncMock

from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.memorybench import DEFAULT_SCENARIOS, MemoryBenchScenario


@pytest.mark.asyncio
async def test_rag_baseline_single_scenario():
    llm = AsyncMock()
    llm.reason = AsyncMock(return_value={"answer": "Latency causes churn due to slow API."})
    llm.evaluate_answer_quality = AsyncMock(
        return_value={"retention_score": 0.9, "groundedness_score": 0.85, "reasoning": "ok", "judge": "llm"}
    )

    runner = RAGBaselineRunner(llm)
    scenario = MemoryBenchScenario(
        name="test",
        episodes=[{"content": "Latency causes churn.", "source_type": "user"}],
        query="Why churn?",
        expected_concepts=["latency", "churn"],
    )
    result = await runner._run_scenario(scenario)
    assert result["retention_score"] == 0.9
    llm.reason.assert_called_once()


def test_default_scenarios_count():
    assert len(DEFAULT_SCENARIOS) >= 10
