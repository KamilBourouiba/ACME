#!/usr/bin/env python3
"""Background consolidation worker — calls ACME consolidation API on interval."""

import argparse
import asyncio
import json
import os
import sys
import time

import httpx


async def run_once(base: str, dry_run: bool) -> dict:
    async with httpx.AsyncClient(timeout=600.0) as client:
        health = await client.get(f"{base}/api/v1/health")
        health.raise_for_status()
        r = await client.post(
            f"{base}/api/v1/consolidation/run",
            json={
                "consolidate": True,
                "generate_hypotheses": True,
                "create_predictions": True,
                "forget_dry_run": dry_run,
            },
        )
        r.raise_for_status()
        return r.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description="ACME consolidation worker")
    parser.add_argument("--url", default=os.getenv("ACME_API_URL", "http://localhost:8000"))
    parser.add_argument("--interval", type=int, default=0, help="Repeat every N seconds (0=once)")
    parser.add_argument("--dry-run-forget", action="store_true", default=True)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    while True:
        try:
            result = await run_once(base, args.dry_run_forget)
            print(json.dumps(result, indent=2))
        except Exception as exc:
            print(f"Consolidation failed: {exc}", file=sys.stderr)
            if args.interval <= 0:
                return 1
        if args.interval <= 0:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
