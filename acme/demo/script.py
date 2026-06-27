"""Scripted Slack beats — Nexus Advisory website build."""

from dataclasses import dataclass

from acme.demo.agents import APP_JS, INDEX_HTML, SITE_ARTIFACTS, STYLES_CSS


@dataclass(frozen=True)
class DemoBeat:
    channel: str
    agent_id: str
    kind: str  # message | code | query | deploy
    content: str
    code_file: str | None = None
    code_lang: str | None = None
    code_body: str | None = None


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat(
        "general",
        "alex",
        "message",
        "Kickoff: we're shipping a marketing site for Nexus Advisory (consulting SaaS) by Friday — GitHub Pages + contact form.",
    ),
    DemoBeat(
        "product",
        "morgan",
        "message",
        "Client wants proof of enterprise clients, a services grid, and a single CTA above the fold.",
    ),
    DemoBeat(
        "design",
        "priya",
        "message",
        "Hero uses purple→blue gradient, system font stack, WCAG AA contrast on the CTA button.",
    ),
    DemoBeat(
        "design",
        "riley",
        "message",
        "Headline draft: *Clarity for complex transformations* — sub: boutique consulting for SaaS, ops, GTM.",
    ),
    DemoBeat(
        "engineering",
        "sam",
        "query",
        "What layout and copy decisions have we locked for the Nexus homepage?",
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Pushed initial static shell — hero + services grid placeholder.",
        code_file="index.html",
        code_lang="html",
        code_body=INDEX_HTML,
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Brand tokens and hero layout CSS.",
        code_file="styles.css",
        code_lang="css",
        code_body=STYLES_CSS,
    ),
    DemoBeat(
        "engineering",
        "chen",
        "message",
        "Contact API can stay mocked for v1 — form posts to `/api/lead` later; static demo is fine for Pages.",
    ),
    DemoBeat(
        "engineering",
        "marco",
        "code",
        "Services grid rendered from a small JS array — easy to extend.",
        code_file="app.js",
        code_lang="javascript",
        code_body=APP_JS,
    ),
    DemoBeat(
        "engineering",
        "jordan",
        "message",
        "Smoke test: hero renders, 3 service cards, CTA click shows acknowledgment — all green on mobile width.",
    ),
    DemoBeat(
        "product",
        "alex",
        "message",
        "Scope freeze: no blog, no auth — just landing + CTA. Ship artifacts to GitHub when green.",
    ),
    DemoBeat(
        "deploy",
        "nina",
        "deploy",
        "Autonomous publish: pushing `index.html`, `styles.css`, `app.js` to GitHub Pages now…",
    ),
    DemoBeat(
        "general",
        "kai",
        "message",
        "Velocity looks good — 3 files, static host, client review tomorrow AM.",
    ),
    DemoBeat(
        "deploy",
        "sam",
        "message",
        "Remember: each of us keeps an ACME tenant — my graph tracks why we chose static over SSR for this sprint.",
    ),
    DemoBeat(
        "general",
        "priya",
        "message",
        "Added note in #design: increase hero padding on tablet — Marco can tweak in the next CSS pass.",
    ),
    DemoBeat(
        "engineering",
        "chen",
        "message",
        "If we add lead capture later, I'll store schema as beliefs before wiring the API.",
    ),
)

# Re-export for deploy endpoint
DEFAULT_SITE_ARTIFACTS = SITE_ARTIFACTS
