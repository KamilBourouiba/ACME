"""Runtime skills for the Belief Observatory demo squad — HTTP probes, logs, deploy status."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from acme.config import settings
from acme.demo.site_guard import javascript_syntax_ok, live_matches_canon
from acme.demo.vm_deploy import settings_site_url
from acme.demo.vm_exec import REMEDIATION_RECIPES, exec_on_vm, run_recipe

logger = logging.getLogger("acme.demo.skills")

SKILL_CATALOG = """
Available skills (agents use these every improvement turn):
- http_probe: GET /api/health, /api/trace, and verify live js/app.js matches canon
- http_search: GET /api/search?q=... on the live VM
- http_fetch: GET any URL (staging preview path, GitHub Pages)
- deploy_status: read VM receiver last deploy result + docker build stderr
- container_logs: tail docker compose logs (api/nginx) — the "console"
- list_artifacts: inventory of files the squad has committed in-memory
- acme_query: ask ACME memory graph a technical question
- edit_file: patch or create a repo file (frontend/backend/css/js/python)
- deploy: push artifacts to VM (+ GitHub Pages when configured)
- deploy_static: static/ files publish at site root — HTML uses css/ and js/ paths, NOT /static/
- triage: Vera consolidates failing probes into one incident report (dedupes spam)
- ui_audit: Taylor clicks through live Pages/VM — screenshots, console errors, hands fixes to Marco/Priya/Chen
- vm_exec: run allowlisted curl/docker/systemctl on the VM via receiver POST /exec
- vm_remediate: Vera runs a fix recipe (compose restart, health curls, receiver restart)
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

    async def probe_static_shell(self) -> SkillResult:
        if not self._site_url:
            return SkillResult(
                skill="static_shell",
                ok=False,
                summary="No live site URL configured yet",
                detail={},
            )
        root = await self.http_get(f"{self._site_url}/")
        css = await self.http_get(f"{self._site_url}/css/observatory.css")
        body = root.detail.get("body_preview") or ""
        ok = root.ok and css.ok
        return SkillResult(
            skill="static_shell",
            ok=ok,
            summary=f"root={root.detail.get('status')} observatory.css={css.detail.get('status')}",
            detail={"root": root.detail, "css": css.detail},
        )

    async def probe_frontend_js(self) -> SkillResult:
        if not self._site_url:
            return SkillResult(
                skill="frontend_js",
                ok=False,
                summary="No live site URL configured yet",
                detail={},
            )
        app = await self.http_get(f"{self._site_url}/js/app.js")
        api = await self.http_get(f"{self._site_url}/js/api.js")
        app_body = app.detail.get("body_preview") or ""
        if app.ok and len(app_body) < 500:
            # body_preview is truncated — fetch full file for hash/syntax check
            full = await self.http_get(f"{self._site_url}/js/app.js")
            app_body = full.detail.get("body_preview") or app_body
        async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as client:
            try:
                resp = await client.get(f"{self._site_url}/js/app.js")
                app_body = resp.text if resp.status_code < 400 else app_body
                api_resp = await client.get(f"{self._site_url}/js/api.js")
                api_body = api_resp.text if api_resp.status_code < 400 else ""
            except Exception as exc:
                return SkillResult(
                    skill="frontend_js",
                    ok=False,
                    summary=f"fetch js failed: {exc}",
                    detail={},
                )
        syntax_ok = javascript_syntax_ok("static/js/app.js", app_body)
        canon_ok = live_matches_canon(app_body, "static/js/app.js")
        api_ok = live_matches_canon(api_body, "static/js/api.js") if api_body else False
        ok = app.ok and syntax_ok and canon_ok and api_ok
        return SkillResult(
            skill="frontend_js",
            ok=ok,
            summary=(
                f"app.js http={app.detail.get('status')} syntax={syntax_ok} canon={canon_ok} "
                f"api_canon={api_ok} bytes={len(app_body)}"
            ),
            detail={
                "app_status": app.detail.get("status"),
                "syntax_ok": syntax_ok,
                "canon_ok": canon_ok,
                "api_canon_ok": api_ok,
                "bytes": len(app_body),
            },
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
        trace = await self.probe_trace()
        shell = await self.probe_static_shell()
        frontend = await self.probe_frontend_js()
        pages_ok = self.last_deploy.get("pages_verified") is True and frontend.ok
        api_ok = health.ok and trace.ok and frontend.ok
        ok = shell.ok and api_ok
        return SkillResult(
            skill="http_probe",
            ok=ok,
            summary=(
                f"health={health.detail.get('status')} static={shell.detail.get('root', {}).get('status')} "
                f"trace={trace.detail.get('status')} frontend={frontend.detail.get('syntax_ok')}"
            ),
            detail={
                "health": health.detail,
                "trace": trace.detail,
                "static_shell": shell.detail,
                "frontend_js": frontend.detail,
                "pages_ok": pages_ok,
            },
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

    async def probe_trace(self) -> SkillResult:
        if not self._site_url:
            return SkillResult(skill="http_trace", ok=False, summary="No live site URL", detail={})
        return await self.http_get(f"{self._site_url}/api/trace", timeout=15.0)

    async def probe_search(self, query: str = "graph intelligence") -> SkillResult:
        """Legacy alias — belief observatory uses /api/trace, not search."""
        return await self.probe_trace()

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

    async def vm_exec(self, command: str, *, timeout: float = 45.0) -> SkillResult:
        result = await exec_on_vm(command, timeout=timeout)
        ok = bool(result.get("ok")) and result.get("returncode", 1) == 0
        err = result.get("error")
        return SkillResult(
            skill="vm_exec",
            ok=ok and not err,
            summary=(
                f"exec exit={result.get('returncode')} "
                + (err or (result.get("stdout") or "")[:80].replace("\n", " "))
            )[:160],
            detail=result,
        )

    async def vm_remediate(self, recipe: str) -> SkillResult:
        if recipe not in REMEDIATION_RECIPES:
            return SkillResult(
                skill="vm_remediate",
                ok=False,
                summary=f"unknown recipe: {recipe}",
                detail={"recipe": recipe, "available": list(REMEDIATION_RECIPES.keys())},
            )
        result = await run_recipe(recipe)
        ok = bool(result.get("ok")) and result.get("returncode", 1) == 0
        return SkillResult(
            skill="vm_remediate",
            ok=ok,
            summary=f"{recipe} exit={result.get('returncode')}",
            detail=result,
        )

    async def gather_observations(self, *, include_logs: bool = True) -> tuple[str, list[SkillResult]]:
        results: list[SkillResult] = [self.list_artifacts()]
        parallel = await asyncio.gather(
            self.probe_receiver(),
            self.probe_site_health(),
            self.probe_static_shell(),
            self.probe_frontend_js(),
            self.probe_search(),
            self.read_deploy_status(),
            return_exceptions=True,
        )
        for item in parallel:
            if isinstance(item, SkillResult):
                results.append(item)
            elif isinstance(item, Exception):
                results.append(
                    SkillResult(
                        skill="http_probe",
                        ok=False,
                        summary=str(item),
                        detail={},
                    )
                )
        if include_logs:
            log_results = await asyncio.gather(
                self.read_container_logs(service="api", tail=60),
                self.read_container_logs(service="nginx", tail=40),
                return_exceptions=True,
            )
            for item in log_results:
                if isinstance(item, SkillResult):
                    results.append(item)

        if self.last_deploy.get("pages_url"):
            results.append(await self.http_get(self.last_deploy["pages_url"]))

        lines = [r.to_line() for r in results]
        for r in results:
            if r.skill == "container_logs" and r.detail.get("logs"):
                lines.append(f"--- console ({r.detail.get('service')}) ---\n{r.detail['logs'][:1200]}")
            elif r.skill == "deploy_status" and r.detail.get("stderr"):
                lines.append(f"--- deploy stderr ---\n{r.detail['stderr'][:800]}")

        return "\n".join(lines), results

    async def ui_audit(self) -> SkillResult:
        from acme.demo.ui_probe import run_ui_audit

        pages = (self.last_deploy or {}).get("pages_url")
        report = await run_ui_audit(
            pages_url=pages,
            vm_site_url=self._site_url or None,
        )
        return SkillResult(
            skill="ui_audit",
            ok=report.ok,
            summary=report.summary,
            detail={
                **report.detail,
                "issues": report.issues,
                "fix_tasks": [t.to_dict() for t in report.fix_tasks],
                "screenshot_ids": list(report.screenshots.keys()),
            },
        )
