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
from acme.demo.agents import AGENT_BY_ID, DEMO_AGENTS, DemoAgent
from acme.demo.artifacts import REFERENCE_ARTIFACTS, baseline_artifacts
from acme.demo.coding import generate_agent_code
from acme.demo.channels import CHANNEL_BY_ID, DEMO_CHANNELS
from acme.demo.github_deploy import deploy_files
from acme.demo.github_pages import github_pages_files
from acme.demo.preview import build_staging_preview
from acme.demo.reset import cleanup_all_demo_tenants
from acme.demo.vm_deploy import deploy_to_vm
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


def _index_key(artifacts: dict[str, str]) -> str | None:
    if "static/index.html" in artifacts:
        return "static/index.html"
    if "index.html" in artifacts:
        return "index.html"
    return None


def _trim_messages(messages: list["_DemoMessage"]) -> list["_DemoMessage"]:
    cap = settings.demo_message_cap
    if cap <= 0 or len(messages) <= cap:
        return messages
    return messages[-cap:]


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
    reply_to: str | None = None
    reply_to_name: str | None = None
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
            reply_to=self.reply_to,
            reply_to_name=self.reply_to_name,
            timestamp=self.timestamp,
        )


class DemoService:
    def __init__(self) -> None:
        self.running = False
        self.tick = 0
        self._beat_index = 0
        self._turn_index = 0
        self._messages: list[_DemoMessage] = []
        self._artifacts: dict[str, str] = baseline_artifacts()
        self._last_deploy: dict[str, Any] | None = None
        self._last_sessions: dict[str, str] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._last_reset_at: datetime | None = None
        self._last_publish_at: datetime | None = None
        self._preview_ready: bool = False
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
        if settings.demo_clean_on_start:
            await self._clean_state(force=True)
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
            await asyncio.sleep(max(1, settings.demo_interval_sec))

    async def _run_turn(self) -> None:
        beat = SCRIPT_BEATS[self._beat_index % len(SCRIPT_BEATS)]
        self._beat_index += 1
        self._turn_index += 1
        self.tick = self._turn_index
        agent = AGENT_BY_ID[beat.agent_id]
        reply_name = AGENT_BY_ID[beat.reply_to].name if beat.reply_to and beat.reply_to in AGENT_BY_ID else None

        content = beat.content
        if settings.demo_llm_paraphrase and beat.kind not in ("code", "preview"):
            content = await self._maybe_paraphrase(agent, beat.kind, beat.content)

        code_body = beat.code_body
        if beat.kind == "code" and beat.code_file:
            if code_body is None and settings.demo_llm_code:
                code_body = await generate_agent_code(agent, beat, artifacts=self._artifacts)
                content = f"Pushed `{beat.code_file}` — {beat.content}"
            elif code_body is None and settings.demo_code_fallback:
                code_body = REFERENCE_ARTIFACTS.get(beat.code_file, "")

        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            channel=beat.channel,
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=beat.kind,
            content=content,
            reply_to=beat.reply_to,
            reply_to_name=reply_name,
            code_file=beat.code_file,
            code_lang=beat.code_lang,
            code_body=code_body,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if beat.kind == "code" and beat.code_file and code_body:
            self._artifacts[beat.code_file] = code_body
            if _index_key(self._artifacts):
                self._preview_ready = True

        if beat.kind == "preview":
            self._preview_ready = bool(_index_key(self._artifacts))
            if self._last_deploy and self._last_deploy.get("pages_verified"):
                msg.content = f"{content} Live: {self._last_deploy.get('pages_url', '')}"

        if beat.kind == "query":
            await self._run_acme_query(beat, msg, agent)

        self._messages.append(msg)
        self._messages = _trim_messages(self._messages)

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

        if beat.kind == "deploy" and settings.demo_auto_publish:
            pub = asyncio.create_task(self._autonomous_publish(trigger_msg=msg))
            self._bg_tasks.add(pub)
            pub.add_done_callback(self._bg_tasks.discard)

    async def _run_acme_query(self, beat: DemoBeat, msg: _DemoMessage, agent: DemoAgent) -> None:
        """Run ACME query synchronously so Q&A appears in the same turn."""
        try:
            llm = get_llm_client()
            async with SessionLocal() as session:
                orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
                qr = await orch.query(QueryRequest(question=msg.content, challenge=False))
                msg.answer = qr.answer
                msg.beliefs_used = [b.model_dump() for b in qr.beliefs_used]
                self._last_sessions[agent.id] = str(qr.session_id)
                await orch.ingest_experience(
                    ExperienceCreate(
                        content=f"Q: {msg.content} A: {qr.answer}",
                        source_type=SourceType.HUMAN_EXPERT,
                        source_id=f"demo-{agent.id}",
                        tags=["demo", "erebor", beat.channel, "query"],
                        tenant_id=agent.tenant_id,
                    )
                )
                if settings.demo_channel_hearsay:
                    hearsay = f"[#{beat.channel}] {agent.name} asked: {msg.content} ACME answered: {qr.answer[:200]}"
                    for peer in DEMO_AGENTS:
                        if peer.id == agent.id or beat.channel not in peer.channels:
                            continue
                        peer_orch = ACMEOrchestrator(
                            session, neo4j_client, llm, tenant_id=peer.tenant_id
                        )
                        await peer_orch.ingest_experience(
                            ExperienceCreate(
                                content=hearsay,
                                source_type=SourceType.SYSTEM,
                                source_id=f"hearsay-query-{agent.id}",
                                tags=["demo", "peer", "query", beat.channel],
                                tenant_id=peer.tenant_id,
                            )
                        )
                await session.commit()
        except Exception:
            logger.exception("Sync ACME query failed for %s", agent.id)
            msg.answer = "(ACME query pending — graph still warming up.)"

    def build_preview_html(self) -> str:
        return build_staging_preview(self._artifacts)

    def preview_api_url(self) -> str:
        return "/api/v1/demo/preview"

    def _publish_configured(self) -> bool:
        return bool(settings.demo_github_token and settings.demo_github_repo)

    def _vm_configured(self) -> bool:
        return bool(settings.demo_vm_url and settings.demo_vm_deploy_key)

    async def _deploy_to_vm(self) -> dict[str, Any] | None:
        if not self._vm_configured() or not settings.demo_vm_auto_deploy:
            return None
        try:
            return await deploy_to_vm(
                self._artifacts,
                vm_url=settings.demo_vm_url,
                deploy_key=settings.demo_vm_deploy_key,
            )
        except Exception:
            logger.exception("VM deploy failed")
            return None

    def _publish_on_cooldown(self) -> bool:
        if self._last_publish_at is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self._last_publish_at).total_seconds()
        return elapsed < settings.demo_publish_cooldown_sec

    async def _append_agent_message(
        self,
        *,
        channel: str,
        agent_id: str,
        kind: str,
        content: str,
    ) -> _DemoMessage:
        agent = AGENT_BY_ID[agent_id]
        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            channel=channel,
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=kind,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._messages.append(msg)
        self._messages = _trim_messages(self._messages)
        return msg

    async def _autonomous_publish(self, *, trigger_msg: _DemoMessage) -> None:
        """Nina's squad publishes without visitor interaction."""
        if not self._publish_configured():
            trigger_msg.content = (
                f"{trigger_msg.content}\n\n_(GitHub token missing on server — set DEMO_GITHUB_TOKEN.)_"
            )
            state = await self.get_state()
            await self._notify({"type": "update", "state": state.model_dump()})
            return

        if self._publish_on_cooldown() and self._last_deploy:
            url = self._last_deploy.get("pages_url", "")
            follow = await self._append_agent_message(
                channel="deploy",
                agent_id="nina",
                kind="message",
                content=f"Publish cooldown active — site still live at {url}",
            )
            state = await self.get_state()
            await self._notify(
                {
                    "type": "turn",
                    "tick": self.tick,
                    "message": follow.to_out().model_dump(),
                    "state": state.model_dump(),
                }
            )
            return

        try:
            result = await self.deploy()
            self._last_publish_at = datetime.now(timezone.utc)
            trigger_msg.content = (
                f"Published {', '.join(result['files'])} to `{result['repo']}` on `{result['branch']}`."
            )
            pages_url = result["pages_url"]
            verified = result.get("pages_verified")
            status = result.get("pages_status_code")
            if verified:
                nina_msg = f"GitHub Pages reachable — site live at {pages_url} (HTTP {status})."
                jordan_msg = (
                    f"Fetched {pages_url} — found Erebor globe + OSS search shell. Pages build OK."
                )
            else:
                nina_msg = (
                    f"Pushed to GitHub; Pages URL {pages_url} not ready yet "
                    f"(HTTP {status or 'timeout'}). Build may still be propagating."
                )
                jordan_msg = f"Pages poll incomplete — retrying on next cycle. Target: {pages_url}"

            follow = await self._append_agent_message(
                channel="deploy",
                agent_id="nina",
                kind="message",
                content=nina_msg,
            )
            await self._append_agent_message(
                channel="deploy",
                agent_id="jordan",
                kind="message",
                content=jordan_msg,
            )
            await self._ingest_pages_access(pages_url, verified=bool(verified))
            vm_result = await self._deploy_to_vm()
            if vm_result:
                site = settings.demo_vm_site_url or vm_result.get("site_url", settings.demo_vm_url)
                self._last_deploy = {
                    **(self._last_deploy or {}),
                    "vm_url": site,
                    "vm_files": vm_result.get("files", []),
                }
                await self._append_agent_message(
                    channel="deploy",
                    agent_id="chen",
                    kind="message",
                    content=f"VM stack live — API + Postgres on secure host. Site: {site}",
                )
            state = await self.get_state()
            await self._notify(
                {
                    "type": "turn",
                    "tick": self.tick,
                    "message": follow.to_out().model_dump(),
                    "state": state.model_dump(),
                }
            )
        except Exception as exc:
            logger.exception("Autonomous publish failed")
            trigger_msg.content = f"{trigger_msg.content}\n\nPublish failed: {exc}"
            fail = await self._append_agent_message(
                channel="deploy",
                agent_id="sam",
                kind="message",
                content=f"Publish blocked — check repo permissions and DEMO_GITHUB_TOKEN. ({exc})",
            )
            state = await self.get_state()
            await self._notify(
                {
                    "type": "turn",
                    "tick": self.tick,
                    "message": fail.to_out().model_dump(),
                    "state": state.model_dump(),
                }
            )

    async def _process_acme(self, beat: DemoBeat, msg: _DemoMessage, agent: DemoAgent) -> None:
        try:
            llm = get_llm_client()
            async with SessionLocal() as session:
                orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
                tags = ["demo", "erebor", beat.channel]

                if beat.kind in ("message", "code", "deploy", "reply", "preview"):
                    body = beat.content
                    if beat.code_file and msg.code_body:
                        body = f"{beat.content} File: {beat.code_file}\n{msg.code_body[:500]}"
                    elif beat.code_file:
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
                    # Query already handled synchronously in _run_acme_query
                    pass

                await session.commit()

            if msg.beliefs_used and beat.kind != "query":
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

    async def _ingest_pages_access(self, pages_url: str, *, verified: bool) -> None:
        """Let DevOps/QA agents remember they accessed the live GitHub Pages site."""
        summary = (
            f"GitHub Pages site {'verified live' if verified else 'deployed but not yet verified'} "
            f"at {pages_url}"
        )
        for agent_id in ("nina", "jordan", "sam"):
            agent = AGENT_BY_ID[agent_id]
            try:
                llm = get_llm_client()
                async with SessionLocal() as session:
                    orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
                    await orch.ingest_experience(
                        ExperienceCreate(
                            content=summary,
                            source_type=SourceType.SYSTEM,
                            source_id="github-pages",
                            tags=["demo", "deploy", "pages"],
                            tenant_id=agent.tenant_id,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.exception("Pages access ingest failed for %s", agent_id)

    async def _list_beliefs_for_tenant(self, session, tenant_id: str):
        from acme.engines.belief import BeliefEngine

        engine = BeliefEngine(session, tenant_id=tenant_id)
        return await engine.list_beliefs(min_confidence=0.0, exclude_deprecated=False)

    async def get_state(
        self,
        *,
        selected_agent: str | None = None,
        selected_channel: str | None = None,
    ) -> DemoStateOut:
        agents_out: list[DemoAgentOut] = []
        async with SessionLocal() as session:
            for agent in DEMO_AGENTS:
                beliefs = await self._list_beliefs_for_tenant(session, agent.tenant_id)
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
                        beliefs=[],
                    )
                )

        sel_agent = selected_agent if selected_agent in AGENT_BY_ID else None
        sel_channel = selected_channel if selected_channel in CHANNEL_BY_ID else None
        channels_out = [
            DemoChannelOut(id=c.id, name=c.name, topic=c.topic, emoji=c.emoji) for c in DEMO_CHANNELS
        ]

        msgs = self._messages
        cap = settings.demo_state_message_cap
        if cap > 0:
            msgs = msgs[-cap:]
        return DemoStateOut(
            running=self.running and settings.demo_enabled,
            model=self.model_label(),
            tick=self.tick,
            selected_agent=sel_agent,
            selected_channel=sel_channel,
            channels=channels_out,
            agents=agents_out,
            messages=[m.to_out() for m in msgs],
            artifacts=dict(self._artifacts),
            last_deploy=self._last_deploy,
            preview_ready=self._preview_ready or bool(_index_key(self._artifacts)),
            preview_url=self.preview_api_url()
            if (self._preview_ready or _index_key(self._artifacts))
            else None,
            live_preview_url=(
                self._last_deploy.get("vm_url")
                or (
                    self._last_deploy.get("pages_url")
                    if self._last_deploy and self._last_deploy.get("pages_verified")
                    else None
                )
                if self._last_deploy
                else (settings.demo_vm_site_url or None)
            ),
        )

    async def get_agent_detail(self, agent_id: str) -> DemoAgentOut | None:
        agent = AGENT_BY_ID.get(agent_id)
        if not agent:
            return None
        async with SessionLocal() as session:
            beliefs = await self._list_beliefs_for_tenant(session, agent.tenant_id)
        return DemoAgentOut(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            tenant_id=agent.tenant_id,
            color=agent.color,
            initials=agent.initials,
            channels=list(agent.channels),
            belief_count=len(beliefs),
            beliefs=beliefs,
        )

    async def deploy(
        self,
        *,
        repo: str | None = None,
        branch: str | None = None,
        token: str | None = None,
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        auth = token or settings.demo_github_token
        if not auth:
            raise ValueError("GitHub token not configured — set DEMO_GITHUB_TOKEN or pass token")

        target_repo = repo or settings.demo_github_repo
        target_branch = branch or settings.demo_github_branch
        if not target_repo:
            raise ValueError("GitHub repo not configured — set DEMO_GITHUB_REPO or pass repo")

        result = await deploy_files(
            github_pages_files(self._artifacts),
            token=auth,
            repo=target_repo,
            branch=target_branch,
            commit_message=commit_message
            or "Autonomous publish — Erebor open intelligence graph (ACME demo squad)",
            bootstrap_repo=True,
            enable_pages=True,
        )
        self._last_deploy = {**result, "deployed_at": datetime.now(timezone.utc).isoformat()}
        vm_result = await self._deploy_to_vm()
        if vm_result:
            site = settings.demo_vm_site_url or vm_result.get("site_url", "")
            self._last_deploy = {
                **self._last_deploy,
                "vm_url": site,
                "vm_live": vm_result.get("live_ok", False),
            }
        state = await self.get_state()
        await self._notify({"type": "deploy", "deploy": self._last_deploy, "state": state.model_dump()})
        return result

    async def _clean_state(self, *, force: bool = False) -> list[dict[str, int | str]]:
        async with SessionLocal() as session:
            stats = await cleanup_all_demo_tenants(session, neo4j_client)

        self._messages.clear()
        self._last_sessions.clear()
        self._artifacts = baseline_artifacts()
        self._last_deploy = None
        self._last_publish_at = None
        self._preview_ready = False
        self._beat_index = 0
        self._turn_index = 0
        self.tick = 0
        if force:
            self._last_reset_at = None
        return stats

    async def reset(self) -> tuple[bool, str, list[dict[str, int | str]]]:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._last_reset_at is not None:
                wait = settings.demo_reset_cooldown_sec - (now - self._last_reset_at).total_seconds()
                if wait > 0:
                    return False, f"Please wait {int(wait)}s before resetting again.", []

            stats = await self._clean_state(force=False)
            self._last_reset_at = now

            if settings.demo_clean_repo_on_reset and self._publish_configured():
                try:
                    await self.deploy(
                        commit_message="Reset Erebor demo site to baseline (ACME squad clean)",
                    )
                except Exception:
                    logger.exception("Repo baseline reset failed during demo reset")
            elif self._vm_configured() and settings.demo_vm_auto_deploy:
                try:
                    await self._deploy_to_vm()
                except Exception:
                    logger.exception("VM baseline reset failed during demo reset")

        state = await self.get_state()
        await self._notify({"type": "reset", "state": state.model_dump()})
        return True, "Demo reset complete.", stats


demo_service = DemoService()
