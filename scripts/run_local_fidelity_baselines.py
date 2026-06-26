#!/usr/bin/env python3
"""Run MemoryBench v3 scenarios locally for paper-faithful baselines (Azure LLM required)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from acme.evaluation.baseline_langgraph_pkg import LangGraphPackageBaselineRunner
from acme.evaluation.baseline_memgpt import MemGPTBaselineRunner
from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.memorybench import V3_SCENARIOS
from acme.llm.factory import llm_client


async def main() -> None:
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        print("AZURE_OPENAI_API_KEY missing — skip local fidelity run", file=sys.stderr)
        sys.exit(1)

    llm = llm_client
    runners = {
        "rag_like": RAGBaselineRunner(llm),
        "memgpt_inspired": MemGPTBaselineRunner(llm),
        "langgraph_pkg": LangGraphPackageBaselineRunner(llm),
    }
    out = {}
    for name, runner in runners.items():
        result = await runner.run(scenarios=V3_SCENARIOS)
        out[name] = result.model_dump()
        print(
            f"{name}: retention={result.retention_score:.3f} "
            f"gnd={result.hallucination_resistance_score:.3f} "
            f"overall={result.overall_score:.3f}"
        )

    path = ROOT / "benchmark-results" / "fidelity-baselines-v3.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
