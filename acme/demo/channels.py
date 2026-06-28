"""Slack-style rooms for the Erebor open intelligence demo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoChannel:
    id: str
    name: str
    topic: str
    emoji: str


DEMO_CHANNELS: tuple[DemoChannel, ...] = (
    DemoChannel("general", "general", "Erebor — open intelligence graph (site = product)", "💬"),
    DemoChannel("product", "product", "Palantir-adjacent UX, OSS-only data policy", "📋"),
    DemoChannel("design", "design", "Three.js globe, obsidian shell, no AI slop", "🎨"),
    DemoChannel("engineering", "engineering", "OSS API proxies, graph model, ES modules", "⚙️"),
    DemoChannel("deploy", "deploy", "GitHub Pages + secure VM stack", "🚀"),
)

CHANNEL_BY_ID = {c.id: c for c in DEMO_CHANNELS}
