"""Public demo API schemas."""

from typing import Any

from pydantic import BaseModel, Field

from acme.schemas import BeliefScore


class DemoMessageOut(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    role: str
    kind: str
    content: str
    answer: str | None = None
    beliefs_used: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str


class DemoAgentOut(BaseModel):
    id: str
    name: str
    role: str
    tenant_id: str
    color: str
    belief_count: int = 0
    top_beliefs: list[BeliefScore] = Field(default_factory=list)


class DemoStateOut(BaseModel):
    running: bool
    model: str
    tick: int
    selected_agent: str | None = None
    agents: list[DemoAgentOut]
    messages: list[DemoMessageOut]


class DemoResetOut(BaseModel):
    ok: bool
    tenants_reset: int
    stats: list[dict[str, int | str]]
