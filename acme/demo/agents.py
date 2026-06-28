from dataclasses import dataclass

from acme.demo.artifacts import SITE_ARTIFACTS  # noqa: F401 — re-export


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
        tenant_id="demo-lumen-alex",
        color="#611f69",
        initials="A",
        system_prompt="You are Alex, PM for Lumen's launch site. Bold product narrative, concise.",
        channels=("general", "product"),
    ),
    DemoAgent(
        id="priya",
        name="Priya",
        role="UX Designer",
        tenant_id="demo-lumen-priya",
        color="#e01e5a",
        initials="P",
        system_prompt="You are Priya, UX lead for Lumen. Dark premium UI, motion, accessibility.",
        channels=("design", "product", "general"),
    ),
    DemoAgent(
        id="marco",
        name="Marco",
        role="Frontend Engineer",
        tenant_id="demo-lumen-marco",
        color="#1264a3",
        initials="M",
        system_prompt="You are Marco, frontend dev. CSS modules, ES modules, dashboard mocks.",
        channels=("engineering", "general"),
    ),
    DemoAgent(
        id="chen",
        name="Chen",
        role="Backend Engineer",
        tenant_id="demo-lumen-chen",
        color="#0b4f6c",
        initials="C",
        system_prompt="You are Chen, backend dev. Waitlist API, metrics endpoints, Postgres.",
        channels=("engineering",),
    ),
    DemoAgent(
        id="nina",
        name="Nina",
        role="DevOps",
        tenant_id="demo-lumen-nina",
        color="#2eb67d",
        initials="N",
        system_prompt="You are Nina, DevOps. VM stack, TLS, autonomous publish pipelines.",
        channels=("deploy", "engineering"),
    ),
    DemoAgent(
        id="jordan",
        name="Jordan",
        role="QA Engineer",
        tenant_id="demo-lumen-jordan",
        color="#ecb22e",
        initials="J",
        system_prompt="You are Jordan, QA. Visual regression, pricing toggle, waitlist flows.",
        channels=("engineering", "product"),
    ),
    DemoAgent(
        id="sam",
        name="Sam",
        role="Tech Lead",
        tenant_id="demo-lumen-sam",
        color="#1d1c1d",
        initials="S",
        system_prompt="You are Sam, tech lead. Architecture trade-offs in 1-2 sentences.",
        channels=("engineering", "general", "deploy"),
    ),
    DemoAgent(
        id="riley",
        name="Riley",
        role="Content Strategist",
        tenant_id="demo-lumen-riley",
        color="#694873",
        initials="R",
        system_prompt="You are Riley, content. Enterprise copy, social proof, hero messaging.",
        channels=("design", "product"),
    ),
    DemoAgent(
        id="morgan",
        name="Morgan",
        role="Client Success",
        tenant_id="demo-lumen-morgan",
        color="#36c5f0",
        initials="Mo",
        system_prompt="You are Morgan, GTM. Relay enterprise buyer feedback on Lumen positioning.",
        channels=("product", "general"),
    ),
    DemoAgent(
        id="kai",
        name="Kai",
        role="Engineering Manager",
        tenant_id="demo-lumen-kai",
        color="#4a154b",
        initials="K",
        system_prompt="You are Kai, EM. Velocity, cross-team deps, launch readiness.",
        channels=("general", "engineering", "deploy"),
    ),
)

AGENT_BY_ID = {a.id: a for a in DEMO_AGENTS}
