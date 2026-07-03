from dataclasses import dataclass

from acme.demo.artifacts import SITE_ARTIFACTS  # noqa: F401 — re-export

_SKILL_SUFFIX = (
    " You have runtime skills: HTTP probes, deploy, ACME memory queries, file edits, ui_audit."
    " HTML links use css/foo.css and js/bar.js — NEVER /static/ prefix."
    " Boot files (server.py, api/routes/*) are pinned — edit static/ only."
)


@dataclass(frozen=True)
class DemoAgent:
    id: str
    name: str
    role: str
    tenant_id: str
    color: str
    initials: str
    system_prompt: str
    channels: tuple[str, ...]


DEMO_AGENTS: tuple[DemoAgent, ...] = (
    DemoAgent(
        id="alex",
        name="Alex",
        role="Product Manager",
        tenant_id="demo-belief-alex",
        color="#611f69",
        initials="A",
        system_prompt="You are Alex, PM for Belief Observatory. The site IS ACME's product story — auditable beliefs, not RAG cosplay." + _SKILL_SUFFIX,
        channels=("general", "product"),
    ),
    DemoAgent(
        id="priya",
        name="Priya",
        role="UX Designer",
        tenant_id="demo-belief-priya",
        color="#e01e5a",
        initials="P",
        system_prompt="You are Priya, UX lead. Observatory shell: episodic stream, SVG belief graph, CRS scrubber — cinematic dark UI.",
        channels=("design", "product", "general"),
    ),
    DemoAgent(
        id="marco",
        name="Marco",
        role="Frontend Engineer",
        tenant_id="demo-belief-marco",
        color="#1264a3",
        initials="M",
        system_prompt="You are Marco. You ship observatory.css, app.js, SVG graph interactions — polished ES modules.",
        channels=("engineering", "general"),
    ),
    DemoAgent(
        id="chen",
        name="Chen",
        role="Backend Engineer",
        tenant_id="demo-belief-chen",
        color="#0b4f6c",
        initials="C",
        system_prompt="You are Chen. FastAPI /api/trace, belief_data.py, CRS payloads — no OSS proxies." + _SKILL_SUFFIX,
        channels=("engineering",),
    ),
    DemoAgent(
        id="nina",
        name="Nina",
        role="DevOps",
        tenant_id="demo-belief-nina",
        color="#2eb67d",
        initials="N",
        system_prompt="You are Nina. Publish static/ to GitHub Pages and VM after meaningful changes." + _SKILL_SUFFIX,
        channels=("deploy", "engineering"),
    ),
    DemoAgent(
        id="jordan",
        name="Jordan",
        role="QA Engineer",
        tenant_id="demo-belief-jordan",
        color="#ecb22e",
        initials="J",
        system_prompt="You are Jordan. http_probe, /api/health, /api/trace JSON checks." + _SKILL_SUFFIX,
        channels=("engineering", "product"),
    ),
    DemoAgent(
        id="taylor",
        name="Taylor",
        role="UI/UX QA Lead",
        tenant_id="demo-belief-taylor",
        color="#ff6b35",
        initials="T",
        system_prompt=(
            "You are Taylor. Run ui_audit on live Pages + VM: belief-svg, scrubber, CRS meter, mobile stack."
            " Hand off to Marco/Priya/Chen — audit first."
        )
        + _SKILL_SUFFIX,
        channels=("qa", "design", "engineering"),
    ),
    DemoAgent(
        id="vera",
        name="Vera",
        role="SRE · Debug & Triage",
        tenant_id="demo-belief-vera",
        color="#c9184a",
        initials="V",
        system_prompt="You are Vera. Probes, logs, VM exec recipes — keep belief-observatory stack green." + _SKILL_SUFFIX,
        channels=("ops", "deploy", "engineering"),
    ),
)

AGENT_BY_ID = {a.id: a for a in DEMO_AGENTS}
