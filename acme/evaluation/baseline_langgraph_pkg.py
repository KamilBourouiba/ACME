"""LangGraph package baseline — optional official StateGraph when `langgraph` is installed.

Falls back to LangGraphBaselineRunner if the package is unavailable.
"""

from __future__ import annotations

from typing import Any

from acme.evaluation.baseline_langgraph import LangGraphBaselineRunner
from acme.evaluation.memorybench import MemoryBenchScenario, _avg, _overall
from acme.evaluation.scoring import keyword_retention_score
from acme.llm.base import BaseLLMClient
from acme.schemas import MemoryBenchResult

try:
    from langgraph.graph import END, StateGraph
    from typing_extensions import TypedDict

    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False


if _HAS_LANGGRAPH:

    class _AgentState(TypedDict):
        facts: list[str]
        last_answer: str

    class LangGraphPackageBaselineRunner:
        """Official LangGraph StateGraph accumulating extracted facts."""

        def __init__(self, llm: BaseLLMClient) -> None:
            self.llm = llm
            self._facts: list[str] = []

            async def ingest_node(state: _AgentState) -> _AgentState:
                return state

            async def answer_node(state: _AgentState) -> _AgentState:
                if not state["facts"]:
                    return {**state, "last_answer": "Insufficient memory to answer."}
                ctx = "\n".join(f"- {f}" for f in state["facts"][-40:])
                result = await self.llm.reason(question=self._question, memory_context=ctx)
                return {**state, "last_answer": str(result["answer"])}

            graph = StateGraph(_AgentState)
            graph.add_node("answer", answer_node)
            graph.set_entry_point("answer")
            graph.add_edge("answer", END)
            self._graph = graph.compile()

        async def ingest(self, content: str) -> None:
            extraction = await self.llm.extract_knowledge(content, action=None)
            for entity in extraction.entities:
                self._facts.append(f"Entity: {entity.name} ({entity.entity_type})")
            for relation in extraction.relations:
                self._facts.append(
                    f"{relation.source} {relation.relation_type} {relation.target}"
                )
            if not self._facts:
                self._facts.append(content)

        async def _run_scenario(self, scenario: MemoryBenchScenario) -> dict[str, Any]:
            self._facts = []
            contents: list[str] = []
            for ep in scenario.episodes:
                await self.ingest(ep["content"])
                contents.append(ep["content"])

            self._question = scenario.query
            state = await self._graph.ainvoke({"facts": list(self._facts), "last_answer": ""})
            answer = state["last_answer"]
            concepts = scenario.expected_concepts or scenario.expected_keywords
            evaluation = await self.llm.evaluate_answer_quality(
                question=scenario.query,
                answer=answer,
                reference_concepts=concepts,
                source_episodes=contents,
            )
            return {
                "name": scenario.name,
                "retention_score": evaluation["retention_score"],
                "keyword_retention_score": keyword_retention_score(
                    answer, scenario.expected_keywords or concepts
                ),
                "feedback_score": 0.0,
                "hallucination_score": evaluation["groundedness_score"],
                "belief_quality_score": 0.0,
                "answer_preview": answer[:200],
            }

        async def run(
            self,
            scenarios: list[MemoryBenchScenario] | None = None,
        ) -> MemoryBenchResult:
            from acme.evaluation.memorybench import DEFAULT_SCENARIOS

            scenarios = scenarios or DEFAULT_SCENARIOS
            results = [await self._run_scenario(s) for s in scenarios]
            retention = _avg([r["retention_score"] for r in results])
            hallucination = _avg([r["hallucination_score"] for r in results])
            return MemoryBenchResult(
                retention_score=retention,
                feedback_correction_score=0.0,
                hallucination_resistance_score=hallucination,
                belief_quality_score=0.0,
                overall_score=_overall(retention, 0.0, hallucination, 0.0),
                details={
                    "system": "langgraph_package_baseline",
                    "scoring_method": "semantic_llm_judge",
                    "scenarios_run": len(scenarios),
                    "scenarios": results,
                    "note": "Official langgraph StateGraph runner; no belief/feedback layer",
                },
            )

else:
    LangGraphPackageBaselineRunner = LangGraphBaselineRunner  # type: ignore[misc,assignment]
