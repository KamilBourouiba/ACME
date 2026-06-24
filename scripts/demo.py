#!/usr/bin/env python3
"""End-to-end demo of the ACME learning loop."""

import asyncio
import json

import httpx

BASE = "http://localhost:8000/api/v1"


async def demo() -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        health = await client.get(f"{BASE}/health")
        print("Health:", health.json())

        experiences = [
            {
                "content": "Customer A complained about API latency during peak hours. Response time exceeded 2s.",
                "action": "investigate latency",
                "tags": ["latency", "customer"],
            },
            {
                "content": "Customer B churned after repeated timeout errors on checkout endpoint.",
                "action": "analyze churn",
                "tags": ["latency", "churn"],
            },
            {
                "content": "Customer C reported slow dashboard loading — traced to database query bottleneck.",
                "action": "optimize queries",
                "tags": ["latency", "database"],
            },
        ]

        for exp in experiences:
            r = await client.post(f"{BASE}/experiences", json=exp)
            print(f"Ingested: {r.json()['id']}")

        query = {
            "question": "What causes customer failures in our system?",
            "challenge": True,
        }
        r = await client.post(f"{BASE}/query", json=query)
        result = r.json()
        print("\nQuery result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        feedback = {
            "session_id": result["session_id"],
            "outcome": "success",
            "feedback": "Analysis confirmed latency as root cause",
        }
        r = await client.post(f"{BASE}/feedback", json=feedback)
        print("\nFeedback:", r.json())

        r = await client.get(f"{BASE}/beliefs")
        print("\nBeliefs:", json.dumps(r.json(), indent=2, ensure_ascii=False))

        r = await client.post(
            f"{BASE}/compress",
            json={"tags": ["latency"], "min_episodes": 3, "min_confidence": 0.5},
        )
        print("\nCompression:", json.dumps(r.json(), indent=2, ensure_ascii=False))

        r = await client.post(
            f"{BASE}/forget/run",
            json={"dry_run": True, "delete_enabled": False},
        )
        print("\nForgetting (dry run):", json.dumps(r.json(), indent=2, ensure_ascii=False))

        r = await client.post(
            f"{BASE}/learn/run",
            json={"consolidate": True, "generate_hypotheses": True, "forget_dry_run": True},
        )
        print("\nAutonomous learning:", json.dumps(r.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(demo())
