"""LangGraph-style baseline — accumulated state graph of facts per session.

Reference: LangGraph agent state pattern. See docs/BASELINES.md.
"""

from dataclasses import dataclass, field
from typing import Any

from acme.evaluation.memorybench import DEFAULT_SCENARIOS, MemoryBenchScenario, _avg, _overall
from acme.evaluation.scoring import keyword_retention_score
from acme.llm.base import BaseLLMClient
from acme.schemas import MemoryBenchResult


@dataclass
class _GraphState:
    facts: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)


class LangGraphBaselineRunner:
    """Simplified LangGraph memory: append facts, linear state accumulation."""

    def __init__(self, llm: BaseLLMClient) -> None:
        self.llm = llm
        self.state = _GraphState()

    async def ingest(self, content: str) -> None:
        extraction = await self.llm.extract_knowledge(content, action=None)
        for entity in extraction.entities:
            self.state.facts.append(f"Entity: {entity.name} ({entity.entity_type})")
        for relation in extraction.relations:
            self.state.facts.append(
                f"{relation.source} {relation.relation_type} {relation.target}"
            )
            self.state.edges.append((relation.source, relation.target))
        if not self.state.facts:
            self.state.facts.append(content)

    async def query(self, question: str) -> str:
        if not self.state.facts:
            return "Insufficient memory to answer."
        memory_context = "\n".join(f"- {fact}" for fact in self.state.facts[-40:])
        result = await self.llm.reason(question=question, memory_context=memory_context)
        return result["answer"]

    async def _run_scenario(self, scenario: MemoryBenchScenario) -> dict[str, Any]:
        self.state = _GraphState()
        contents: list[str] = []
        for ep in scenario.episodes:
            await self.ingest(ep["content"])
            contents.append(ep["content"])

        answer = await self.query(scenario.query)
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
                "system": "langgraph_baseline",
                "scoring_method": "semantic_llm_judge",
                "scenarios_run": len(scenarios),
                "scenarios": results,
                "note": "LangGraph baseline has no belief/feedback layer",
            },
        )
