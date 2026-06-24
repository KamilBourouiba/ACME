#!/usr/bin/env python3
"""Investor demo — 5-minute reproducible ACME cognitive loop + benchmark comparison."""

import argparse
import asyncio
import json
import os
import sys
import time

import httpx


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = os.getenv("ACME_API_KEY") or os.getenv("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


async def demo(base: str) -> None:
    base = base.rstrip("/")
    api = f"{base}/api/v1"
    headers = _headers()
    async with httpx.AsyncClient(timeout=600.0, headers=headers) as client:
        print("=== ACME Investor Demo ===\n")
        health = (await client.get(f"{api}/health")).json()
        print(f"Health: {health['status']} | LLM: {health['llm_provider']}\n")

        print("1) Multi-source ingestion (3 independent sources)")
        for ep in [
            {"content": "Customer A churned after API latency incidents.", "tags": ["latency", "churn"], "source_type": "database", "source_id": "crm-1"},
            {"content": "Customer B left following checkout timeouts.", "tags": ["latency", "churn"], "source_type": "api", "source_id": "monitor-1"},
            {"content": "Customer C cancelled after slow dashboard loads.", "tags": ["latency", "churn"], "source_type": "human_expert", "source_id": "analyst-1"},
        ]:
            await client.post(f"{api}/experiences", json=ep)
        print("   ✓ 3 episodes ingested with embeddings + graph extraction\n")

        print("2) Graph-backed query with contrarian check")
        qr = (await client.post(f"{api}/query", json={"question": "Why do customers churn?", "challenge": True})).json()
        print(f"   Answer: {qr['answer'][:180]}...")
        print(f"   Confidence: {qr['confidence']}\n")

        print("3) Contradiction feedback + belief adjustment")
        await client.post(
            f"{api}/feedback",
            json={"session_id": qr["session_id"], "outcome": "failed", "contradicts_belief": True, "feedback": "Partial — pricing also matters"},
        )
        beliefs = (await client.get(f"{api}/beliefs?min_confidence=0")).json()
        print(f"   Beliefs tracked: {len(beliefs)} | top CRS: {beliefs[0]['crs'] if beliefs else 'n/a'}\n")

        print("4) Autonomous learning + auto-predictions")
        learn = (await client.post(f"{api}/learn/run", json={"consolidate": True, "generate_hypotheses": True, "create_predictions": True, "forget_dry_run": True})).json()
        print(f"   Hypotheses: {learn['hypotheses_generated']} | Predictions: {learn['predictions_created']}\n")

        print("5) MemoryBench + baseline comparison (async)")
        started = time.time()
        job = (await client.post(f"{api}/benchmark/compare/async")).json()
        job_id = job["job_id"]
        print(f"   Job {job_id} started — polling…")
        comparison = None
        for _ in range(120):
            status = (await client.get(f"{api}/benchmark/compare/jobs/{job_id}")).json()
            if status["status"] == "completed":
                comparison = status["result"]
                break
            if status["status"] == "failed":
                raise RuntimeError(status.get("error", "compare job failed"))
            await asyncio.sleep(5)
        if comparison is None:
            raise TimeoutError("compare job did not complete within 10 minutes")
        elapsed = time.time() - started
        table = comparison["comparison_table"]
        print(f"   Completed in {elapsed:.0f}s\n")
        print(f"   {'Metric':<35} {'ACME':>8} {'RAG':>8} {'Δ':>8}")
        print("   " + "-" * 62)
        for row in table:
            print(f"   {row['metric']:<35} {row['acme']:>8.3f} {row['rag_baseline']:>8.3f} {row['delta']:>+8.3f}")
        print(f"\n   ACME overall: {comparison['acme']['overall_score']:.3f}")
        print(f"   RAG overall:  {comparison['rag_baseline']['overall_score']:.3f}")
        print("\n=== Demo complete ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("ACME_API_URL", "http://localhost:8000"))
    args = parser.parse_args()
    try:
        asyncio.run(demo(args.url))
        return 0
    except httpx.HTTPError as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
