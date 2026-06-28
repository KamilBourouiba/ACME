"""Scripted Slack beats — Lumen revenue platform launch."""

from dataclasses import dataclass

from acme.demo.artifacts import artifact as A


@dataclass(frozen=True)
class DemoBeat:
    channel: str
    agent_id: str
    kind: str
    content: str
    reply_to: str | None = None
    code_file: str | None = None
    code_lang: str | None = None
    code_body: str | None = None


def _code(agent: str, path: str, lang: str, msg: str) -> DemoBeat:
    return DemoBeat("engineering", agent, "code", msg, code_file=path, code_lang=lang, code_body=A(path))


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat("general", "alex", "message", "Kickoff: *Lumen* — premium revenue intelligence launch site. Dark UI, dashboard mock, waitlist API."),
    DemoBeat("general", "riley", "message", "Positioning: *Revenue clarity for modern GTM* — not another generic BI tool."),
    DemoBeat("product", "morgan", "message", "Buyers want: animated hero, live dashboard preview, pricing toggle, enterprise trust strip."),
    DemoBeat("product", "alex", "reply", "@Morgan — v1 ships hero + 6 features + 3-tier pricing + waitlist.", reply_to="morgan"),
    DemoBeat("design", "priya", "message", "Visual system: near-black canvas, cyan→violet gradient, floating dashboard mock with motion."),
    DemoBeat("design", "sam", "query", "What visual and UX patterns should define the Lumen marketing experience?"),
    DemoBeat("design", "priya", "reply", "@Sam gradient mesh hero, glass KPI cards, animated stat counters, pricing card elevation.", reply_to="sam"),
    DemoBeat("engineering", "chen", "query", "What API surface do we need beyond a static marketing page?"),
    DemoBeat("engineering", "sam", "reply", "@Chen `/api/waitlist`, `/api/features`, `/api/pricing`, `/api/metrics` on Postgres VM.", reply_to="chen"),
    _code("marco", "ARCHITECTURE.md", "markdown", "Architecture — static modules + API routes + VM deploy."),
    _code("marco", "static/css/tokens.css", "css", "Design tokens — dark theme palette + gradient."),
    _code("marco", "static/css/base.css", "css", "Base layout, nav, typography."),
    _code("priya", "static/css/hero.css", "css", "Hero grid, badge, stat row."),
    _code("priya", "static/css/dashboard-mock.css", "css", "CSS-only dashboard preview with KPI + chart."),
    _code("priya", "static/css/features.css", "css", "Feature cards + logo strip."),
    _code("priya", "static/css/pricing.css", "css", "Pricing toggle + tier cards + waitlist form."),
    _code("priya", "static/css/animations.css", "css", "Float + fade-up motion."),
    _code("marco", "static/index.html", "html", "Full page — hero, features, pricing, waitlist."),
    _code("marco", "static/js/api.js", "javascript", "API client — waitlist, features, pricing, metrics."),
    _code("marco", "static/js/hero.js", "javascript", "Animated stat counters."),
    _code("marco", "static/js/features.js", "javascript", "Feature grid renderer."),
    _code("marco", "static/js/pricing.js", "javascript", "Monthly/annual pricing toggle."),
    _code("marco", "static/js/app.js", "javascript", "App bootstrap + waitlist handler."),
    _code("chen", "api/config.py", "python", "Feature catalog, pricing tiers, platform metrics."),
    _code("chen", "api/db.py", "python", "Postgres pool + waitlist schema."),
    _code("chen", "api/models.py", "python", "Pydantic schemas."),
    _code("chen", "api/routes/health.py", "python", "Health check."),
    _code("chen", "api/routes/platform.py", "python", "Features, pricing, metrics, waitlist routes."),
    _code("chen", "server.py", "python", "ASGI entry — mount routers."),
    _code("jordan", "tests/test_api.py", "python", "API smoke test."),
    DemoBeat("engineering", "priya", "preview", "Staging preview — checking gradient hero, dashboard mock float, pricing cards."),
    DemoBeat("engineering", "jordan", "query", "What are acceptance criteria for the Lumen launch site?"),
    DemoBeat("engineering", "jordan", "reply", "Hero animates, 6 features render, pricing toggles, waitlist POST succeeds.", reply_to="jordan"),
    DemoBeat("deploy", "nina", "query", "What are we publishing and where for Lumen?"),
    DemoBeat("deploy", "nina", "deploy", "Autonomous publish: static/ → GitHub Pages, full stack → secure VM…"),
    DemoBeat("deploy", "chen", "message", "VM live — waitlist persisting to private Postgres, `/api/features` serving catalog."),
    DemoBeat("deploy", "jordan", "preview", "Production check — HTTPS dashboard mock + waitlist on live VM."),
    DemoBeat("general", "kai", "message", "Lumen v1 shipped. Squad logs ACME beliefs on every architecture call we made."),
    DemoBeat("product", "morgan", "query", "Summarize why Lumen's site architecture impresses enterprise buyers."),
)
