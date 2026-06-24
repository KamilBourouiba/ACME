#!/usr/bin/env python3
"""Run MemoryBench against a live ACME API."""

import argparse
import json
import sys
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MemoryBench on ACME API")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)",
    )
    parser.add_argument("--timeout", type=float, default=600.0, help="Request timeout seconds")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    health_url = f"{base}/api/v1/health"
    bench_url = f"{base}/api/v1/benchmark/memorybench"

    print(f"Checking health: {health_url}")
    with httpx.Client(timeout=30.0) as client:
        for attempt in range(30):
            try:
                r = client.get(health_url)
                if r.status_code == 200:
                    health = r.json()
                    print(json.dumps(health, indent=2))
                    if not health.get("postgres"):
                        print("Postgres not ready, retrying...", file=sys.stderr)
                        time.sleep(5)
                        continue
                    break
            except httpx.HTTPError as exc:
                print(f"Health check failed ({exc}), retrying...", file=sys.stderr)
            time.sleep(5)
        else:
            print("API did not become healthy in time", file=sys.stderr)
            return 1

        print(f"\nRunning MemoryBench (timeout={args.timeout}s): {bench_url}")
        started = time.time()
        r = client.post(bench_url, timeout=args.timeout)
        elapsed = time.time() - started

        if r.status_code != 200:
            print(f"MemoryBench failed: HTTP {r.status_code}", file=sys.stderr)
            print(r.text, file=sys.stderr)
            return 1

        result = r.json()
        print(f"\nMemoryBench completed in {elapsed:.1f}s\n")
        print(json.dumps(result, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
