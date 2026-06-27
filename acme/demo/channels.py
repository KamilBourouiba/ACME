"""Slack-style rooms for the consulting-site build demo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoChannel:
    id: str
    name: str
    topic: str
    emoji: str


DEMO_CHANNELS: tuple[DemoChannel, ...] = (
    DemoChannel("general", "general", "Nexus Advisory website squad", "💬"),
    DemoChannel("product", "product", "Scope, milestones, client sign-off", "📋"),
    DemoChannel("design", "design", "Brand, UX, copy", "🎨"),
    DemoChannel("engineering", "engineering", "Frontend, API, tests", "⚙️"),
    DemoChannel("deploy", "deploy", "CI/CD and GitHub Pages", "🚀"),
)

CHANNEL_BY_ID = {c.id: c for c in DEMO_CHANNELS}
