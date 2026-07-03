"""Scripted beats — Belief Observatory bootstrap."""

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
    code_body: str | None = None


def _code(agent: str, path: str, lang: str, msg: str) -> DemoBeat:
    return DemoBeat("engineering", agent, "code", msg, code_file=path, code_lang=lang)


SCRIPT_BEATS: tuple[DemoBeat, ...] = (
    DemoBeat("general", "alex", "message", "Kickoff: *Belief Observatory* — the website shows ACME's belief lifecycle in one investigation trace."),
    DemoBeat("deploy", "nina", "message", "📌 Static paths: `css/foo.css` and `js/bar.js` at site root — never `/static/`."),
    DemoBeat("product", "alex", "message", "Story: episodic stream → hypothesis → contradiction → feedback → promoted belief with CRS."),
    DemoBeat("design", "priya", "message", "Layout: episodes left, SVG graph center, inspector right, scrubber bottom."),
    _code("priya", "static/css/observatory.css", "css", "Observatory dark shell + responsive stack."),
    DemoBeat("engineering", "marco", "message", "Pinned canonical shell: index.html + js/api.js + js/app.js + trace-fallback.json from reference."),
    _code("chen", "api/belief_data.py", "python", "Canonical trace — latency/churn investigation."),
    _code("chen", "api/routes/beliefs.py", "python", "GET /api/trace"),
    _code("chen", "api/routes/health.py", "python", "Health — product: belief-observatory."),
    _code("chen", "server.py", "python", "Mount beliefs router."),
    DemoBeat("qa", "taylor", "message", "UI audit duty: scrubber, CRS animation, mobile column stack."),
    DemoBeat("deploy", "nina", "deploy", "Publish Belief Observatory static → GitHub Pages + VM."),
    DemoBeat("general", "alex", "message", "Observatory v1 — memory you can audit, not just retrieve."),
)
