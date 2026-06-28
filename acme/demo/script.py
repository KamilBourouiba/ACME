"""Scripted Slack beats — Erebor open intelligence platform (agents write code via LLM)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoBeat:
    channel: str
    agent_id: str
    kind: str
    content: str
    reply_to: str | None = None
    code_file: str | None = None
    code_lang: str | None = None
    code_body: str | None = None  # None = agent generates at runtime


def _code(agent: str, path: str, lang: str, msg: str) -> DemoBeat:
    return DemoBeat("engineering", agent, "code", msg, code_file=path, code_lang=lang)


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat("general", "alex", "message", "Kickoff: *Erebor* — open Palantir. The website *is* the product. Three.js graph + real OSS APIs."),
    DemoBeat("deploy", "nina", "message", "📌 *Squad lesson — static paths*: files live in `static/` but index.html links `css/foo.css` and `js/bar.js` — **never** `/static/`. Pages + VM both serve static/ at site root."),
    DemoBeat("engineering", "marco", "message", "📌 Frontend rule: root-relative assets only. Jordan checks css+js return 200 before we call deploy done."),
    DemoBeat("ops", "vera", "message", "📌 Stack rule: `server.py` + `api/routes/*` are pinned — improve `static/` only; broken API syntax crashes the VM."),
    DemoBeat("general", "morgan", "message", "Investigators need: omnibar search, globe graph, entity inspector, investigation trail."),
    DemoBeat("product", "riley", "message", "Data policy: *only* open APIs — GitHub REST, OpenAlex (CC0), Nominatim (ODbL). No proprietary feeds."),
    DemoBeat("product", "alex", "reply", "@Riley v1 ships unified search + seed graph + Three.js canvas. Site replaces any separate app.", reply_to="riley"),
    DemoBeat("design", "priya", "message", "Visual bar: obsidian shell, IBM Plex, subtle grid — *not* purple gradient AI slop."),
    DemoBeat("design", "sam", "query", "What Three.js patterns keep Erebor feeling premium vs generic WebGL demos?"),
    DemoBeat("design", "priya", "reply", "@Sam icosahedron wireframe globe, emissive node spheres, quadratic arc links, OrbitControls damping.", reply_to="sam"),
    DemoBeat("engineering", "chen", "query", "Which open-source APIs do we proxy for unified search?"),
    DemoBeat("engineering", "sam", "reply", "@Chen GitHub `/search/repositories`, OpenAlex `/works`, Nominatim geocode — httpx async fan-out.", reply_to="chen"),
    _code("marco", "ARCHITECTURE.md", "markdown", "Architecture — product shell, OSS proxies, Three.js scene."),
    _code("marco", "static/css/tokens.css", "css", "Obsidian palette + accent tokens."),
    _code("marco", "static/css/base.css", "css", "Typography — IBM Plex Sans/Mono."),
    _code("priya", "static/css/shell.css", "css", "App shell grid — header, workspace, timeline."),
    _code("priya", "static/css/omnibar.css", "css", "Investigation omnibar + search results."),
    _code("priya", "static/css/panels.css", "css", "Entity list panel."),
    _code("priya", "static/css/canvas.css", "css", "Canvas HUD + loading veil."),
    _code("priya", "static/css/inspector.css", "css", "Entity inspector — stats, relations, source link."),
    _code("priya", "static/css/timeline.css", "css", "Investigation trail timeline."),
    _code("marco", "static/index.html", "html", "Product shell — canvas, panels, importmap for Three.js r170."),
    _code("marco", "static/js/api.js", "javascript", "API client — catalog, graph, search, trail."),
    _code("marco", "static/js/scene.js", "javascript", "Three.js globe — instanced nodes, arc links, raycast select."),
    _code("marco", "static/js/panels.js", "javascript", "Entity list, inspector, search results renderer."),
    _code("marco", "static/js/timeline.js", "javascript", "Investigation trail state."),
    _code("marco", "static/js/app.js", "javascript", "Bootstrap — wires scene, search, panels."),
    _code("chen", "api/config.py", "python", "OSS source catalog + seed graph nodes."),
    _code("chen", "api/oss_clients.py", "python", "httpx wrappers — GitHub, OpenAlex, Nominatim."),
    _code("chen", "api/models.py", "python", "Pydantic schemas for catalog, graph, search, trail."),
    _code("chen", "api/db.py", "python", "Postgres — investigation_trail table."),
    _code("chen", "api/routes/health.py", "python", "Health check — product: erebor."),
    _code("chen", "api/routes/intelligence.py", "python", "/catalog, /graph, /search, /trail routes."),
    _code("chen", "server.py", "python", "ASGI entry — mount intelligence router."),
    _code("jordan", "tests/test_api.py", "python", "API smoke — catalog, seed graph, health."),
    DemoBeat("engineering", "priya", "preview", "Staging preview — globe nodes, omnibar, inspector panel."),
    DemoBeat("engineering", "jordan", "query", "Acceptance criteria for Erebor v1?"),
    DemoBeat("engineering", "jordan", "reply", "Search fans out to 3 OSS APIs, nodes appear on globe, inspector shows stats + source link.", reply_to="jordan"),
    DemoBeat("qa", "taylor", "message", "I'm on *UI audit* duty — click-through on live Pages, screenshots, console errors. Builders ship after my handoff."),
    DemoBeat("qa", "kai", "reply", "@Taylor perfect — you audit, Marco/Priya/Chen fix. Jordan keeps HTTP probes.", reply_to="taylor"),
    DemoBeat("deploy", "nina", "query", "Publish targets for Erebor?"),
    DemoBeat("deploy", "nina", "deploy", "Autonomous publish: static/ → GitHub Pages, full stack + OSS proxies → secure VM…"),
    DemoBeat("deploy", "chen", "message", "VM live — `/api/search` proxying GitHub + OpenAlex + Nominatim, trail persisting to Postgres."),
    DemoBeat("deploy", "jordan", "preview", "Production — Three.js globe + live OSS search on HTTPS VM."),
    DemoBeat("general", "kai", "message", "Erebor v1 shipped. Open intelligence graph — site is the product."),
    DemoBeat("product", "morgan", "query", "Why does Erebor feel Palantir-grade while staying 100% open source?"),
)
