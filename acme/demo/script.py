"""Scripted Slack beats — Nexus Advisory website build with peer Q&A."""

from dataclasses import dataclass

from acme.demo.agents import APP_JS, INDEX_HTML, SERVER_PY, SITE_ARTIFACTS, STYLES_CSS


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


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat(
        "general",
        "alex",
        "message",
        "Kickoff: we're shipping the Nexus Advisory consulting site by Friday — static host on GitHub Pages.",
    ),
    DemoBeat(
        "general",
        "kai",
        "message",
        "@Alex — I'll track cross-team deps. Design, eng, and QA all post blockers in-channel.",
    ),
    DemoBeat(
        "product",
        "morgan",
        "message",
        "Client wants enterprise proof points, a services grid, and one primary CTA above the fold.",
    ),
    DemoBeat(
        "product",
        "alex",
        "reply",
        "@Morgan — can we defer case-study PDFs and still hit Friday?",
        reply_to="morgan",
    ),
    DemoBeat(
        "product",
        "morgan",
        "reply",
        "@Alex yes — logo strip + 3 service cards is enough for v1 sign-off.",
        reply_to="alex",
    ),
    DemoBeat(
        "design",
        "priya",
        "message",
        "Hero: purple→blue gradient, system fonts, WCAG AA on the CTA. @Riley headline goes above the fold.",
    ),
    DemoBeat(
        "design",
        "riley",
        "reply",
        '@Priya headline locked: *Clarity for complex transformations* — subline covers SaaS, ops, and GTM.',
        reply_to="priya",
    ),
    DemoBeat(
        "design",
        "sam",
        "query",
        "What copy and layout constraints should engineering implement on the homepage?",
    ),
    DemoBeat(
        "design",
        "marco",
        "reply",
        "@Sam — copying that into the shell: gradient hero, 3-card services grid, single CTA.",
        reply_to="sam",
    ),
    DemoBeat(
        "engineering",
        "chen",
        "query",
        "Do we need a backend for v1 or is static HTML enough for the consulting landing page?",
    ),
    DemoBeat(
        "engineering",
        "sam",
        "reply",
        "@Chen static only this sprint — mock the lead form; API can land next iteration.",
        reply_to="chen",
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Initial HTML shell — hero, nav, services mount point.",
        code_file="index.html",
        code_lang="html",
        code_body=INDEX_HTML,
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Brand tokens + hero layout CSS.",
        code_file="styles.css",
        code_lang="css",
        code_body=STYLES_CSS,
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Services grid from JS array + CTA handler (posts to `/api/lead`).",
        code_file="app.js",
        code_lang="javascript",
        code_body=APP_JS,
    ),
    DemoBeat(
        "engineering",
        "chen",
        "code",
        "Lead capture API — FastAPI + asyncpg on secure Postgres VM.",
        code_file="server.py",
        code_lang="python",
        code_body=SERVER_PY,
    ),
    DemoBeat(
        "engineering",
        "chen",
        "message",
        "@Nina — backend ready for VM deploy: `/api/lead` persists to private Postgres (~1 TB).",
    ),
    DemoBeat(
        "engineering",
        "priya",
        "preview",
        "Opening staging preview — checking visual balance on hero padding and CTA contrast.",
    ),
    DemoBeat(
        "engineering",
        "jordan",
        "query",
        "What are our smoke-test acceptance criteria for mobile and desktop?",
    ),
    DemoBeat(
        "engineering",
        "jordan",
        "reply",
        "Running visual pass on staging now — hero, 3 cards, CTA alert all render correctly.",
        reply_to="jordan",
    ),
    DemoBeat(
        "product",
        "alex",
        "reply",
        "@Jordan if staging looks good, @Nina can publish to GitHub Pages autonomously.",
        reply_to="jordan",
    ),
    DemoBeat(
        "deploy",
        "nina",
        "query",
        "What files and hosting target are we publishing for Nexus Advisory?",
    ),
    DemoBeat(
        "deploy",
        "nina",
        "deploy",
        "Autonomous publish: static files to GitHub Pages + stack to secure squad VM…",
    ),
    DemoBeat(
        "deploy",
        "jordan",
        "preview",
        "Production visual check — comparing live GitHub Pages to staging preview.",
    ),
    DemoBeat(
        "general",
        "kai",
        "message",
        "Nice work — client review tomorrow AM. Each of us keeps ACME beliefs on why we chose static v1.",
    ),
    DemoBeat(
        "engineering",
        "chen",
        "reply",
        "@Sam I'll log lead-capture schema as beliefs before we wire `/api/lead` next sprint.",
        reply_to="sam",
    ),
)

DEFAULT_SITE_ARTIFACTS = SITE_ARTIFACTS
