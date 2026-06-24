"""Benchmark comparison — ACME vs RAG baseline."""

from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.baseline_memgpt import MemGPTBaselineRunner
from acme.evaluation.baseline_langgraph import LangGraphBaselineRunner
from acme.evaluation.memorybench import run_memorybench_with_orchestrator
from acme.llm.base import BaseLLMClient
from acme.schemas import BenchmarkComparisonResult, MemoryBenchResult


async def run_benchmark_comparison(
    orchestrator,
    llm: BaseLLMClient,
    *,
    persist: bool = True,
) -> BenchmarkComparisonResult:
    from acme.evaluation.compare_mutex import compare_slot

    tenant_id = getattr(orchestrator, "tenant_id", "default")
    async with compare_slot(tenant_id):
        return await _run_benchmark_comparison(orchestrator, llm, persist=persist)


async def _run_benchmark_comparison(
    orchestrator,
    llm: BaseLLMClient,
    *,
    persist: bool = True,
) -> BenchmarkComparisonResult:
    acme_result = await run_memorybench_with_orchestrator(orchestrator)
    rag_runner = RAGBaselineRunner(llm)
    memgpt_runner = MemGPTBaselineRunner(llm)
    langgraph_runner = LangGraphBaselineRunner(llm)

    rag_result = await rag_runner.run()
    memgpt_result = await memgpt_runner.run()
    langgraph_result = await langgraph_runner.run()

    result = BenchmarkComparisonResult(
        acme=acme_result,
        rag_baseline=rag_result,
        memgpt_baseline=memgpt_result,
        langgraph_baseline=langgraph_result,
        comparison_table=_build_table(acme_result, rag_result, memgpt_result, langgraph_result),
        export=_build_export(orchestrator, acme_result, rag_result, memgpt_result, langgraph_result),
    )
    if persist:
        from acme.evaluation.benchmark_store import save_compare_run

        tenant_id = getattr(orchestrator, "tenant_id", "default")
        await save_compare_run(orchestrator.session, result, tenant_id=tenant_id)
    return result


def _build_export(orchestrator, acme, rag, memgpt, langgraph) -> dict:
    from datetime import datetime, timezone

    from acme import __version__

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "isolation": "sandbox_per_scenario",
        "benchmark_version": "v3.1",
        "systems": {
            "acme": acme.model_dump(),
            "rag_baseline": rag.model_dump(),
            "memgpt_baseline": memgpt.model_dump(),
            "langgraph_baseline": langgraph.model_dump(),
        },
    }


def _build_table(
    acme: MemoryBenchResult,
    rag: MemoryBenchResult,
    memgpt: MemoryBenchResult,
    langgraph: MemoryBenchResult,
) -> list[dict]:
    """Compare on applicable metrics; baselines lack feedback/belief layers."""
    acme_applicable = (
        acme.retention_score + acme.hallucination_resistance_score
        + acme.feedback_correction_score + acme.belief_quality_score
    ) / 4
    rag_applicable = (rag.retention_score + rag.hallucination_resistance_score) / 2

    baselines = {
        "rag_baseline": rag,
        "memgpt_baseline": memgpt,
        "langgraph_baseline": langgraph,
    }

    rows = []
    metrics = [
        ("retention_score", False),
        ("hallucination_resistance_score", False),
        ("feedback_correction_score", True),
        ("belief_quality_score", True),
        ("overall_score", False),
        ("overall_applicable_only", False),
    ]

    for metric, acme_only in metrics:
        acme_val = acme_applicable if metric == "overall_applicable_only" else getattr(acme, metric)
        row = {"metric": metric, "acme": round(acme_val, 4), "acme_wins": True}
        for name, baseline in baselines.items():
            if metric == "overall_applicable_only":
                val = (baseline.retention_score + baseline.hallucination_resistance_score) / 2
            elif acme_only:
                val = "N/A"
            else:
                val = getattr(baseline, metric)
            row[name] = round(val, 4) if isinstance(val, float) else val
            if isinstance(val, float) and acme_val < val:
                row["acme_wins"] = False
        rows.append(row)

    return rows
