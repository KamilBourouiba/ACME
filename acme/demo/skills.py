"""Runtime skills for the Erebor demo squad — HTTP probes, logs, deploy status."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from acme.config import settings
from acme.demo.vm_deploy import settings_site_url

logger = logging.getLogger("acme.demo.skills")

SKILL_CATALOG = """
Available skills (agents use these every improvement turn):
- http_probe: GET live site /api/health and /api/catalog
- http_search: GET /api/search?q=... on the live VM
- http_fetch: GET any URL (staging preview path, GitHub Pages)
- deploy_status: read VM receiver last deploy result + docker build stderr
- container_logs: tail docker compose logs (api/nginx) — the "console"
- list_artifacts: inventory of files the squad has committed in-memory
- acme_query: ask ACME memory graph a technical question
- edit_file: patch or create a repo file (frontend/backend/css/js/python)
- deploy: push artifacts to VM (+ GitHub Pages when configured)
"""


@dataclass
class SkillResult:
    skill: str
    ok: bool
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_line(self) -> str:
        flag = "OK" if self.ok else "FAIL"
        return f"[{self.skill}] {flag}: {self.summary}"


class DemoSkills:
    def __init__(
        self,
        *,
        artifacts: dict[str, str],
        last_deploy: dict[str, Any] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.last_deploy = last_deploy or {}
        self._site_url = (settings.demo_vm_site_url or self.last_deploy.get("vm_url") or "").rstrip("/")
        if not self._site_url and settings.demo_vm_url:
            self._site_url = settings_site_url(settings.demo_vm_url)

    def _vm_base(self) -> str | None:
        if not settings.demo_vm_url:
            return None
        return settings.demo_vm_url.rstrip("/")

    def _vm_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.demo_vm_deploy_key}"}

    async def http_get(self, url: str, *, timeout: float = 15.0) -> SkillResult:
        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
                resp = await client.get(url)
                body = resp.text[:2500]
                return SkillResult(
                    skill="http_fetch",
                    ok=resp.status_code < 400,
                    summary=f"GET {url} → HTTP {resp.status_code} ({len(resp.text)} bytes)",
                    detail={"url": url, "status": resp.status_code, "body_preview": body},
                )
        except Exception as exc:
            return SkillResult(
                skill="http_fetch",
                ok=False,
                summary=f"GET {url} failed: {exc}",
                detail={"url": url, "error": str(exc)},
            )

    async def probe_site_health(self) -> SkillResult:
        if not self._site_url:
            return SkillResult(
                skill="http_probe",
                ok=False,
                summary="No live site URL configured yet",
                detail={},
            )
        health = await self.http_get(f"{self._site_url}/api/health")
        if not health.ok:
            health = await self.http_get(f"{self._site_url}/healthz")
        catalog = await self.http_get(f"{self._site_url}/api/catalog")
        pages_ok = self.last_deploy.get("pages_verified") is True
        ok = health.ok and (catalog.ok or pages_ok)
        return SkillResult(
            skill="http_probe",
            ok=ok,
            summary=(
                f"health={health.detail.get('status')} catalog={catalog.detail.get('status')}"
                + (" (Pages-only mode OK)" if pages_ok and not health.ok else "")
            ),
            detail={"health": health.detail, "catalog": catalog.detail, "pages_ok": pages_ok},
        )

    async def probe_receiver(self) -> SkillResult:
        base = self._vm_base()
        if not base:
            return SkillResult(
                skill="receiver_probe",
                ok=False,
                summary="VM receiver URL not configured",
                detail={},
            )
        return await self.http_get(f"{base}/health", timeout=8.0)

    async def probe_search(self, query: str = "graph intelligence") -> SkillResult:
        if not self._site_url:
            return SkillResult(skill="http_search", ok=False, summary="No live site URL", detail={})
        qs = urlencode({"q": query})
        return await self.http_get(f"{self._site_url}/api/search?{qs}", timeout=25.0)

    async def read_deploy_status(self) -> SkillResult:
        base = self._vm_base()
        if not base or not settings.demo_vm_deploy_key:
            return SkillResult(
                skill="deploy_status",
                ok=False,
                summary="VM receiver not configured",
                detail=self.last_deploy,
            )
        try:
            async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
                resp = await client.get(
                    f"{base}/deploy/status",
                    headers=self._vm_headers(),
                )
                if resp.status_code == 404:
                    return SkillResult(
                        skill="deploy_status",
                        ok=bool(self.last_deploy),
                        summary="Receiver has no /deploy/status yet — using last API deploy",
                        detail=self.last_deploy,
                    )
                resp.raise_for_status()
                data = resp.json()
                ok = data.get("ok", False)
                return SkillResult(
                    skill="deploy_status",
                    ok=ok,
                    summary=f"last deploy ok={ok}",
                    detail=data,
                )
        except Exception as exc:
            return SkillResult(
                skill="deploy_status",
                ok=False,
                summary=f"deploy status unavailable: {exc}",
                detail={"error": str(exc), "last_deploy": self.last_deploy},
            )

    async def read_container_logs(self, *, service: str = "api", tail: int = 80) -> SkillResult:
        base = self._vm_base()
        if not base or not settings.demo_vm_deploy_key:
            return SkillResult(skill="container_logs", ok=False, summary="VM not configured", detail={})
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                resp = await client.get(
                    f"{base}/logs",
                    params={"service": service, "tail": tail},
                    headers=self._vm_headers(),
                )
                if resp.status_code == 404:
                    return SkillResult(
                        skill="container_logs",
                        ok=False,
                        summary="Receiver has no /logs endpoint yet",
                        detail={},
                    )
                resp.raise_for_status()
                data = resp.json()
                lines = data.get("logs", "")[-3000:]
                return SkillResult(
                    skill="container_logs",
                    ok=True,
                    summary=f"{service} logs ({data.get('lines', 0)} lines)",
                    detail={"service": service, "logs": lines},
                )
        except Exception as exc:
            return SkillResult(
                skill="container_logs",
                ok=False,
                summary=f"logs failed: {exc}",
                detail={"error": str(exc)},
            )

    def list_artifacts(self) -> SkillResult:
        paths = sorted(self.artifacts.keys())
        preview = {p: len(self.artifacts[p]) for p in paths[:40]}
        return SkillResult(
            skill="list_artifacts",
            ok=bool(paths),
            summary=f"{len(paths)} files in squad repo",
            detail={"paths": paths, "sizes": preview},
        )

    async def gather_observations(self, *, include_logs: bool = True) -> tuple[str, list[SkillResult]]:
        results: list[SkillResult] = [self.list_artifacts()]
        results.append(await self.probe_receiver())
        results.append(await self.probe_site_health())
        results.append(await self.probe_search())
        results.append(await self.read_deploy_status())
        if include_logs:
            results.append(await self.read_container_logs(service="api", tail=60))
            results.append(await self.read_container_logs(service="nginx", tail=40))

        if self.last_deploy.get("pages_url"):
            results.append(await self.http_get(self.last_deploy["pages_url"]))

        lines = [r.to_line() for r in results]
        for r in results:
            if r.skill == "container_logs" and r.detail.get("logs"):
                lines.append(f"--- console ({r.detail.get('service')}) ---\n{r.detail['logs'][:1200]}")
            elif r.skill == "deploy_status" and r.detail.get("stderr"):
                lines.append(f"--- deploy stderr ---\n{r.detail['stderr'][:800]}")

        return "\n".join(lines), results
