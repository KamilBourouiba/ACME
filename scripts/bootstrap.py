#!/usr/bin/env python3
"""Bootstrap script — start infrastructure and verify connectivity."""

import asyncio
import subprocess
import sys

import httpx


async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"Ollama OK — models: {', '.join(models) or 'none'}")
            return True
    except Exception as exc:
        print(f"Ollama unreachable: {exc}")
        return False


async def check_api() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:8000/api/v1/health")
            data = r.json()
            print(f"API status: {data}")
            return r.status_code == 200
    except Exception as exc:
        print(f"API unreachable: {exc}")
        return False


def main() -> None:
    print("Starting Docker services (Postgres + Neo4j)...")
    subprocess.run(["docker", "compose", "up", "-d"], check=False)

    print("\nChecking Ollama...")
    ollama_ok = asyncio.run(check_ollama())
    if not ollama_ok:
        print("\nPull recommended models:")
        print("  ollama pull qwen2.5:3b")
        print("  ollama pull llama3.2:3b")

    print("\nStart the API with:")
    print("  uvicorn acme.main:app --reload --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
