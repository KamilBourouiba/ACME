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
        tenant_id="demo-nexus-alex",
        color="#611f69",
        initials="A",
        system_prompt="You are Alex, PM for Nexus Advisory's new site. Concise, milestone-focused.",
        channels=("general", "product"),
    ),
    DemoAgent(
        id="priya",
        name="Priya",
        role="UX Designer",
        tenant_id="demo-nexus-priya",
        color="#e01e5a",
        initials="P",
        system_prompt="You are Priya, UX lead. Talk layout, accessibility, and brand tone briefly.",
        channels=("design", "product", "general"),
    ),
    DemoAgent(
        id="marco",
        name="Marco",
        role="Frontend Engineer",
        tenant_id="demo-nexus-marco",
        color="#1264a3",
        initials="M",
        system_prompt="You are Marco, frontend dev. Reference components and CSS modules in short messages.",
        channels=("engineering", "general"),
    ),
    DemoAgent(
        id="chen",
        name="Chen",
        role="Backend Engineer",
        tenant_id="demo-nexus-chen",
        color="#0b4f6c",
        initials="C",
        system_prompt="You are Chen, backend dev. Mention APIs, routes, and data models briefly.",
        channels=("engineering",),
    ),
    DemoAgent(
        id="nina",
        name="Nina",
        role="DevOps",
        tenant_id="demo-nexus-nina",
        color="#2eb67d",
        initials="N",
        system_prompt="You are Nina, DevOps. Focus on deploy pipelines, VM stack, and GitHub Pages.",
        channels=("deploy", "engineering"),
    ),
    DemoAgent(
        id="jordan",
        name="Jordan",
        role="QA Engineer",
        tenant_id="demo-nexus-jordan",
        color="#ecb22e",
        initials="J",
        system_prompt="You are Jordan, QA. Flag regressions and acceptance criteria tersely.",
        channels=("engineering", "product"),
    ),
    DemoAgent(
        id="sam",
        name="Sam",
        role="Tech Lead",
        tenant_id="demo-nexus-sam",
        color="#1d1c1d",
        initials="S",
        system_prompt="You are Sam, tech lead. Unblock the team and decide trade-offs in 1-2 sentences.",
        channels=("engineering", "general", "deploy"),
    ),
    DemoAgent(
        id="riley",
        name="Riley",
        role="Content Strategist",
        tenant_id="demo-nexus-riley",
        color="#694873",
        initials="R",
        system_prompt="You are Riley, content. Ship headlines and case-study copy briefly.",
        channels=("design", "product"),
    ),
    DemoAgent(
        id="morgan",
        name="Morgan",
        role="Client Success",
        tenant_id="demo-nexus-morgan",
        color="#36c5f0",
        initials="Mo",
        system_prompt="You are Morgan, client success. Relay stakeholder feedback from Nexus Advisory.",
        channels=("product", "general"),
    ),
    DemoAgent(
        id="kai",
        name="Kai",
        role="Engineering Manager",
        tenant_id="demo-nexus-kai",
        color="#4a154b",
        initials="K",
        system_prompt="You are Kai, EM. Track velocity and cross-team dependencies briefly.",
        channels=("general", "engineering", "deploy"),
    ),
)

AGENT_BY_ID = {a.id: a for a in DEMO_AGENTS}

# Re-export for backwards compatibility
__all__ = ["DEMO_AGENTS", "AGENT_BY_ID", "DemoAgent", "SITE_ARTIFACTS"]
