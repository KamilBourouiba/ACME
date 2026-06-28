"""Push demo site artifacts to the secure squad VM."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("acme.demo.vm")

SITE_DIR = Path(__file__).resolve().parent / "site"


def _stack_files(artifacts: dict[str, str]) -> dict[str, str]:
    """Merge static artifacts with backend stack files for VM deploy."""
    stack = {
        "server.py": (SITE_DIR / "server.py").read_text(encoding="utf-8"),
        "requirements.txt": (SITE_DIR / "requirements.txt").read_text(encoding="utf-8"),
        "Dockerfile": (SITE_DIR / "Dockerfile").read_text(encoding="utf-8"),
        "docker-compose.yml": (SITE_DIR / "docker-compose.yml").read_text(encoding="utf-8"),
        "nginx.conf": (SITE_DIR / "nginx.conf").read_text(encoding="utf-8"),
    }
    for name in ("index.html", "styles.css", "app.js"):
        if name in artifacts:
            stack[name] = artifacts[name]
    return stack


async def deploy_to_vm(
    artifacts: dict[str, str],
    *,
    vm_url: str,
    deploy_key: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    base = vm_url.rstrip("/")
    deploy_url = f"{base}/deploy"
    health_url = f"{base}/health"

    files = _stack_files(artifacts)
    async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
        health = await client.get(health_url)
        health.raise_for_status()
        resp = await client.post(
            deploy_url,
            json={"files": files},
            headers={"Authorization": f"Bearer {deploy_key}"},
        )
        if resp.status_code not in (200, 202):
            logger.error("VM deploy failed: %s", resp.text)
            resp.raise_for_status()
        body = resp.json()

        site_base = (vm_url.replace(":9090", "").rstrip("/") or vm_url).replace("http://", "https://")
        for _ in range(60):
            await asyncio.sleep(5)
            try:
                live = await client.get(f"{site_base}/api/health")
                if live.status_code == 200:
                    break
            except Exception:
                continue

    return {
        "vm_url": base,
        "site_url": base.replace(":9090", "").rstrip("/") or base,
        "files": sorted(files.keys()),
        "status": body.get("status", "deployed"),
    }


async def check_vm_health(*, vm_url: str, timeout: float = 10.0) -> bool:
    base = vm_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.get(f"{base}/health")
            return resp.status_code == 200
    except Exception:
        return False
