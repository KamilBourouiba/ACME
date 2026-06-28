"""Slack-style rooms for the Lumen product launch demo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoChannel:
    id: str
    name: str
    topic: str
    emoji: str


DEMO_CHANNELS: tuple[DemoChannel, ...] = (
    DemoChannel("general", "general", "Lumen launch — revenue intelligence platform", "💬"),
    DemoChannel("product", "product", "Positioning, pricing, enterprise narrative", "📋"),
    DemoChannel("design", "design", "Motion, dark UI, dashboard mock", "🎨"),
    DemoChannel("engineering", "engineering", "Frontend modules, API, Postgres", "⚙️"),
    DemoChannel("deploy", "deploy", "GitHub Pages + secure VM stack", "🚀"),
)

CHANNEL_BY_ID = {c.id: c for c in DEMO_CHANNELS}
