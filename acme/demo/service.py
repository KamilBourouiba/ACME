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
from acme.demo.agents import DemoAgent
from acme.demo.artifacts import baseline_artifacts, empty_artifacts
from acme.demo.coding import generate_agent_code
from acme.demo.channels import DemoChannel
from acme.demo.github_deploy import delete_repo, deploy_files, wipe_repo
from acme.demo.github_pages import github_pages_files
from acme.demo.preview import build_staging_preview
from acme.demo.improvement import ImprovementPlan, _fallback_plan, plan_improvement
from acme.demo.site_guard import is_pinned_on_deploy, is_protected_site_file, reference_site_files, safe_site_artifact
from acme.demo.reset import ALL_DEMO_TENANT_IDS, cleanup_all_demo_tenants
from acme.demo.skills import DemoSkills
from acme.demo.remediation import RemediationState, execute_remediation, format_remediation_message
from acme.demo.triage import (
    failure_signature,
    format_triage_report,
    is_spam_duplicate,
    normalize_message,
)
from acme.demo.vm_deploy import deploy_to_vm
from acme.demo.schemas import (
    DemoAgentOut,
    DemoChannelOut,
    DemoMessageOut,
    DemoStateOut,
    DemoVisitorSayOut,
    DemoVisitorUnlockOut,
    DemoPauseOut,
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
        self._artifacts: dict[str, str] = empty_artifacts()
        self._last_deploy: dict[str, Any] | None = None
        self._last_sessions: dict[str, str] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._last_reset_at: datetime | None = None
        self._last_publish_at: datetime | None = None
        self._preview_ready: bool = False
        self._bg_tasks: set[asyncio.Task] = set()
        self._last_visitor_say_at: datetime | None = None
        self._visitor_turn: int = 0
        self._registry = SquadRegistry.default()
        self._belief_counts: dict[str, int] = {
            a.id: 0 for a in self._registry.list_agents()
        }
        self._belief_fetch_tick: int = -999
        self._recycling: bool = False
        self._paused: bool = False
        self._phase: str = "bootstrap"
        self._improvement_turn: int = 0
        self._publish_lock = asyncio.Lock()
        self._deploy_paused: bool = False
        self._deploy_paused_reason: str | None = None
        self._consecutive_deploy_failures: int = 0
        self._consecutive_vm_probe_failures: int = 0
        self._deploy_blocked_until: datetime | None = None
        self._recent_message_norms: list[str] = []
        self._last_agent_post_at: dict[str, datetime] = {}
        self._last_plan_signature: str | None = None
        self._repeat_plan_count: int = 0
        self._last_triage_signature: str | None = None
        self._last_triage_tick: int = -999
        self._remediation = RemediationState()
        self._observation_task: asyncio.Task | None = None
        self._observations_text: str = ""
        self._observations_results: list = []
        self._observations_at: datetime | None = None
        self._turn_busy = asyncio.Lock()

    def _pin_code_artifact(self, path: str, body: str) -> str:
        """Boot-critical files always use the canonical site/ copy; reject syntax errors."""
        return safe_site_artifact(path, body, previous=self._artifacts.get(path.replace("\\", "/")))

    async def pause(self) -> DemoPauseOut:
        async with self._lock:
            self._paused = True
            self._phase = "paused"
        state = await self.get_state()
        await self._notify({"type": "pause", "state": state.model_dump()})
        return DemoPauseOut(ok=True, paused=True, phase=self._phase)

    async def resume(self) -> DemoPauseOut:
        async with self._lock:
            self._paused = False
            if self._beat_index >= len(SCRIPT_BEATS):
                self._phase = "improve"
            else:
                self._phase = "bootstrap"
        state = await self.get_state()
        await self._notify({"type": "resume", "state": state.model_dump()})
        return DemoPauseOut(ok=True, paused=False, phase=self._phase)

    @staticmethod
    def _visitor_wants_stop_deploy(text: str) -> bool:
        lower = text.lower()
        stop_phrases = (
            "stop deploy",
            "stop deploying",
            "pause deploy",
            "no more deploy",
            "stop redeploy",
            "arrête le deploy",
            "arrete le deploy",
            "arrête de deploy",
        )
        return any(p in lower for p in stop_phrases)

    @staticmethod
    def _visitor_wants_resume_deploy(text: str) -> bool:
        lower = text.lower()
        return any(p in lower for p in ("resume deploy", "start deploy", "reprendre deploy"))

    def _deploy_failure_blocked(self) -> bool:
        if self._consecutive_deploy_failures < settings.demo_deploy_failure_cap:
            return False
        if self._deploy_blocked_until is None:
            return True
        return datetime.now(timezone.utc) < self._deploy_blocked_until

    def _deploy_allowed(self, *, observations: str = "", imp_turn: int = 0) -> tuple[bool, str | None]:
        if self._deploy_paused:
            return False, self._deploy_paused_reason or "visitor requested stop"
        if self._deploy_failure_blocked():
            return False, f"{self._consecutive_deploy_failures} consecutive publish failures (cooldown)"
        if self._publish_on_cooldown():
            return False, "publish cooldown"
        if self._publish_lock.locked():
            return False, "publish already in progress"
        if (
            imp_turn > 0
            and imp_turn % settings.demo_improvement_deploy_interval != 0
            and "http_probe] FAIL" in observations
        ):
            return False, "VM probes failing — code/probe turn"
        if self._consecutive_vm_probe_failures >= 3:
            return False, "VM API unreachable for 3+ turns — fix code first"
        return True, None

    def _record_deploy_failure(self) -> None:
        self._consecutive_deploy_failures += 1
        if self._consecutive_deploy_failures >= settings.demo_deploy_failure_cap:
            from datetime import timedelta

            self._deploy_blocked_until = datetime.now(timezone.utc) + timedelta(
                seconds=settings.demo_deploy_cooldown_after_fail_sec
            )

    def _record_deploy_success(self) -> None:
        self._consecutive_deploy_failures = 0
        self._deploy_blocked_until = None

    def _sanitize_improvement_plan(
        self,
        plan: ImprovementPlan,
        *,
        observations: str,
        imp_turn: int,
        artifacts: dict[str, str],
        deploy_allowed: bool,
        failure_sig: str,
    ) -> ImprovementPlan:
        if plan.action == "triage" and failure_sig == self._last_triage_signature:
            plan = ImprovementPlan(
                agent_id="vera",
                channel="ops",
                action="remediate",
                skill="vm_remediate",
                message="Incident already triaged — running VM fix instead of another report.",
            )
        if plan.action == "edit" and plan.file and is_pinned_on_deploy(plan.file):
            plan = ImprovementPlan(
                agent_id="marco",
                channel="engineering",
                action="edit",
                file="static/js/scene.js",
                lang="javascript",
                message=f"`{plan.file}` is pinned — polishing Three.js globe instead.",
            )

        sig = self._plan_signature(plan)
        if sig == self._last_plan_signature:
            self._repeat_plan_count += 1
        else:
            self._last_plan_signature = sig
            self._repeat_plan_count = 0
        if self._repeat_plan_count >= 2:
            logger.info("Breaking repeat plan loop: %s", sig)
            self._last_plan_signature = None
            self._repeat_plan_count = 0
            plan = _fallback_plan(
                turn=imp_turn + self._repeat_plan_count,
                observations=observations,
                artifacts=artifacts,
                deploy_allowed=deploy_allowed,
                failure_sig=failure_sig,
            )

        wants_deploy = plan.deploy or plan.action == "deploy"
        if not wants_deploy:
            return plan

        allowed, reason = self._deploy_allowed(observations=observations, imp_turn=imp_turn)
        if allowed:
            return plan

        vm_down = "http_probe] FAIL" in observations or "receiver_probe] FAIL" in observations
        pages_ok = "Pages-only mode OK" in observations

        if vm_down and "server.py" in self._artifacts:
            return ImprovementPlan(
                agent_id="vera",
                channel="ops",
                action="remediate",
                skill="vm_remediate",
                message=f"Deploy blocked ({reason}). Running VM curl/docker fix before code edits.",
            )
        if pages_ok:
            return ImprovementPlan(
                agent_id="jordan",
                channel="engineering",
                action="probe",
                skill="deploy_status",
                message=f"Deploy blocked ({reason}). GitHub Pages OK — probing VM receiver before next publish.",
            )
        return ImprovementPlan(
            agent_id="sam",
            channel="engineering",
            action="announce",
            message=f"Holding deploy ({reason}). Next turn focuses on probes or code fixes.",
        )

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def paused(self) -> bool:
        return self._paused

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
        if settings.demo_probe_refresh_sec > 0:
            self._observation_task = asyncio.create_task(
                self._observation_loop(), name="acme-demo-observations"
            )
        logger.info(
            "Demo loop started (pipeline=%s, interval=%ss, model=%s)",
            settings.demo_pipeline_mode,
            settings.demo_interval_sec,
            self.model_label(),
        )

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
        if self._observation_task:
            self._observation_task.cancel()
            try:
                await self._observation_task
            except asyncio.CancelledError:
                pass
            self._observation_task = None

    async def _observation_loop(self) -> None:
        """Refresh probes/logs on its own cadence — agents don't wait on this."""
        interval = max(2, settings.demo_probe_refresh_sec)
        while self.running and settings.demo_enabled:
            try:
                await self._refresh_observations()
            except Exception:
                logger.exception("Background observation refresh failed")
            await asyncio.sleep(interval)

    async def _refresh_observations(self) -> None:
        async with self._lock:
            artifacts_snapshot = dict(self._artifacts)
            last_deploy = dict(self._last_deploy) if self._last_deploy else None
        skills = DemoSkills(artifacts=artifacts_snapshot, last_deploy=last_deploy)
        observations, skill_results = await skills.gather_observations()
        async with self._lock:
            self._observations_text = observations
            self._observations_results = skill_results
            self._observations_at = datetime.now(timezone.utc)
            probe_results = [
                r for r in skill_results if r.skill in ("http_probe", "receiver_probe")
            ]
            if probe_results:
                if any(not r.ok for r in probe_results):
                    self._consecutive_vm_probe_failures += 1
                elif all(r.ok for r in probe_results):
                    self._consecutive_vm_probe_failures = 0

    async def _get_observations(
        self, *, artifacts: dict[str, str], last_deploy: dict[str, Any] | None
    ) -> tuple[str, list]:
        max_age = settings.demo_observations_max_age_sec
        async with self._lock:
            cached_at = self._observations_at
            if (
                cached_at is not None
                and self._observations_text
                and (datetime.now(timezone.utc) - cached_at).total_seconds() <= max_age
            ):
                return self._observations_text, list(self._observations_results)
        skills = DemoSkills(artifacts=artifacts, last_deploy=last_deploy)
        observations, skill_results = await skills.gather_observations()
        async with self._lock:
            self._observations_text = observations
            self._observations_results = skill_results
            self._observations_at = datetime.now(timezone.utc)
        return observations, skill_results

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
        delay = max(0, settings.demo_startup_delay_sec)
        if delay:
            await asyncio.sleep(delay)
        while self.running and settings.demo_enabled:
            if self._paused:
                await asyncio.sleep(0.25)
                continue
            try:
                async with self._turn_busy:
                    await self._run_turn()
            except Exception:
                logger.exception("Demo turn failed")
            if settings.demo_pipeline_mode:
                if settings.demo_turn_yield_ms > 0:
                    await asyncio.sleep(settings.demo_turn_yield_ms / 1000.0)
            elif settings.demo_interval_sec > 0:
                await asyncio.sleep(settings.demo_interval_sec)

    async def _run_turn(self) -> None:
        if self._paused:
            return
        if self._beat_index < len(SCRIPT_BEATS):
            await self._run_scripted_turn()
        elif settings.demo_continuous_improvement:
            await self._run_improvement_turn()

    async def _run_scripted_turn(self) -> None:
        async with self._lock:
            if self._recycling:
                return
            beat = SCRIPT_BEATS[self._beat_index]
            self._beat_index += 1
            self._turn_index += 1
            tick = self._turn_index
            self.tick = tick
            self._phase = "bootstrap"
            if self._beat_index >= len(SCRIPT_BEATS):
                self._phase = "improve"
            agent = self._registry.get_agent(beat.agent_id)
            if agent is None:
                return
            reply_name = (
                self._registry.get_agent(beat.reply_to).name
                if beat.reply_to and self._registry.get_agent(beat.reply_to)
                else None
            )
            artifacts_snapshot = dict(self._artifacts)

        content = beat.content
        if settings.demo_llm_paraphrase and beat.kind not in ("code", "preview"):
            content = await self._maybe_paraphrase(agent, beat.kind, beat.content)

        code_body = beat.code_body
        if beat.kind == "code" and beat.code_file:
            if code_body is None and settings.demo_llm_code:
                code_body = await generate_agent_code(agent, beat, artifacts=artifacts_snapshot)
                content = f"Pushed `{beat.code_file}` — {beat.content}"

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

        if beat.kind == "query":
            await self._run_acme_query(beat, msg, agent)

        async with self._lock:
            if self._recycling:
                return

            if beat.kind == "code" and beat.code_file and code_body:
                self._artifacts[beat.code_file] = self._pin_code_artifact(beat.code_file, code_body)
                if _index_key(self._artifacts):
                    self._preview_ready = True

            if beat.kind == "preview":
                self._preview_ready = bool(_index_key(self._artifacts))
                if self._last_deploy and self._last_deploy.get("pages_verified"):
                    msg.content = f"{content} Live: {self._last_deploy.get('pages_url', '')}"

            self._messages.append(msg)
            self._messages = _trim_messages(self._messages)

            state = await self.get_state()
            await self._notify(
                {
                    "type": "turn",
                    "tick": tick,
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

        if self._beat_index >= len(SCRIPT_BEATS):
            announce = asyncio.create_task(self._announce_improvement_mode())
            self._bg_tasks.add(announce)
            announce.add_done_callback(self._bg_tasks.discard)

    async def _announce_improvement_mode(self) -> None:
        msg = await self._append_agent_message(
            channel="general",
            agent_id="kai",
            kind="message",
            content=(
                "Bootstrap script complete — switching to *continuous improvement* (pipeline mode — no idle waits). "
                "Squad probes in the background, patches files, and ships until POST /api/v1/demo/pause. "
                "Vera triages incidents in #ops."
            ),
        )
        async with self._lock:
            self._phase = "improve"
            state = await self.get_state()
            if msg:
                await self._notify(
                    {
                        "type": "phase",
                        "phase": "improve",
                        "message": msg.to_out().model_dump(),
                        "state": state.model_dump(),
                    }
                )

    async def _run_improvement_turn(self) -> None:
        async with self._lock:
            if self._recycling:
                return
            self._improvement_turn += 1
            self._turn_index += 1
            tick = self._turn_index
            self.tick = tick
            self._phase = "improve"
            artifacts_snapshot = dict(self._artifacts)
            last_deploy = dict(self._last_deploy) if self._last_deploy else None
            recent = "\n".join(
                f"{m.agent_name}: {m.content[:160]}" for m in self._messages[-10:]
            )
            imp_turn = self._improvement_turn

        skills = DemoSkills(artifacts=artifacts_snapshot, last_deploy=last_deploy)
        observations, skill_results = await self._get_observations(
            artifacts=artifacts_snapshot, last_deploy=last_deploy
        )
        failure_sig = failure_signature(observations, skill_results)

        async with self._lock:
            deploy_allowed, deploy_block_reason = self._deploy_allowed(
                observations=observations, imp_turn=imp_turn
            )

        plan = await plan_improvement(
            turn=imp_turn,
            observations=observations,
            artifacts=artifacts_snapshot,
            recent_thread=recent,
            deploy_allowed=deploy_allowed,
            deploy_block_reason=deploy_block_reason,
            failure_sig=failure_sig,
            agents=self._registry.list_agents(),
            channels=self._registry.list_channels(),
        )
        plan = self._sanitize_improvement_plan(
            plan,
            observations=observations,
            imp_turn=imp_turn,
            artifacts=artifacts_snapshot,
            deploy_allowed=deploy_allowed,
            failure_sig=failure_sig,
        )
        agent = self._registry.get_agent(plan.agent_id)
        if agent is None:
            agent = self._registry.get_agent("marco") or self._registry.list_agents()[0]

        skill_note = ""
        if plan.action == "probe" or plan.skill:
            fails = [r for r in skill_results if not r.ok]
            if fails:
                skill_note = "\n".join(r.to_line() for r in fails[:4])

        code_body = None
        beat: DemoBeat | None = plan.to_beat()
        content = plan.message
        if skill_note:
            content = f"{content}\n\n```\n{skill_note}\n```"

        kind = plan.action
        if plan.action == "edit" and beat:
            kind = "code"
            if settings.demo_llm_code and beat.code_file:
                code_body = await generate_agent_code(agent, beat, artifacts=artifacts_snapshot)
                content = f"Pushed `{beat.code_file}` — {plan.message}"
        elif plan.action == "deploy":
            kind = "deploy"
        elif plan.action == "triage":
            kind = "triage"
            content = format_triage_report(
                observations=observations,
                skill_results=skill_results,
                deploy_block_reason=deploy_block_reason,
                signature=failure_sig,
            )
        elif plan.action == "remediate":
            kind = "remediate"
            skill_result, recipe, cmd = await execute_remediation(
                signature=failure_sig,
                state=self._remediation,
                attempt_cap=settings.demo_remediation_attempt_cap,
                recipe=plan.recipe,
                command=plan.command,
            )
            if skill_result.summary.startswith("recipe") and "exhausted" in skill_result.summary:
                refs = reference_site_files()
                async with self._lock:
                    self._artifacts.update(refs)
                plan = ImprovementPlan(
                    agent_id="nina",
                    channel="deploy",
                    action="deploy",
                    deploy=True,
                    message="VM recipes exhausted — restored pinned server stack and redeploying.",
                )
                nina = self._registry.get_agent("nina")
                agent = nina or self._registry.list_agents()[0]
                kind = "deploy"
                content = plan.message
                beat = None
                code_body = None
            else:
                content = format_remediation_message(
                    recipe=recipe,
                    command=cmd,
                    result=skill_result.detail,
                    signature=failure_sig,
                )
                if skill_result.ok:
                    async with self._lock:
                        self._remediation.reset_signature(failure_sig)
                        self._consecutive_vm_probe_failures = 0
        elif plan.action == "hire":
            kind = "hire"
            try:
                chans = plan.new_agent_channels or ["engineering"]
                hired = self._registry.hire_agent(
                    name=plan.new_agent_name or "Riley II",
                    role=plan.new_agent_role or "Specialist",
                    channels=chans,
                )
                async with self._lock:
                    self._belief_counts[hired.id] = 0
                content = (
                    f"Hired *{hired.name}* (`{hired.id}`) as {hired.role} "
                    f"— channels: {', '.join('#' + c for c in hired.channels)}."
                )
                agent = hired
            except Exception as exc:
                content = f"Hire blocked: {exc}"
        elif plan.action == "create_channel":
            kind = "channel"
            try:
                ch = self._registry.create_channel(
                    name=plan.new_channel_name or "war-room",
                    topic=plan.new_channel_topic or "Ad-hoc squad coordination",
                    emoji=plan.new_channel_emoji or "📌",
                )
                content = f"Opened #{ch.name} (`{ch.id}`) — {ch.topic}"
            except Exception as exc:
                content = f"Channel create blocked: {exc}"
        elif plan.action == "query" and beat:
            kind = "query"
        else:
            kind = "skill" if plan.action == "probe" else "message"

        if self._should_suppress_agent_message(agent_id=agent.id, content=content):
            logger.info("Suppressed improvement loop from %s — skipping turn", agent.id)
            return

        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            channel=plan.channel,
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=kind,
            content=content,
            code_file=beat.code_file if beat else None,
            code_lang=beat.code_lang if beat else None,
            code_body=code_body,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if kind == "query" and plan.query:
            msg.content = plan.query
            if beat:
                beat = DemoBeat(
                    channel=plan.channel,
                    agent_id=plan.agent_id,
                    kind="query",
                    content=plan.query,
                )

        if kind == "query" and beat:
            await self._run_acme_query(beat, msg, agent)

        async with self._lock:
            if beat and kind == "code" and beat.code_file and code_body:
                self._artifacts[beat.code_file] = self._pin_code_artifact(beat.code_file, code_body)
                if _index_key(self._artifacts):
                    self._preview_ready = True

            self._messages.append(msg)
            self._messages = _trim_messages(self._messages)
            self._mark_agent_post(agent.id, content)
            state = await self.get_state()
            await self._notify(
                {
                    "type": "turn",
                    "tick": tick,
                    "message": msg.to_out().model_dump(),
                    "state": state.model_dump(),
                }
            )

        if beat:
            task = asyncio.create_task(self._process_acme(beat, msg, agent))
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

        if plan.action == "triage":
            async with self._lock:
                self._last_triage_signature = failure_signature(observations, skill_results)
                self._last_triage_tick = tick
        elif any(not r.ok for r in skill_results) or deploy_block_reason:
            if plan.action not in ("triage", "remediate", "deploy"):
                await self._maybe_post_vera_triage(
                    observations=observations,
                    skill_results=skill_results,
                    deploy_block_reason=deploy_block_reason,
                    tick=tick,
                )

        should_deploy = plan.deploy or plan.action == "deploy"
        if should_deploy and settings.demo_auto_publish and self._artifacts:
            allowed, _ = self._deploy_allowed(observations=observations, imp_turn=imp_turn)
            if allowed:
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
                    for peer in self._registry.list_agents():
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

    def _remember_message_norm(self, content: str) -> None:
        norm = normalize_message(content)
        if not norm:
            return
        self._recent_message_norms.append(norm)
        cap = 24
        if len(self._recent_message_norms) > cap:
            self._recent_message_norms = self._recent_message_norms[-cap:]

    @staticmethod
    def _plan_signature(plan: ImprovementPlan) -> str:
        return "|".join(
            [
                plan.agent_id,
                plan.action,
                plan.skill or "",
                plan.file or "",
                plan.recipe or "",
                (plan.message or "")[:80],
            ]
        )

    def _should_suppress_agent_message(self, *, agent_id: str, content: str) -> bool:
        if self._is_duplicate_spam(agent_id=agent_id, content=content):
            return True
        if not self._registry.agent_dedup_messages(agent_id):
            return False
        last = self._last_agent_post_at.get(agent_id)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < settings.demo_agent_message_cooldown_sec

    def _mark_agent_post(self, agent_id: str, content: str) -> None:
        self._last_agent_post_at[agent_id] = datetime.now(timezone.utc)
        self._remember_message_norm(content)

    def _is_duplicate_spam(self, *, agent_id: str, content: str) -> bool:
        if not self._registry.agent_dedup_messages(agent_id):
            return False
        return is_spam_duplicate(content, self._recent_message_norms)

    async def _maybe_post_vera_triage(
        self,
        *,
        observations: str,
        skill_results: list,
        deploy_block_reason: str | None,
        tick: int,
    ) -> None:
        signature = failure_signature(observations, skill_results)
        if signature == "ok" and not deploy_block_reason:
            self._last_triage_signature = None
            return
        if (
            signature == self._last_triage_signature
            and (tick - self._last_triage_tick) < settings.demo_triage_interval_ticks
        ):
            return
        self._last_triage_signature = signature
        self._last_triage_tick = tick
        report = format_triage_report(
            observations=observations,
            skill_results=skill_results,
            deploy_block_reason=deploy_block_reason,
            signature=signature,
        )
        await self._append_agent_message(
            channel="ops",
            agent_id="vera",
            kind="triage",
            content=report,
            skip_dedup=True,
        )
        state = await self.get_state()
        await self._notify({"type": "update", "state": state.model_dump()})

    async def _append_agent_message(
        self,
        *,
        channel: str,
        agent_id: str,
        kind: str,
        content: str,
        reply_to_name: str | None = None,
        answer: str | None = None,
        skip_dedup: bool = False,
    ) -> _DemoMessage | None:
        if not skip_dedup and self._should_suppress_agent_message(agent_id=agent_id, content=content):
            logger.debug("suppressed duplicate demo message from %s", agent_id)
            return None
        agent = self._registry.get_agent(agent_id)
        if agent is None:
            logger.warning("unknown agent_id %s for message", agent_id)
            return None
        msg = _DemoMessage(
            id=str(uuid.uuid4()),
            channel=channel,
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            kind=kind,
            content=content,
            answer=answer,
            reply_to_name=reply_to_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._messages.append(msg)
        self._messages = _trim_messages(self._messages)
        self._mark_agent_post(agent_id, content)
        return msg

    def _check_visitor_secret(self, secret: str) -> None:
        if not settings.demo_visitor_secret or secret != settings.demo_visitor_secret:
            raise ValueError("Invalid secret")

    async def unlock_visitor(self, *, secret: str) -> DemoVisitorUnlockOut:
        self._check_visitor_secret(secret)
        return DemoVisitorUnlockOut(ok=True)

    async def _agent_reply_to_visitor(
        self, agent: DemoAgent, *, channel: str, visitor_text: str
    ) -> str:
        recent = [m for m in self._messages[-14:] if m.channel == channel]
        thread = "\n".join(f"{m.agent_name}: {m.content[:220]}" for m in recent)
        llm = get_llm_client()
        model = settings.demo_azure_deployment or None
        prompt = f"""#{channel} thread:
{thread}

Visitor says: {visitor_text}

Reply as {agent.name} ({agent.role}) in Slack — 1-3 sentences, helpful, on the Erebor build. No markdown fences."""
        try:
            return await llm.generate(
                prompt,
                system=agent.system_prompt,
                model=model,
                temperature=0.55,
                timeout=25.0,
            )
        except Exception:
            logger.exception("Visitor reply failed for %s", agent.id)
            return f"Hey — {agent.name} here. We're heads-down on Erebor; ask again in a sec."

    async def handle_visitor_say(
        self, *, secret: str, channel: str, message: str
    ) -> DemoVisitorSayOut:
        self._check_visitor_secret(secret)
        channel = channel.strip().lower()
        if not self._registry.get_channel(channel):
            raise ValueError(f"Unknown channel: {channel}")
        text = message.strip()
        if not text:
            raise ValueError("Empty message")

        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._last_visitor_say_at is not None:
                wait = settings.demo_visitor_say_cooldown_sec - (
                    now - self._last_visitor_say_at
                ).total_seconds()
                if wait > 0:
                    raise ValueError(f"Slow down — try again in {int(wait)}s")
            self._last_visitor_say_at = now

            if self._visitor_wants_stop_deploy(text):
                self._deploy_paused = True
                self._deploy_paused_reason = "visitor requested stop"
            elif self._visitor_wants_resume_deploy(text):
                self._deploy_paused = False
                self._deploy_paused_reason = None
                self._consecutive_deploy_failures = 0
                self._deploy_blocked_until = None

            visitor_msg = _DemoMessage(
                id=str(uuid.uuid4()),
                channel=channel,
                agent_id="visitor",
                agent_name="You",
                role="Visitor",
                kind="visitor",
                content=text,
                timestamp=now.isoformat(),
            )
            self._messages.append(visitor_msg)

            pool = self._registry.agents_for_channel(channel) or self._registry.list_agents()[:3]
            self._visitor_turn += 1
            primary = pool[self._visitor_turn % len(pool)]
            responders = [primary]
            secondary = pool[(self._visitor_turn + 2) % len(pool)]
            if secondary.id != primary.id and self._visitor_turn % 2 == 0:
                responders.append(secondary)

        reply_bodies: list[tuple[DemoAgent, str]] = []
        for agent in responders:
            body = await self._agent_reply_to_visitor(agent, channel=channel, visitor_text=text)
            reply_bodies.append((agent, body))

        async with self._lock:
            replies: list[_DemoMessage] = []
            for agent, body in reply_bodies:
                reply = await self._append_agent_message(
                    channel=channel,
                    agent_id=agent.id,
                    kind="reply",
                    content=body,
                    reply_to_name="You",
                )
                if reply:
                    replies.append(reply)

            self._messages = _trim_messages(self._messages)
            self.tick += 1

            state = await self.get_state()
            for reply in replies:
                await self._notify(
                    {
                        "type": "turn",
                        "tick": self.tick,
                        "message": reply.to_out().model_dump(),
                        "state": state.model_dump(),
                    }
                )
            await self._notify(
                {
                    "type": "visitor",
                    "message": visitor_msg.to_out().model_dump(),
                    "state": state.model_dump(),
                }
            )

            task = asyncio.create_task(
                self._ingest_visitor_exchange(channel, text, replies)
            )
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

            return DemoVisitorSayOut(
                ok=True,
                your_message=visitor_msg.to_out(),
                replies=[r.to_out() for r in replies],
            )

    async def _ingest_visitor_exchange(
        self, channel: str, visitor_text: str, replies: list[_DemoMessage]
    ) -> None:
        try:
            llm = get_llm_client()
            async with SessionLocal() as session:
                for reply in replies:
                    agent = self._registry.get_agent(reply.agent_id)
                    if agent is None:
                        continue
                    orch = ACMEOrchestrator(
                        session, neo4j_client, llm, tenant_id=agent.tenant_id
                    )
                    await orch.ingest_experience(
                        ExperienceCreate(
                            content=f"[#{channel}] Visitor: {visitor_text} → {agent.name}: {reply.content}",
                            source_type=SourceType.HUMAN_EXPERT,
                            source_id="demo-visitor",
                            tags=["demo", "erebor", channel, "visitor"],
                            tenant_id=agent.tenant_id,
                        )
                    )
                    if "?" in visitor_text:
                        try:
                            qr = await orch.query(
                                QueryRequest(question=visitor_text, challenge=False)
                            )
                            reply.answer = qr.answer[:500]
                            reply.beliefs_used = [b.model_dump() for b in qr.beliefs_used]
                        except Exception:
                            pass
                await session.commit()
            state = await self.get_state()
            await self._notify({"type": "update", "state": state.model_dump()})
        except Exception:
            logger.exception("Visitor ACME ingest failed")

    async def _autonomous_publish(self, *, trigger_msg: _DemoMessage) -> None:
        """Nina's squad publishes without visitor interaction."""
        if self._deploy_paused:
            return

        if not self._publish_configured():
            trigger_msg.content = (
                f"{trigger_msg.content}\n\n_(GitHub token missing on server — set DEMO_GITHUB_TOKEN.)_"
            )
            state = await self.get_state()
            await self._notify({"type": "update", "state": state.model_dump()})
            return

        if self._publish_lock.locked():
            return

        async with self._publish_lock:
            if self._publish_on_cooldown():
                return

            pages_already_ok = bool((self._last_deploy or {}).get("pages_verified"))

            try:
                if pages_already_ok:
                    result = {
                        "repo": (self._last_deploy or {}).get("repo", settings.demo_github_repo),
                        "branch": (self._last_deploy or {}).get("branch", settings.demo_github_branch),
                        "files": [],
                        "pages_url": (self._last_deploy or {}).get("pages_url", ""),
                        "pages_verified": True,
                        "pages_status_code": (self._last_deploy or {}).get("pages_status_code"),
                    }
                else:
                    result = await self.deploy(skip_vm=True)
                self._last_publish_at = datetime.now(timezone.utc)
                self._record_deploy_success()

                if not pages_already_ok:
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
                elif pages_already_ok:
                    nina_msg = f"GitHub Pages still healthy at {pages_url} — VM-only deploy this turn."
                    jordan_msg = f"Skipped GitHub publish (Pages OK). Target VM restore: {settings.demo_vm_site_url or settings.demo_vm_url}"
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
                if not pages_already_ok:
                    await self._ingest_pages_access(pages_url, verified=bool(verified))

                vm_result = await self._deploy_to_vm()
                if vm_result:
                    site = settings.demo_vm_site_url or vm_result.get("site_url", settings.demo_vm_url)
                    self._last_deploy = {
                        **(self._last_deploy or {}),
                        **result,
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
                if follow:
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
                self._record_deploy_failure()
                trigger_msg.content = f"{trigger_msg.content}\n\nPublish failed: {exc}"
                fail = await self._append_agent_message(
                    channel="deploy",
                    agent_id="sam",
                    kind="message",
                    content=f"Publish blocked — check repo permissions and DEMO_GITHUB_TOKEN. ({exc})",
                )
                state = await self.get_state()
                if fail:
                    await self._notify(
                        {
                            "type": "turn",
                            "tick": self.tick,
                            "message": fail.to_out().model_dump(),
                            "state": state.model_dump(),
                        }
                    )
                if pages_already_ok and self._vm_configured():
                    try:
                        vm_result = await self._deploy_to_vm()
                        if vm_result:
                            site = settings.demo_vm_site_url or vm_result.get(
                                "site_url", settings.demo_vm_url
                            )
                            self._last_deploy = {
                                **(self._last_deploy or {}),
                                "vm_url": site,
                                "vm_files": vm_result.get("files", []),
                            }
                            await self._append_agent_message(
                                channel="deploy",
                                agent_id="nina",
                                kind="message",
                                content=f"GitHub skipped after error; pushed VM-only to {site}.",
                            )
                            self._record_deploy_success()
                    except Exception:
                        logger.exception("VM-only fallback deploy failed")

    async def _process_acme(self, beat: DemoBeat, msg: _DemoMessage, agent: DemoAgent) -> None:
        try:
            llm = get_llm_client()
            async with SessionLocal() as session:
                orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=agent.tenant_id)
                tags = ["demo", "erebor", beat.channel]

                if beat.kind in ("message", "code", "deploy", "reply", "preview", "skill"):
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
        for agent in self._registry.list_agents():
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
            agent = self._registry.get_agent(agent_id)
            if agent is None:
                continue
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
        refresh_beliefs = (
            self._belief_fetch_tick < 0
            or (self.tick - self._belief_fetch_tick) >= settings.demo_belief_refresh_ticks
        )
        if refresh_beliefs:
            async with SessionLocal() as session:
                for agent in self._registry.list_agents():
                    beliefs = await self._list_beliefs_for_tenant(session, agent.tenant_id)
                    self._belief_counts[agent.id] = len(beliefs)
            self._belief_fetch_tick = self.tick

        agents_out: list[DemoAgentOut] = []
        for agent in self._registry.list_agents():
            agents_out.append(
                DemoAgentOut(
                    id=agent.id,
                    name=agent.name,
                    role=agent.role,
                    tenant_id=agent.tenant_id,
                    color=agent.color,
                    initials=agent.initials,
                    channels=list(agent.channels),
                    belief_count=self._belief_counts.get(agent.id, 0),
                    beliefs=[],
                )
            )

        sel_agent = selected_agent if self._registry.get_agent(selected_agent or "") else None
        sel_channel = selected_channel if self._registry.get_channel(selected_channel or "") else None
        channels_out = [
            DemoChannelOut(id=c.id, name=c.name, topic=c.topic, emoji=c.emoji)
            for c in self._registry.list_channels()
        ]

        msgs = self._messages
        cap = settings.demo_state_message_cap
        if cap > 0:
            msgs = msgs[-cap:]
        return DemoStateOut(
            running=self.running and settings.demo_enabled,
            model=self.model_label(),
            tick=self.tick,
            scenario="erebor-open-intelligence",
            phase=self._phase,
            paused=self._paused,
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
        agent = self._registry.get_agent(agent_id)
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
        skip_github: bool = False,
        skip_vm: bool = False,
    ) -> dict[str, Any]:
        auth = token or settings.demo_github_token
        target_repo = repo or settings.demo_github_repo
        target_branch = branch or settings.demo_github_branch

        result: dict[str, Any] = dict(self._last_deploy or {})
        if not skip_github:
            if not auth:
                raise ValueError("GitHub token not configured — set DEMO_GITHUB_TOKEN or pass token")
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

        if not skip_vm:
            vm_result = await self._deploy_to_vm()
            if vm_result:
                site = settings.demo_vm_site_url or vm_result.get("site_url", "")
                self._last_deploy = {
                    **(self._last_deploy or result),
                    "vm_url": site,
                    "vm_live": vm_result.get("live_ok", False),
                }

        state = await self.get_state()
        await self._notify({"type": "deploy", "deploy": self._last_deploy, "state": state.model_dump()})
        return result

    async def _clean_state(
        self, *, force: bool = False, wipe_external: bool = True, force_wipe: bool = False
    ) -> list[dict[str, int | str]]:
        async with SessionLocal() as session:
            tenant_ids = tuple(dict.fromkeys(ALL_DEMO_TENANT_IDS + self._registry.tenant_ids()))
            stats = await cleanup_all_demo_tenants(
                session, neo4j_client, tenant_ids=tenant_ids
            )

        self._messages.clear()
        self._last_sessions.clear()
        self._artifacts = empty_artifacts()
        self._last_deploy = None
        self._last_publish_at = None
        self._preview_ready = False
        self._beat_index = 0
        self._turn_index = 0
        self._improvement_turn = 0
        self._deploy_paused = False
        self._deploy_paused_reason = None
        self._consecutive_deploy_failures = 0
        self._consecutive_vm_probe_failures = 0
        self._deploy_blocked_until = None
        self._recent_message_norms = []
        self._last_agent_post_at = {}
        self._last_plan_signature = None
        self._repeat_plan_count = 0
        self._last_triage_signature = None
        self._last_triage_tick = -999
        self._remediation = RemediationState()
        self._observations_text = ""
        self._observations_results = []
        self._observations_at = None
        self.tick = 0
        self._phase = "bootstrap"
        self._paused = False
        self._last_visitor_say_at = None
        self._visitor_turn = 0
        self._registry = SquadRegistry.default()
        self._belief_counts = {a.id: 0 for a in self._registry.list_agents()}
        self._belief_fetch_tick = -999
        if force:
            self._last_reset_at = None

        if wipe_external and (settings.demo_wipe_on_clean or force_wipe):
            if self._vm_configured():
                await self._wipe_vm_product()
            if self._publish_configured() and settings.demo_clean_repo_on_reset:
                await self._wipe_github_repo(nuclear=force_wipe)

        return stats

    async def _wipe_github_repo(self, *, nuclear: bool = False) -> None:
        if not self._publish_configured():
            return
        try:
            if nuclear:
                deleted = await delete_repo(
                    token=settings.demo_github_token,
                    repo=settings.demo_github_repo,
                )
                if deleted:
                    return
            await wipe_repo(
                token=settings.demo_github_token,
                repo=settings.demo_github_repo,
                branch=settings.demo_github_branch,
            )
        except Exception:
            logger.exception("GitHub repo wipe failed")

    async def _wipe_vm_product(self) -> None:
        """Remove prior squad files on VM so deploy starts clean."""
        if not self._vm_configured():
            return
        try:
            import httpx

            base = settings.demo_vm_url.rstrip("/")
            async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
                await client.post(
                    f"{base}/deploy",
                    json={"files": dict(baseline_artifacts()), "wipe": True},
                    headers={"Authorization": f"Bearer {settings.demo_vm_deploy_key}"},
                )
        except Exception:
            logger.exception("VM product wipe failed")

    async def reset(self) -> tuple[bool, str, list[dict[str, int | str]]]:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._last_reset_at is not None:
                wait = settings.demo_reset_cooldown_sec - (now - self._last_reset_at).total_seconds()
                if wait > 0:
                    return False, f"Please wait {int(wait)}s before resetting again.", []

            stats = await self._clean_state(force=False, wipe_external=True, force_wipe=True)
            self._last_reset_at = now

        state = await self.get_state()
        await self._notify({"type": "reset", "state": state.model_dump()})
        return True, "Demo reset complete.", stats


demo_service = DemoService()
