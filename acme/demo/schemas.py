"""Public demo API schemas."""

from typing import Any

from pydantic import BaseModel, Field

from acme.schemas import BeliefScore


class DemoChannelOut(BaseModel):
    id: str
    name: str
    topic: str
    emoji: str


class DemoMessageOut(BaseModel):
    id: str
    channel: str
    agent_id: str
    agent_name: str
    role: str
    kind: str
    content: str
    answer: str | None = None
    code_file: str | None = None
    code_lang: str | None = None
    code_body: str | None = None
    beliefs_used: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str


class DemoAgentOut(BaseModel):
    id: str
    name: str
    role: str
    tenant_id: str
    color: str
    initials: str
    channels: list[str]
    belief_count: int = 0
    top_beliefs: list[BeliefScore] = Field(default_factory=list)


class DemoStateOut(BaseModel):
    running: bool
    model: str
    tick: int
    scenario: str = "nexus-advisory-site"
    selected_agent: str | None = None
    selected_channel: str | None = None
    channels: list[DemoChannelOut]
    agents: list[DemoAgentOut]
    messages: list[DemoMessageOut]
    artifacts: dict[str, str] = Field(default_factory=dict)
    last_deploy: dict[str, Any] | None = None


class DemoResetOut(BaseModel):
    ok: bool
    tenants_reset: int
    stats: list[dict[str, int | str]]


class DemoDeployIn(BaseModel):
    repo: str | None = None
    branch: str | None = None
    token: str | None = None


class DemoDeployOut(BaseModel):
    ok: bool
    repo: str
    branch: str
    files: list[str]
    pages_url: str
    commit_message: str
