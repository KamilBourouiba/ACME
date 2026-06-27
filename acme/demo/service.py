"""Background multi-agent conversation loop for the public demo."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from acme.config import settings
from acme.db.session import SessionLocal
from acme.demo.agents import AGENT_BY_ID, DEMO_AGENTS, DemoAgent
from acme.demo.schemas import DemoAgentOut, DemoMessageOut, DemoStateOut
from acme.graph.neo4j_client import neo4j_client
from acme.llm.factory import get_llm_client
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import ExperienceCreate, FeedbackRequest, QueryRequest, SourceType

logger = logging.getLogger("acme.demo")

# Scripted beats ensure the demo works even if the LLM is slow; LLM paraphrases when available.
SCRIPT_BEATS: list[tuple[str, str, str]] = [
    (
        "analyst",
        "statement",
        "Enterprise dashboard p95 latency reached 4.2s; two churn tickets cite slow loads.",
    ),
    (
        "skeptic",
        "statement",
        "We shipped dark mode the same week — latency might not be the only story.",
    ),
    (
        "lead",
        "query",
        "What factors are we tracking that relate to enterprise churn?",
    ),
    (
        "analyst",
        "statement",
        "Checkout API timeouts spiked 40% before the Acme Corp cancellation.",
    ),
    (
        "skeptic",
        "feedback",
        "Customer success says pricing drove the SMB churn, not latency alone.",
    ),
    (
        "lead",
        "query",
        "Does latency cause churn for enterprise accounts?",
    ),
    (
        "analyst",
        "statement",
        "Multi-source review: latency incidents precede churn in enterprise, not SMB.",
    ),
    (
        "skeptic",
        "statement",
        "I'll downgrade confidence until we see a controlled experiment.",
    ),
]


@dataclass
class _DemoMessage:
    id: str
    agent_id: str
    agent_name: str
    role: str
    kind: str
    content: str
    answer: str | None = None
    beliefs_used: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_out(self) -> DemoMessageOut:
        return DemoMessageOut(
            id=self.id,
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            role=self.role,
            kind=self.kind,
            content=self.content,
            answer=self.answer,
            beliefs_used=self.beliefs_used,
            timestamp=self.timestamp,
        )


class DemoService:
    def __init__(self) -> None:
        self.running = False
        self.tick = 0
        self._beat_index = 0
        self._turn_index = 0
        self._messages: list[_DemoMessage] = []
        self._last_sessions: dict[str, str] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def model_label(self) -> str:
        if settings.demo_azure_deployment:
            return settings.demo_azure_deployment
        return settings.azure_openai_deployment or settings.llm_provider

    async def start(self) -> None:
        if not settings.demo_enabled:
            return
        if self._task and not self._task.done():
            return
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="acme-demo-loop")
        logger.info("Demo loop started (interval=%ss, model=%s)", settings.demo_interval_sec, self.model_label())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=32)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def _notify(self, event: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    async def _loop(self) -> None:
        await asyncio.sleep(5)
        while self.running and settings.demo_enabled:
            try:
                async with self._lock:
                    await self._run_turn()
            except Exception:
                logger.exception("Demo turn failed")
            await asyncio.sleep(max(15, settings.demo_interval_sec))

    async def _run_turn(self) -> None:
        agent_id, kind, scripted = SCRIPT_BEATS[self._beat_index % len(SCRIPT_BEATS)]
        self._beat_index += 1
        self._turn_index += 1
        self.tick = self._turn_index
        agent = AGENT_BY_ID[agent_id]

        content = await self._maybe_paraphrase(agent, kind, scripted)
        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=kind,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        llm = get_llm_client()
        demo_model = settings.demo_azure_deployment or None

        async with SessionLocal() as session:
            orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)

            if kind == "statement":
                await orch.ingest_experience(
                    ExperienceCreate(
                        content=content,
                        source_type=SourceType.HUMAN_EXPERT,
                        source_id=f"demo-{agent.id}",
                        tags=["demo", "latency", "churn"],
                        tenant_id=agent.tenant_id,
                    )
                )
                await self._broadcast_hearsay(session, llm, speaker=agent, content=content, model=demo_model)

            elif kind == "query":
                qr = await orch.query(QueryRequest(question=content, challenge=agent.id == "skeptic"))
                msg.answer = qr.answer
                msg.beliefs_used = [b.model_dump() for b in qr.beliefs_used]
                self._last_sessions[agent.id] = str(qr.session_id)

            elif kind == "feedback":
                target = AGENT_BY_ID["lead"]
                lead_orch = ACMEOrchestrator(
                    session, neo4j_client, llm, tenant_id=target.tenant_id
                )
                await lead_orch.ingest_experience(
                    ExperienceCreate(
                        content=content,
                        source_type=SourceType.HUMAN_EXPERT,
                        source_id="demo-customer-success",
                        tags=["pricing", "churn", "contradiction"],
                        tenant_id=target.tenant_id,
                    )
                )
                session_id = self._last_sessions.get("lead")
                if session_id:
                    try:
                        await lead_orch.feedback(
                            FeedbackRequest(
                                session_id=uuid.UUID(session_id),
                                outcome="failed",
                                contradicts_belief=True,
                            )
                        )
                    except ValueError:
                        pass

            await session.commit()

        self._messages.append(msg)
        if len(self._messages) > 80:
            self._messages = self._messages[-80:]

        state = await self.get_state()
        await self._notify({"type": "turn", "tick": self.tick, "message": msg.to_out().model_dump(), "state": state.model_dump()})

    async def _broadcast_hearsay(
        self,
        session,
        llm,
        *,
        speaker: DemoAgent,
        content: str,
        model: str | None,
    ) -> None:
        hearsay = f"{speaker.name} ({speaker.role}) said: {content}"
        for agent in DEMO_AGENTS:
            if agent.id == speaker.id:
                continue
            orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
            await orch.ingest_experience(
                ExperienceCreate(
                    content=hearsay,
                    source_type=SourceType.SYSTEM,
                    source_id=f"hearsay-{speaker.id}",
                    tags=["demo", "peer"],
                    tenant_id=agent.tenant_id,
                )
            )
        del model  # reserved for future per-call model override on ingest

    async def _maybe_paraphrase(self, agent: DemoAgent, kind: str, scripted: str) -> str:
        if not settings.demo_llm_paraphrase:
            return scripted
        llm = get_llm_client()
        model = settings.demo_azure_deployment or None
        prompt = (
            f"Rewrite this {kind} in your voice (keep facts, max 2 sentences):\n{scripted}"
        )
        try:
            return await llm.generate(
                prompt,
                system=agent.system_prompt,
                model=model,
                temperature=0.4,
                timeout=45.0,
            )
        except Exception:
            logger.warning("Demo paraphrase failed — using scripted line")
            return scripted

    async def get_state(self, *, selected_agent: str | None = None) -> DemoStateOut:
        agents_out: list[DemoAgentOut] = []
        async with SessionLocal() as session:
            for agent in DEMO_AGENTS:
                from acme.engines.belief import BeliefEngine

                engine = BeliefEngine(session, tenant_id=agent.tenant_id)
                beliefs = await engine.list_beliefs(min_confidence=0.0)
                agents_out.append(
                    DemoAgentOut(
                        id=agent.id,
                        name=agent.name,
                        role=agent.role,
                        tenant_id=agent.tenant_id,
                        color=agent.color,
                        belief_count=len(beliefs),
                        top_beliefs=beliefs[:8],
                    )
                )

        sel = selected_agent if selected_agent in AGENT_BY_ID else None
        return DemoStateOut(
            running=self.running and settings.demo_enabled,
            model=self.model_label(),
            tick=self.tick,
            selected_agent=sel,
            agents=agents_out,
            messages=[m.to_out() for m in self._messages[-40:]],
        )

    async def get_agent_detail(self, agent_id: str) -> DemoAgentOut | None:
        agent = AGENT_BY_ID.get(agent_id)
        if not agent:
            return None
        async with SessionLocal() as session:
            from acme.engines.belief import BeliefEngine

            engine = BeliefEngine(session, tenant_id=agent.tenant_id)
            beliefs = await engine.list_beliefs(min_confidence=0.0)
        return DemoAgentOut(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            tenant_id=agent.tenant_id,
            color=agent.color,
            belief_count=len(beliefs),
            top_beliefs=beliefs[:20],
        )


demo_service = DemoService()
