"""Slack-style rooms for the Belief Observatory demo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoChannel:
    id: str
    name: str
    topic: str
    emoji: str


DEMO_CHANNELS: tuple[DemoChannel, ...] = (
    DemoChannel("general", "general", "Belief Observatory — site is the product", "💬"),
    DemoChannel("product", "product", "CRS, belief lifecycle, MemoryBench narrative", "📋"),
    DemoChannel("design", "design", "Observatory UX — episodes, graph, inspector, scrubber", "🎨"),
    DemoChannel("engineering", "engineering", "Trace API, SVG graph, belief state", "⚙️"),
    DemoChannel("deploy", "deploy", "GitHub Pages + VM static publish", "🚀"),
    DemoChannel("ops", "ops", "Probes, triage, VM health", "🩺"),
    DemoChannel("qa", "qa", "Taylor — UI audit on belief trace flows", "🖱️"),
)

CHANNEL_BY_ID = {c.id: c for c in DEMO_CHANNELS}
