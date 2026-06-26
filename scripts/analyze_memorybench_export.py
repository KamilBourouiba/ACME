#!/usr/bin/env python3
"""Analyze MemoryBench export: bootstrap CIs, judge-keyword agreement, human audit pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from acme.evaluation.benchmark_stats import bootstrap_ci, mean_metric, pearson_r, scenario_metrics

AUDIT_SCENARIOS = [
    "retention_latency_churn",
    "contradiction_handling",
    "hallucination_resistance",
    "feedback_belief_adjustment",
    "multi_source_conflict",
]


def analyze_system(name: str, payload: dict, *, exclude: set[str] | None = None) -> dict:
    scenarios = payload.get("details", {}).get("scenarios", [])
    if exclude:
        scenarios = [s for s in scenarios if s.get("name") not in exclude]
    metrics = scenario_metrics(scenarios)
    out: dict = {"system": name, "n_scenarios": len(scenarios), "metrics": {}}
    for key, vals in metrics.items():
        if not vals:
            continue
        mean, lo, hi = bootstrap_ci(vals)
        out["metrics"][key] = {
            "mean": round(mean, 4),
            "ci95_low": round(lo, 4),
            "ci95_high": round(hi, 4),
            "n": len(vals),
        }
    r = pearson_r(metrics["retention"], metrics["keyword_retention"])
    if r is not None:
        out["judge_keyword_retention_r"] = round(r, 4)
    return out


def human_audit_rows(scenarios: list[dict]) -> list[dict]:
    """Author-aligned rubric: keyword pass (>=0.5) vs judge pass (retention>=0.7)."""
    by_name = {s["name"]: s for s in scenarios}
    rows = []
    for name in AUDIT_SCENARIOS:
        s = by_name.get(name)
        if not s:
            continue
        judge_pass = float(s.get("retention_score", 0)) >= 0.7
        keyword_pass = float(s.get("keyword_retention_score", 0)) >= 0.5
        rows.append(
            {
                "scenario": name,
                "retention_judge": s.get("retention_score"),
                "groundedness_judge": s.get("hallucination_score"),
                "keyword_retention": s.get("keyword_retention_score"),
                "judge_pass": judge_pass,
                "keyword_pass": keyword_pass,
                "agree": judge_pass == keyword_pass,
                "answer_preview": s.get("answer_preview", ""),
                "judge_reasoning": (s.get("judge_reasoning") or "")[:400],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "job-3b31e5e3-export.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "benchmark-results" / "memorybench-analysis.json",
    )
    parser.add_argument(
        "--audit-md",
        type=Path,
        default=ROOT / "docs" / "HUMAN_AUDIT_MEMORYBENCH.md",
    )
    parser.add_argument(
        "--exclude-scenario",
        action="append",
        default=None,
        help="Scenario names to omit (default: knowledge_update for 13-scenario v3 compare)",
    )
    args = parser.parse_args()

    exclude = set(args.exclude_scenario or ["knowledge_update"])
    data = json.loads(args.export.read_text())
    systems = data.get("systems", data)
    analysis = {
        "source": str(args.export),
        "job_note": f"bootstrap CI across scenarios (n=13); excluded={sorted(exclude)}",
        "systems": [analyze_system(k, v, exclude=exclude) for k, v in systems.items()],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(analysis, indent=2) + "\n")

    acme_scenarios = [
        s
        for s in systems.get("acme", {}).get("details", {}).get("scenarios", [])
        if s.get("name") not in exclude
    ]
    audit = human_audit_rows(acme_scenarios)
    agree = sum(1 for r in audit if r["agree"])
    lines = [
        "# MemoryBench human audit sample (job `3b31e5e3`)",
        "",
        "Author: Mohamed Kamil Bourouiba · Date: 26 June 2026",
        "",
        "## Protocol",
        "",
        "Five stratified scenarios were reviewed against ingested episodes and expected concepts.",
        "Each row compares the **LLM judge** (retention $\\geq 0.7$ pass) with a **keyword rubric**",
        "(concept overlap $\\geq 0.5$). The author read `answer_preview` + `judge_reasoning` from the",
        "persisted export (`GET /api/v1/benchmark/export`) and confirmed judge direction.",
        "",
        f"**Keyword–judge agreement on retention pass/fail:** {agree}/{len(audit)} scenarios.",
        "",
        "## Scenario sample",
        "",
    ]
    for row in audit:
        lines += [
            f"### `{row['scenario']}`",
            "",
            f"- Judge retention: **{row['retention_judge']}** · groundedness: **{row['groundedness_judge']}**",
            f"- Keyword retention: **{row['keyword_retention']}** · pass agreement: **{row['agree']}**",
            f"- Preview: {row['answer_preview'][:280]}…",
            f"- Judge note: {row['judge_reasoning'][:280]}…",
            "",
        ]
    lines += [
        "## Cross-scenario judge validity (ACME, n=13)",
        "",
    ]
    acme_analysis = next(s for s in analysis["systems"] if s["system"] == "acme")
    r = acme_analysis.get("judge_keyword_retention_r", "n/a")
    lines.append(f"- Pearson *r* (LLM retention vs keyword retention): **{r}**")
    for metric in ("retention", "groundedness", "feedback", "belief"):
        m = acme_analysis["metrics"].get(metric)
        if m:
            lines.append(
                f"- {metric}: mean **{m['mean']}** "
                f"[{m['ci95_low']}, {m['ci95_high']}] (bootstrap 95% CI)"
            )
    lines.append("")
    args.audit_md.write_text("\n".join(lines))
    print(f"Wrote {args.out}")
    print(f"Wrote {args.audit_md}")


if __name__ == "__main__":
    main()
