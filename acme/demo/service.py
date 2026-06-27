"""Background Slack-style squad loop for the public demo."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from acme.config import settings
from acme.db.session import SessionLocal
from acme.demo.agents import AGENT_BY_ID, DEMO_AGENTS, SITE_ARTIFACTS, DemoAgent
from acme.demo.channels import CHANNEL_BY_ID, DEMO_CHANNELS
from acme.demo.github_deploy import deploy_files
from acme.demo.reset import cleanup_all_demo_tenants
from acme.demo.schemas import (
    DemoAgentOut,
    DemoChannelOut,
    DemoMessageOut,
    DemoStateOut,
)
from acme.demo.script import SCRIPT_BEATS, DemoBeat
from acme.graph.neo4j_client import neo4j_client
from acme.llm.factory import get_llm_client
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import ExperienceCreate, QueryRequest, SourceType

logger = logging.getLogger("acme.demo")


@dataclass
class _DemoMessage:
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
    beliefs_used: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_out(self) -> DemoMessageOut:
        return DemoMessageOut(
            id=self.id,
            channel=self.channel,
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            role=self.role,
            kind=self.kind,
            content=self.content,
            answer=self.answer,
            code_file=self.code_file,
            code_lang=self.code_lang,
            code_body=self.code_body,
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
        self._artifacts: dict[str, str] = dict(SITE_ARTIFACTS)
        self._last_deploy: dict[str, Any] | None = None
        self._last_sessions: dict[str, str] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._last_reset_at: datetime | None = None
        self._bg_tasks: set[asyncio.Task] = set()

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
        for t in list(self._bg_tasks):
            t.cancel()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.disciscard(q)

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
        await asyncio.sleep(2)
        while self.running and settings.demo_enabled:
            try:
                async with self._lock:
                    await self._run_turn()
            except Exception:
                logger.exception("Demo turn failed")
            await asyncio.sleep(max(5, settings.demo_interval_sec))

    async def _run_turn(self) -> None:
        beat = SCRIPT_BEATS[self._beat_index % len(SCRIPT_BEATS)]
        self._beat_index += 1
        self._turn_index += 1
        self.tick = self._turn_index
        agent = AGENT_BY_ID[beat.agent_id]

        content = beat.content
        if settings.demo_llm_paraphrase and beat.kind != "code":
            content = await self._maybe_paraphrase(agent, beat.kind, beat.content)

        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            channel=beat.channel,
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=beat.kind,
            content=content,
            code_file=beat.code_file,
            code_lang=beat.code_lang,
            code_body=beat.code_body,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if beat.kind == "code" and beat.code_file and beat.code_body:
            self._artifacts[beat.code_file] = beat.code_body

        self._messages.append(msg)
        if len(self._messages) > 120:
            self._messages = self._messages[-120:]

        state = await self.get_state()
        await self._notify(
            {
                "type": "turn",
                "tick": self.tick,
                "message": msg.to_out().model_dump(),
                "state": state.model_dump(),
            }
        )

        task = asyncio.create_task(self._process_acme(beat, msg, agent))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    def _track_bg(self, coro):
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    async def _process_acme(self, beat: DemoBeat, msg: _DemoMessage, agent: DemoAgent) -> None:
        try:
            llm = get_llm_client()
            async with SessionLocal() as session:
                orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
                tags = ["demo", "nexus", beat.channel]

                if beat.kind in ("message", "code", "deploy"):
                    body = beat.content
                    if beat.code_file:
                        body = f"{beat.content} File: {beat.code_file}"
                    await orch.ingest_experience(
                        ExperienceCreate(
                            content=body,
                            source_type=SourceType.HUMAN_EXPERT,
                            source_id=f"demo-{agent.id}",
                            tags=tags,
                            tenant_id=agent.tenant_id,
                        )
                    )
                    if settings.demo_channel_hearsay:
                        await self._channel_hearsay(session, llm, beat, speaker=agent, content=body)

                elif beat.kind == "query":
                    qr = await orch.query(QueryRequest(question=beat.content, challenge=False))
                    msg.answer = qr.answer
                    msg.beliefs_used = [b.model_dump() for b in qr.beliefs_used]
                    self._last_sessions[agent.id] = str(qr.session_id)

                await session.commit()

            if msg.answer or msg.beliefs_used:
                state = await self.get_state()
                await self._notify({"type": "update", "message_id": msg.id, "state": state.model_dump()})
        except Exception:
            logger.exception("Background ACME processing failed for %s", agent.id)

    async def _channel_hearsay(self, session, llm, beat: DemoBeat, *, speaker: DemoAgent, content: str) -> None:
        hearsay = f"[#{beat.channel}] {speaker.name} ({speaker.role}): {content}"
        for agent in DEMO_AGENTS:
            if agent.id == speaker.id or beat.channel not in agent.channels:
                continue
            orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
            await orch.ingest_experience(
                ExperienceCreate(
                    content=hearsay,
                    source_type=SourceType.SYSTEM,
                    source_id=f"hearsay-{speaker.id}",
                    tags=["demo", "peer", beat.channel],
                    tenant_id=agent.tenant_id,
                )
            )

    async def _maybe_paraphrase(self, agent: DemoAgent, kind: str, scripted: str) -> str:
        llm = get_llm_client()
        model = settings.demo_azure_deployment or None
        prompt = f"Rewrite this Slack {kind} in your voice (keep facts, max 2 sentences):\n{scripted}"
        try:
            return await llm.generate(
                prompt,
                system=agent.system_prompt,
                model=model,
                temperature=0.4,
                timeout=8.0,
            )
        except Exception:
            return scripted

    async def get_state(
        self,
        *,
        selected_agent: str | None = None,
        selected_channel: str | None = None,
    ) -> DemoStateOut:
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
                        initials=agent.initials,
                        channels=list(agent.channels),
                        belief_count=len(beliefs),
                        top_beliefs=beliefs[:6],
                    )
                )

        sel_agent = selected_agent if selected_agent in AGENT_BY_ID else None
        sel_channel = selected_channel if selected_channel in CHANNEL_BY_ID else None
        channels_out = [
            DemoChannelOut(id=c.id, name=c.name, topic=c.topic, emoji=c.emoji) for c in DEMO_CHANNELS
        ]

        return DemoStateOut(
            running=self.running and settings.demo_enabled,
            model=self.model_label(),
            tick=self.tick,
            selected_agent=sel_agent,
            selected_channel=sel_channel,
            channels=channels_out,
            agents=agents_out,
            messages=[m.to_out() for m in self._messages[-80:]],
            artifacts=dict(self._artifacts),
            last_deploy=self._last_deploy,
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
            initials=agent.initials,
            channels=list(agent.channels),
            belief_count=len(beliefs),
            top_beliefs=beliefs[:15],
        )

    async def deploy(
        self,
        *,
        repo: str | None = None,
        branch: str | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        auth = token or settings.demo_github_token
        if not auth:
            raise ValueError("GitHub token not configured — set DEMO_GITHUB_TOKEN or pass token")

        target_repo = repo or settings.demo_github_repo
        target_branch = branch or settings.demo_github_branch
        if not target_repo:
            raise ValueError("GitHub repo not configured — set DEMO_GITHUB_REPO or pass repo")

        result = await deploy_files(
            self._artifacts,
            token=auth,
            repo=target_repo,
            branch=target_branch,
            commit_message="Deploy Nexus Advisory site from ACME live demo",
        )
        self._last_deploy = {**result, "deployed_at": datetime.now(timezone.utc).isoformat()}
        state = await self.get_state()
        await self._notify({"type": "deploy", "deploy": self._last_deploy, "state": state.model_dump()})
        return result

    async def reset(self) -> tuple[bool, str, list[dict[str, int | str]]]:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._last_reset_at is not None:
                wait = settings.demo_reset_cooldown_sec - (now - self._last_reset_at).total_seconds()
                if wait > 0:
                    return False, f"Please wait {int(wait)}s before resetting again.", []

            async with SessionLocal() as session:
                stats = await cleanup_all_demo_tenants(session, neo4j_client)

            self._messages.clear()
            self._last_sessions.clear()
            self._artifacts = dict(SITE_ARTIFACTS)
            self._last_deploy = None
            self._beat_index = 0
            self._turn_index = 0
            self.tick = 0
            self._last_reset_at = now

        state = await self.get_state()
        await self._notify({"type": "reset", "state": state.model_dump()})
        return True, "Demo reset complete.", stats


demo_service = DemoService()
