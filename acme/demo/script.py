"""Scripted Slack beats — Nexus Advisory full-stack build with peer Q&A."""

from dataclasses import dataclass

from acme.demo.artifacts import artifact as A


@dataclass(frozen=True)
class DemoBeat:
    channel: str
    agent_id: str
    kind: str  # message | reply | query | code | deploy | preview
    content: str
    reply_to: str | None = None
    code_file: str | None = None
    code_lang: str | None = None
    code_body: str | None = None


def _code(path: str, lang: str, msg: str) -> DemoBeat:
    return DemoBeat("engineering", "marco", "code", msg, code_file=path, code_lang=lang, code_body=A(path))


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat("general", "alex", "message", "Kickoff: Nexus Advisory site — layered architecture (static + API + Postgres VM)."),
    DemoBeat("general", "sam", "message", "Architecture doc first: `static/`, `api/routes/`, nginx TLS, private SQL."),
    DemoBeat("general", "kai", "message", "@Sam tracking file-level ownership — no monolith `app.js` this sprint."),
    DemoBeat("product", "morgan", "message", "Client wants services API-driven, lead capture persisted, enterprise proof strip later."),
    DemoBeat("product", "alex", "reply", "@Morgan — v1 = modular frontend + `/api/lead` + `/api/services`.", reply_to="morgan"),
    DemoBeat("design", "priya", "message", "CSS split: tokens → layout → components. ES modules for JS."),
    DemoBeat("design", "riley", "reply", 'Headline locked: *Clarity for complex transformations*.', reply_to="priya"),
    DemoBeat("design", "sam", "query", "What frontend file structure should we implement for Nexus Advisory?"),
    DemoBeat("engineering", "sam", "reply", "@Priya `@Marco` use `static/css/*` + `static/js/{api,components,app}.js`.", reply_to="sam"),
    DemoBeat("engineering", "chen", "query", "What backend modules do we need for leads and services on the VM stack?"),
    DemoBeat("engineering", "chen", "reply", "@Sam `api/db.py`, `api/models.py`, `api/routes/{health,leads}.py`, thin `server.py`.", reply_to="chen"),
    DemoBeat("engineering", "marco", "code", "Repo architecture overview.", code_file="ARCHITECTURE.md", code_lang="markdown", code_body=A("ARCHITECTURE.md")),
    DemoBeat("engineering", "marco", "code", "Developer README.", code_file="README.md", code_lang="markdown", code_body=A("README.md")),
    _code("static/index.html", "html", "HTML shell — nav, hero, services mount, module entry."),
    _code("static/css/tokens.css", "css", "Design tokens (brand, spacing, typography)."),
    _code("static/css/layout.css", "css", "Page layout — hero grid, footer."),
    _code("static/css/components.css", "css", "Reusable UI — buttons, cards."),
    DemoBeat("engineering", "marco", "code", "Fetch wrapper for `/api/lead` and `/api/services`.", code_file="static/js/api.js", code_lang="javascript", code_body=A("static/js/api.js")),
    DemoBeat("engineering", "marco", "code", "Services grid renderer.", code_file="static/js/components.js", code_lang="javascript", code_body=A("static/js/components.js")),
    DemoBeat("engineering", "marco", "code", "App bootstrap + CTA handler.", code_file="static/js/app.js", code_lang="javascript", code_body=A("static/js/app.js")),
    DemoBeat("engineering", "chen", "code", "Env-backed settings.", code_file="api/config.py", code_lang="python", code_body=A("api/config.py")),
    DemoBeat("engineering", "chen", "code", "Asyncpg pool + migrations.", code_file="api/db.py", code_lang="python", code_body=A("api/db.py")),
    DemoBeat("engineering", "chen", "code", "Pydantic request/response models.", code_file="api/models.py", code_lang="python", code_body=A("api/models.py")),
    DemoBeat("engineering", "chen", "code", "Health route for nginx upstream checks.", code_file="api/routes/health.py", code_lang="python", code_body=A("api/routes/health.py")),
    DemoBeat("engineering", "chen", "code", "Leads + services REST routes.", code_file="api/routes/leads.py", code_lang="python", code_body=A("api/routes/leads.py")),
    DemoBeat("engineering", "chen", "code", "ASGI entry — mounts routers.", code_file="server.py", code_lang="python", code_body=A("server.py")),
    DemoBeat("engineering", "jordan", "code", "API smoke test.", code_file="tests/test_api.py", code_lang="python", code_body=A("tests/test_api.py")),
    DemoBeat("engineering", "priya", "preview", "Staging preview — multi-file CSS/JS inlined; checking hero + cards."),
    DemoBeat("engineering", "jordan", "query", "What acceptance criteria cover the full static + API architecture?"),
    DemoBeat("engineering", "jordan", "reply", "Staging pass: index, 3 CSS modules, ES modules, `/api/health` OK.", reply_to="jordan"),
    DemoBeat("product", "alex", "reply", "@Jordan if green, @Nina publishes Pages + VM stack.", reply_to="jordan"),
    DemoBeat("deploy", "nina", "query", "What files and targets are we publishing for Nexus Advisory?"),
    DemoBeat("deploy", "nina", "deploy", "Autonomous publish: `static/*` → GitHub Pages, full stack → secure squad VM…"),
    DemoBeat("deploy", "chen", "message", "VM live — `/api/lead` persisting to private Postgres (~1 TB capacity)."),
    DemoBeat("deploy", "jordan", "preview", "Production visual check — VM HTTPS vs staging preview."),
    DemoBeat("general", "kai", "message", "Shipped modular v1. Each agent keeps ACME beliefs on architecture trade-offs."),
    DemoBeat("engineering", "sam", "query", "Summarize all architecture decisions we made for Nexus Advisory v1."),
    DemoBeat("engineering", "chen", "reply", "@Sam logging lead schema + route map as beliefs for next sprint API work.", reply_to="sam"),
)

DEFAULT_SITE_ARTIFACTS = None  # use acme.demo.artifacts.SITE_ARTIFACTS
