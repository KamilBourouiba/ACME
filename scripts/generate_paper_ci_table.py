#!/usr/bin/env python3
"""Generate LaTeX rows for MemoryBench CI table from compare export JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from acme.evaluation.benchmark_stats import bootstrap_ci, scenario_metrics

DISPLAY = {
    "acme": (r"\textbf{ACME}", True),
    "rag_baseline": ("RAG-like", False),
    "memgpt_baseline": ("MemGPT-insp.", False),
    "langgraph_baseline": ("LangGraph-sty.", False),
}


def fmt_ci(mean: float, lo: float, hi: float) -> str:
    return f"{mean:.3f} {{\\scriptsize ({lo:.2f}--{hi:.2f})}}"


def row(name: str, payload: dict, *, exclude: set[str]) -> str:
    label, bold = DISPLAY[name]
    scenarios = [
        s for s in payload.get("details", {}).get("scenarios", []) if s.get("name") not in exclude
    ]
    metrics = scenario_metrics(scenarios)
    parts: list[str] = []
    for key in ("retention", "groundedness"):
        mean, lo, hi = bootstrap_ci(metrics[key])
        cell = fmt_ci(mean, lo, hi)
        parts.append(f"\\textbf{{{cell}}}" if bold else cell)
    if name == "acme":
        fb_mean, _, _ = bootstrap_ci(metrics["feedback"])
        bel_mean, bel_lo, bel_hi = bootstrap_ci(metrics["belief"])
        parts.append(f"\\textbf{{{fb_mean:.3f}}}")
        parts.append(f"\\textbf{{{fmt_ci(bel_mean, bel_lo, bel_hi)}}}")
    else:
        parts.extend(["{---}", "{---}"])
    prefix = f"\\rowcolor{{acmerow}}\n      " if bold else ""
    body = " & ".join(parts)
    return f"{prefix}{label} & {body} \\\\"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path, help="Compare export JSON (systems dict or full job result)")
    parser.add_argument("--exclude-scenario", action="append", default=None)
    args = parser.parse_args()
    exclude = set(args.exclude_scenario or ["knowledge_update"])

    data = json.loads(args.export.read_text())
    if "result" in data:
        systems = data["result"]
    elif "systems" in data:
        systems = data["systems"]
    else:
        systems = data

    order = ["acme", "rag_baseline", "memgpt_baseline", "langgraph_baseline"]
    for name in order:
        if name in systems:
            print(row(name, systems[name], exclude=exclude))


if __name__ == "__main__":
    main()
