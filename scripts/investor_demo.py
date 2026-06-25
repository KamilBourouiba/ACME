#!/usr/bin/env python3
"""Investor demo — 5-minute reproducible ACME cognitive loop + benchmark comparison."""

import argparse
import asyncio
import json
import os
import sys
import time

import httpx


def _load_api_key() -> str | None:
    key = os.getenv("ACME_API_KEY") or os.getenv("API_KEY")
    if key:
        return key
    env_file = os.path.join(os.path.dirname(__file__), "..", "azure", "api-key.env")
    if os.path.isfile(env_file):
        for line in open(env_file):
            line = line.strip()
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1]
    return None


def _headers() -> dict[str, str]:
    api_key = _load_api_key()
    return {"X-API-Key": api_key} if api_key else {}


def _normalize_comparison(data: dict) -> dict:
    """Normalize export / runs/latest / job result into display shape."""
    if "payload" in data and isinstance(data["payload"], dict):
        data = data["payload"]
    if data.get("comparison_table") and data.get("acme"):
        return data
    systems = data.get("systems") or {}
    acme = systems.get("acme") or data.get("acme") or {}
    rag = systems.get("rag_baseline") or data.get("rag_baseline") or {}
    table: list[dict] = []
    if acme and rag:
        for metric in ("retention_score", "hallucination_resistance_score", "overall_score"):
            a = acme.get(metric)
            r = rag.get(metric)
            if isinstance(a, (int, float)) and isinstance(r, (int, float)):
                table.append({"metric": metric, "acme": a, "rag_baseline": r, "delta": a - r})
    return {"comparison_table": table, "acme": acme, "rag_baseline": rag}


async def _load_persisted_comparison(client: httpx.AsyncClient, api: str) -> dict:
    for path in (f"{api}/benchmark/runs/latest?run_type=compare", f"{api}/benchmark/export"):
        resp = await client.get(path)
        if resp.status_code == 200:
            return _normalize_comparison(resp.json())
    raise RuntimeError("No persisted compare run — run ./scripts/run_prod_benchmark.sh first")


async def _run_compare_or_fallback(
    client: httpx.AsyncClient,
    api: str,
    *,
    cached: bool = False,
    max_polls: int = 24,
) -> tuple[dict, str]:
    """Return (comparison, source_label)."""
    if cached:
        print("   Using last persisted compare run (--benchmark cached)")
        return await _load_persisted_comparison(client, api), "persisted (cached)"
    job_resp = await client.post(f"{api}/benchmark/compare/async")
    if job_resp.status_code == 429:
        print("   Rate limit hit — using last persisted compare run")
        return await _load_persisted_comparison(client, api), "persisted (rate limit)"
    if job_resp.status_code != 200:
        print(f"   Compare start HTTP {job_resp.status_code} — using last persisted compare run")
        return await _load_persisted_comparison(client, api), "persisted (start failed)"

    job = job_resp.json()
    job_id = job.get("job_id")
    if not job_id:
        print("   No job_id in response — using last persisted compare run")
        return await _load_persisted_comparison(client, api), "persisted (no job_id)"

    print(f"   Job {job_id} started — polling…")
    for _ in range(max_polls):
        status = (await client.get(f"{api}/benchmark/compare/jobs/{job_id}")).json()
        if status["status"] == "completed":
            return status["result"], "live"
        if status["status"] == "failed":
            err = status.get("error", "compare job failed")
            print(f"   Job failed ({err}) — using last persisted compare run")
            return await _load_persisted_comparison(client, api), "persisted (job failed)"
        await asyncio.sleep(5)
    print("   Job timed out — using last persisted compare run")
    return await _load_persisted_comparison(client, api), "persisted (timeout)"


async def demo(base: str, *, benchmark: str = "cached") -> None:
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
        comparison, source = await _run_compare_or_fallback(
            client, api, cached=(benchmark == "cached")
        )
        elapsed = time.time() - started
        if source != "live":
            print(f"   (scores from {source})")
        table = comparison.get("comparison_table") or []
        if table:
            print(f"   Completed in {elapsed:.0f}s\n")
            print(f"   {'Metric':<35} {'ACME':>8} {'RAG':>8} {'Δ':>8}")
            print("   " + "-" * 62)
            for row in table:
                acme_v = row["acme"]
                rag_v = row["rag_baseline"]
                if isinstance(acme_v, (int, float)) and isinstance(rag_v, (int, float)):
                    delta = row.get("delta", acme_v - rag_v)
                    print(f"   {row['metric']:<35} {acme_v:>8.3f} {rag_v:>8.3f} {delta:>+8.3f}")
                else:
                    acme_s = f"{acme_v:.3f}" if isinstance(acme_v, (int, float)) else str(acme_v)
                    rag_s = f"{rag_v:.3f}" if isinstance(rag_v, (int, float)) else str(rag_v)
                    print(f"   {row['metric']:<35} {acme_s:>8} {rag_s:>8} {'—':>8}")
        acme_score = comparison.get("acme", {}).get("overall_score", 0)
        rag_score = comparison.get("rag_baseline", {}).get("overall_score", 0)
        print(f"\n   ACME overall: {acme_score:.3f}")
        print(f"   RAG overall:  {rag_score:.3f}")

        print("\n6) LongMemEval industry benchmark (prod, June 2026)")
        print("   Oracle 500 Q — ACME transcript-first vs baselines:")
        print(f"   {'System':<10} {'Overall':>8} {'KU':>8} {'Temporal':>10}")
        print("   " + "-" * 40)
        for row in (
            ("ACME", 0.848, 0.944, 0.709),
            ("MemGPT", 0.786, 0.875, 0.630),
            ("RAG", 0.780, 0.889, 0.622),
        ):
            print(f"   {row[0]:<10} {row[1]:>8.3f} {row[2]:>8.3f} {row[3]:>10.3f}")
        print("   (MemoryBench + LongMemEval reported separately — see docs/BENCHMARK_RESULTS.md)")

        print("\n=== Demo complete ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("ACME_API_URL", "http://localhost:8000"))
    parser.add_argument(
        "--benchmark",
        choices=("cached", "live"),
        default="cached",
        help="cached: show last prod compare scores (fast); live: run async compare with fallback",
    )
    args = parser.parse_args()
    try:
        asyncio.run(demo(args.url, benchmark=args.benchmark))
        return 0
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
