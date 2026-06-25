#!/usr/bin/env python3
"""Run LongMemEval oracle evaluation for ACME vs RAG vs MemGPT."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acme.evaluation.baseline_memgpt import MemGPTBaselineRunner
from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.longmemeval import (
    ACMELongMemEvalBackend,
    MemGPTLongMemEvalBackend,
    RAGLongMemEvalBackend,
    default_dataset_path,
    run_longmemeval_comparison,
)
from acme.llm.azure_openai import AzureOpenAIClient


def _parse_types(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [t.strip() for t in raw.split(",") if t.strip()]


async def _build_acme_backend():
    from acme.config import settings
    from acme.db.session import SessionLocal
    from acme.graph.neo4j_client import neo4j_client
    from acme.llm.factory import llm_client
    from acme.orchestrator import ACMEOrchestrator

    session = SessionLocal()
    orchestrator = ACMEOrchestrator(
        session=session,
        graph=neo4j_client,
        ollama=llm_client,
        tenant_id=settings.default_tenant_id,
    )
    return ACMELongMemEvalBackend(orchestrator), session


async def main() -> int:
    parser = argparse.ArgumentParser(description="LongMemEval industry benchmark runner")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Path to longmemeval_oracle.json (default: data/longmemeval/ or fixture)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default=None,
        help="Comma-separated question types (e.g. knowledge-update,multi-session)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max questions to run")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N questions")
    parser.add_argument(
        "--systems",
        type=str,
        default="acme,rag,memgpt",
        help="Comma-separated: acme,rag,memgpt",
    )
    parser.add_argument(
        "--no-llm-judge",
        action="store_true",
        help="Use deterministic judge (CI / offline only)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmark-results" / "longmemeval-latest.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    data_path = args.data or default_dataset_path()
    if not data_path.is_file():
        print(f"Dataset not found: {data_path}", file=sys.stderr)
        print("Run: bash scripts/download_longmemeval.sh", file=sys.stderr)
        return 1

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    question_types = _parse_types(args.types)

    from acme.llm.factory import llm_client

    llm = None
    if not args.no_llm_judge:
        llm = llm_client
        if not await llm.ping():
            llm = AzureOpenAIClient()
            if not await llm.ping():
                print("No LLM available for judge — use --no-llm-judge for offline mode", file=sys.stderr)
                return 1

    backends = []
    acme_session = None
    reason_llm = llm or llm_client

    if "acme" in systems:
        acme_backend, acme_session = await _build_acme_backend()
        backends.append(acme_backend)
    if "rag" in systems:
        backends.append(RAGLongMemEvalBackend(RAGBaselineRunner(reason_llm)))
    if "memgpt" in systems:
        backends.append(MemGPTLongMemEvalBackend(MemGPTBaselineRunner(reason_llm)))

    if not backends:
        print("No systems selected", file=sys.stderr)
        return 1

    print(f"==> LongMemEval dataset: {data_path}")
    print(f"==> Systems: {[b.name for b in backends]}")
    if question_types:
        print(f"==> Types filter: {question_types}")
    if args.limit:
        print(f"==> Limit: {args.limit} (offset {args.offset})")

    payload = await run_longmemeval_comparison(
        backends,
        dataset_path=data_path,
        question_types=question_types,
        limit=args.limit,
        offset=args.offset,
        llm_judge=llm,
        use_llm_judge=not args.no_llm_judge,
    )
    payload["completed_at"] = datetime.now(timezone.utc).isoformat()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==> Summary")
    for row in payload["summary_table"]:
        print(f"  {row['system']:8s}  accuracy={row['accuracy']:.3f}  by_type={row['by_type']}")
    print(f"\n✅ Wrote {args.output}")

    if acme_session is not None:
        await acme_session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
