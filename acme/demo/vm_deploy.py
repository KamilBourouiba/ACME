"""Push demo site artifacts to the secure squad VM."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("acme.demo.vm")

from acme.demo.site_guard import DEPLOY_PINNED_FILES, safe_site_artifact

from acme.demo.static_assets import vm_static_bundle

SITE_DIR = Path(__file__).resolve().parent / "site"
INFRA_NAMES = DEPLOY_PINNED_FILES


def _stack_files(artifacts: dict[str, str]) -> dict[str, str]:
    """Merge squad artifacts with infra files from site/ — infra always wins."""
    stack: dict[str, str] = dict(artifacts)
    for name in INFRA_NAMES:
        path = SITE_DIR / name
        if path.is_file():
            stack[name] = path.read_text(encoding="utf-8")
    return stack


async def deploy_to_vm(
    artifacts: dict[str, str],
    *,
    vm_url: str,
    deploy_key: str,
    timeout: float = 300.0,
) -> dict[str, Any]:
    base = vm_url.rstrip("/")
    deploy_url = f"{base}/deploy"
    health_url = f"{base}/health"
    site_https = settings_site_url(vm_url)

    files = _stack_files(vm_static_bundle(artifacts))
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

        live_ok = False
        for _ in range(72):
            await asyncio.sleep(5)
            try:
                live = await client.get(f"{site_https}/api/health")
                if live.status_code == 200 and "ok" in live.text:
                    live_ok = True
                    break
            except Exception:
                continue

    return {
        "vm_url": base,
        "site_url": site_https,
        "files": sorted(files.keys()),
        "status": body.get("status", "deployed"),
        "live_ok": live_ok,
    }


def settings_site_url(vm_url: str) -> str:
    from acme.config import settings

    if settings.demo_vm_site_url:
        return settings.demo_vm_site_url.rstrip("/")
    host = vm_url.replace("http://", "").replace("https://", "").split(":")[0]
    return f"https://{host}"


async def check_vm_health(*, vm_url: str, timeout: float = 10.0) -> bool:
    base = vm_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.get(f"{base}/health")
            return resp.status_code == 200
    except Exception:
        return False
