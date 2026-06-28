"""Mutable squad registry — agents and channels can grow at runtime."""

from __future__ import annotations

import re
import uuid
from copy import deepcopy

from acme.demo.agents import DEMO_AGENTS, DemoAgent, _SKILL_SUFFIX
from acme.demo.channels import DEMO_CHANNELS, DemoChannel

_PALETTE = (
    "#611f69",
    "#1264a3",
    "#2eb67d",
    "#ecb22e",
    "#c9184a",
    "#694873",
    "#36c5f0",
    "#4a154b",
    "#0b4f6c",
    "#e01e5a",
)

_MAX_AGENTS = 24
_MAX_CHANNELS = 16


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24]
    return base or f"member-{uuid.uuid4().hex[:6]}"


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "?"


class SquadRegistry:
    def __init__(
        self,
        *,
        agents: dict[str, DemoAgent] | None = None,
        channels: dict[str, DemoChannel] | None = None,
    ) -> None:
        self.agents: dict[str, DemoAgent] = agents or {a.id: a for a in DEMO_AGENTS}
        self.channels: dict[str, DemoChannel] = channels or {c.id: c for c in DEMO_CHANNELS}

    @classmethod
    def default(cls) -> SquadRegistry:
        return cls(
            agents={a.id: a for a in DEMO_AGENTS},
            channels={c.id: c for c in DEMO_CHANNELS},
        )

    def clone(self) -> SquadRegistry:
        return SquadRegistry(agents=deepcopy(self.agents), channels=deepcopy(self.channels))

    def list_agents(self) -> list[DemoAgent]:
        return list(self.agents.values())

    def list_channels(self) -> list[DemoChannel]:
        return list(self.channels.values())

    def get_agent(self, agent_id: str) -> DemoAgent | None:
        return self.agents.get(agent_id)

    def get_channel(self, channel_id: str) -> DemoChannel | None:
        return self.channels.get(channel_id)

    def tenant_ids(self) -> tuple[str, ...]:
        return tuple(a.tenant_id for a in self.agents.values())

    def agent_dedup_messages(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if agent is None:
            return False
        return getattr(agent, "dedup_messages", False) or agent_id in {
            "nina",
            "sam",
            "jordan",
            "chen",
            "kai",
        }

    def hire_agent(
        self,
        *,
        name: str,
        role: str,
        channels: tuple[str, ...] | list[str],
        system_prompt: str | None = None,
        color: str | None = None,
        agent_id: str | None = None,
    ) -> DemoAgent:
        if len(self.agents) >= _MAX_AGENTS:
            raise ValueError(f"agent cap reached ({_MAX_AGENTS})")
        slug = agent_id or _slug(name)
        while slug in self.agents:
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        chans = tuple(channels)
        for ch in chans:
            if ch not in self.channels:
                raise ValueError(f"unknown channel: {ch}")
        pick_color = color or _PALETTE[len(self.agents) % len(_PALETTE)]
        prompt = system_prompt or (
            f"You are {name}, {role} on the Erebor squad. Ship concrete improvements." + _SKILL_SUFFIX
        )
        agent = DemoAgent(
            id=slug,
            name=name.strip(),
            role=role.strip(),
            tenant_id=f"demo-erebor-{slug}",
            color=pick_color,
            initials=_initials(name),
            system_prompt=prompt,
            channels=chans,
        )
        self.agents[slug] = agent
        return agent

    def create_channel(
        self,
        *,
        name: str,
        topic: str,
        emoji: str = "💬",
        channel_id: str | None = None,
    ) -> DemoChannel:
        if len(self.channels) >= _MAX_CHANNELS:
            raise ValueError(f"channel cap reached ({_MAX_CHANNELS})")
        slug = channel_id or _slug(name)
        while slug in self.channels:
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        channel = DemoChannel(
            id=slug,
            name=name.strip(),
            topic=topic.strip(),
            emoji=emoji or "💬",
        )
        self.channels[slug] = channel
        return channel

    def agents_for_channel(self, channel_id: str) -> list[DemoAgent]:
        return [a for a in self.agents.values() if channel_id in a.channels]
