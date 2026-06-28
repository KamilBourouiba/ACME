"""Browser UI/UX audit for Erebor — clicks, screenshots, fix handoff to builders."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

logger = logging.getLogger("acme.demo.ui_probe")

try:
    from playwright.async_api import async_playwright

    _PLAYWRIGHT = True
except ImportError:
    async_playwright = None  # type: ignore[misc, assignment]
    _PLAYWRIGHT = False

_CSS_HREF = re.compile(r"""href=["'](css/[^"']+)["']""", re.IGNORECASE)
_JS_SRC = re.compile(r"""src=["'](js/[^"']+)["']""", re.IGNORECASE)

CANONICAL_CSS = frozenset(
    {
        "css/tokens.css",
        "css/base.css",
        "css/shell.css",
        "css/omnibar.css",
        "css/panels.css",
        "css/canvas.css",
        "css/inspector.css",
        "css/timeline.css",
    }
)


@dataclass
class UiFixTask:
    agent_id: str
    file: str
    lang: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "agent_id": self.agent_id,
            "file": self.file,
            "lang": self.lang,
            "message": self.message,
        }


@dataclass
class UiAuditReport:
    ok: bool
    summary: str
    issues: list[str] = field(default_factory=list)
    screenshots: dict[str, bytes] = field(default_factory=dict)
    fix_tasks: list[UiFixTask] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def format_ui_audit_message(report: UiAuditReport, *, screenshot_base: str = "/api/v1/demo/ui-screenshot") -> str:
    lines = [report.summary]
    if report.issues:
        lines.append("*Issues*")
        lines.extend(f"• {issue}" for issue in report.issues[:8])
    if report.screenshots:
        lines.append("*Screenshots*")
        for shot_id in report.screenshots:
            lines.append(f"• `{shot_id}` → {screenshot_base}/{shot_id}.png")
    if report.fix_tasks:
        lines.append("*Handoff*")
        for task in report.fix_tasks[:4]:
            lines.append(f"→ @{task.agent_id} `{task.file}` — {task.message}")
    return "\n".join(lines)


def _fix_tasks_for_issues(issues: list[str]) -> list[UiFixTask]:
    tasks: list[UiFixTask] = []
    joined = " ".join(issues).lower()
    if "css" in joined or "404" in joined or "unstyled" in joined:
        tasks.append(
            UiFixTask(
                "priya",
                "static/css/shell.css",
                "css",
                "Fix layout/CSS regressions Taylor flagged in the UI audit.",
            )
        )
    if "search" in joined or "oss" in joined or "api" in joined:
        tasks.append(
            UiFixTask(
                "chen",
                "static/js/api.js",
                "javascript",
                "Fix search/API client failures seen during browser audit.",
            )
        )
        tasks.append(
            UiFixTask(
                "marco",
                "static/js/app.js",
                "javascript",
                "Wire search results → globe + inspector after Taylor's click-through.",
            )
        )
    if "globe" in joined or "canvas" in joined or "three" in joined or "node" in joined:
        tasks.append(
            UiFixTask(
                "marco",
                "static/js/scene.js",
                "javascript",
                "Restore Three.js globe interaction after UI audit findings.",
            )
        )
    if "omnibar" in joined or "inspector" in joined or "panel" in joined:
        tasks.append(
            UiFixTask(
                "priya",
                "static/css/omnibar.css",
                "css",
                "Polish omnibar/inspector spacing and hit targets from UX audit.",
            )
        )
    if not tasks:
        tasks.append(
            UiFixTask(
                "marco",
                "static/js/app.js",
                "javascript",
                "Address UI audit findings — polish interaction flow.",
            )
        )
    return tasks


def _benign_console(text: str) -> bool:
    t = text.lower()
    return any(
        token in t
        for token in (
            "favicon",
            "webgl",
            "gl_driver",
            "gpu stall",
            "readpixels",
            "gl_close_path",
        )
    )


async def _httpx_audit(url: str, *, label: str) -> UiAuditReport:
    issues: list[str] = []
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
        except Exception as exc:
            return UiAuditReport(
                ok=False,
                summary=f"[{label}] UI audit FAIL — could not load {url}",
                issues=[str(exc)],
                fix_tasks=_fix_tasks_for_issues([str(exc)]),
                detail={"url": url, "mode": "httpx"},
            )
        if resp.status_code >= 400:
            issues.append(f"Landing HTTP {resp.status_code}")
        html = resp.text
        if "shell.css" not in html and "layout.css" in html:
            issues.append("index references layout.css instead of canonical shell.css")
        refs = set(_CSS_HREF.findall(html)) | set(_JS_SRC.findall(html))
        for ref in sorted(refs):
            asset_url = urljoin(url, ref.split("?", 1)[0])
            try:
                head = await client.get(asset_url)
                if head.status_code >= 400:
                    issues.append(f"Asset 404: {ref}")
            except Exception as exc:
                issues.append(f"Asset fetch failed {ref}: {exc}")
        bad_css = [r for r in _CSS_HREF.findall(html) if r.split("?", 1)[0] not in CANONICAL_CSS]
        if bad_css:
            issues.append(f"Non-canonical CSS linked: {', '.join(bad_css[:3])}")
    ok = not issues
    return UiAuditReport(
        ok=ok,
        summary=f"[{label}] UI audit {'OK' if ok else 'FAIL'} (httpx) — {len(issues)} issue(s)",
        issues=issues,
        fix_tasks=_fix_tasks_for_issues(issues) if issues else [],
        detail={"url": url, "mode": "httpx"},
    )


async def _playwright_audit(url: str, *, label: str, shot_prefix: str) -> UiAuditReport:
    issues: list[str] = []
    screenshots: dict[str, bytes] = {}
    console_errors: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
        page = await context.new_page()

        def _on_console(msg):
            if msg.type in ("error", "warning"):
                text = msg.text or ""
                if text and not _benign_console(text):
                    console_errors.append(text[:200])

        page.on("console", _on_console)

        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception as exc:
            await browser.close()
            issues.append(f"Navigation failed: {exc}")
            report = UiAuditReport(
                ok=False,
                summary=f"[{label}] UI audit FAIL — navigation",
                issues=issues,
                fix_tasks=_fix_tasks_for_issues(issues),
                detail={"url": url, "mode": "playwright"},
            )
            return report

        shot_landing = f"{shot_prefix}-landing"
        screenshots[shot_landing] = await page.screenshot(full_page=False, type="png")

        selectors = {
            "search-input": "#search-input",
            "reset-view": "#btn-reset-view",
            "rotate": "#btn-rotate",
            "hud-nodes": "#hud-nodes",
        }
        for name, sel in selectors.items():
            try:
                await page.wait_for_selector(sel, timeout=8000)
            except Exception:
                issues.append(f"Missing selector: {sel}")

        try:
            await page.click("#search-input")
            await page.fill("#search-input", "python")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2500)
            shot_search = f"{shot_prefix}-search"
            screenshots[shot_search] = await page.screenshot(full_page=False, type="png")
            results = await page.locator(".search-hit, .search-group, #search-results").count()
            if results == 0:
                issues.append("Search submitted but no .search-hit results rendered")
        except Exception as exc:
            issues.append(f"Search interaction failed: {exc}")

        for btn in ("#btn-reset-view", "#btn-rotate", "#btn-arcs"):
            try:
                if await page.locator(btn).count():
                    await page.click(btn, timeout=3000)
                    await page.wait_for_timeout(400)
            except Exception as exc:
                issues.append(f"Click failed {btn}: {exc}")

        try:
            nodes_text = (await page.locator("#hud-nodes").inner_text()).strip()
            if nodes_text in ("0", "—", ""):
                issues.append(f"Globe HUD shows no linked nodes ({nodes_text!r})")
        except Exception:
            pass

        if console_errors:
            issues.append(f"Console: {console_errors[0]}")
            if len(console_errors) > 1:
                issues.append(f"+{len(console_errors) - 1} more console errors")

        await browser.close()

    ok = not issues
    return UiAuditReport(
        ok=ok,
        summary=f"[{label}] UI audit {'OK' if ok else 'FAIL'} — {len(issues)} issue(s), {len(screenshots)} screenshot(s)",
        issues=issues,
        screenshots=screenshots,
        fix_tasks=_fix_tasks_for_issues(issues) if issues else [],
        detail={"url": url, "mode": "playwright", "console_errors": console_errors[:5]},
    )


async def run_ui_audit(
    *,
    pages_url: str | None = None,
    vm_site_url: str | None = None,
    prefer_playwright: bool = True,
) -> UiAuditReport:
    """Audit live Pages (primary) and optionally VM staging."""
    targets: list[tuple[str, str]] = []
    if pages_url:
        targets.append((pages_url.rstrip("/") + "/", "pages"))
    if vm_site_url and vm_site_url.rstrip("/") not in {(pages_url or "").rstrip("/")}:
        targets.append((vm_site_url.rstrip("/") + "/", "vm"))

    if not targets:
        return UiAuditReport(
            ok=False,
            summary="UI audit skipped — no Pages or VM URL configured",
            issues=["No audit target URL"],
            detail={},
        )

    reports: list[UiAuditReport] = []
    for url, label in targets:
        if prefer_playwright and _PLAYWRIGHT:
            reports.append(await _playwright_audit(url, label=label, shot_prefix=label))
        else:
            reports.append(await _httpx_audit(url, label=label))

    merged_issues: list[str] = []
    merged_shots: dict[str, bytes] = {}
    merged_tasks: list[UiFixTask] = []
    modes: list[str] = []
    for rep in reports:
        merged_issues.extend(rep.issues)
        merged_shots.update(rep.screenshots)
        merged_tasks.extend(rep.fix_tasks)
        modes.append(rep.detail.get("mode", "?"))

    ok = all(r.ok for r in reports)
    summary = " | ".join(r.summary for r in reports)
    if not _PLAYWRIGHT and prefer_playwright:
        summary += " (install playwright for click-through audit)"

    # Dedupe fix tasks by file
    seen: set[str] = set()
    unique_tasks: list[UiFixTask] = []
    for task in merged_tasks:
        if task.file in seen:
            continue
        seen.add(task.file)
        unique_tasks.append(task)

    return UiAuditReport(
        ok=ok,
        summary=summary,
        issues=merged_issues,
        screenshots=merged_shots,
        fix_tasks=unique_tasks,
        detail={"targets": [u for u, _ in targets], "modes": modes},
    )
