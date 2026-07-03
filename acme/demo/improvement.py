"""Autonomous improvement planning — agents pick skills and file edits."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from acme.config import settings
from acme.demo.agents import DEMO_AGENTS, DemoAgent
from acme.demo.channels import DemoChannel
from acme.demo.script import DemoBeat
from acme.demo.lessons import SQUAD_LESSONS_PROMPT
from acme.demo.skills import SKILL_CATALOG
from acme.llm.factory import get_llm_client

logger = logging.getLogger("acme.demo.improvement")

LANG_BY_EXT = {
    ".css": "css",
    ".js": "javascript",
    ".html": "html",
    ".py": "python",
    ".md": "markdown",
}


@dataclass
class ImprovementPlan:
    agent_id: str
    channel: str
    action: str
    message: str
    file: str | None = None
    lang: str | None = None
    query: str | None = None
    skill: str | None = None
    deploy: bool = False
    recipe: str | None = None
    command: str | None = None
    new_agent_name: str | None = None
    new_agent_role: str | None = None
    new_agent_channels: list[str] | None = None
    new_channel_name: str | None = None
    new_channel_topic: str | None = None
    new_channel_emoji: str | None = None

    def to_beat(self) -> DemoBeat | None:
        if self.action == "edit" and self.file:
            return DemoBeat(
                channel=self.channel,
                agent_id=self.agent_id,
                kind="code",
                content=self.message,
                code_file=self.file,
                code_lang=self.lang or _lang_for_path(self.file),
            )
        if self.action == "query" and self.query:
            return DemoBeat(
                channel=self.channel,
                agent_id=self.agent_id,
                kind="query",
                content=self.query,
            )
        return None


def _lang_for_path(path: str) -> str:
    for ext, lang in LANG_BY_EXT.items():
        if path.endswith(ext):
            return lang
    return "text"


def _parse_plan(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _fallback_plan(
    *,
    turn: int,
    observations: str,
    artifacts: dict[str, str],
    deploy_allowed: bool = True,
    failure_sig: str = "ok",
    ui_fix_pending: bool = False,
) -> ImprovementPlan:
    agents_cycle = ["jordan", "marco", "chen", "priya", "nina", "alex"]
    agent_id = agents_cycle[turn % len(agents_cycle)]
    has_index = "static/index.html" in artifacts
    vm_failing = failure_sig != "ok" or "http_probe] FAIL" in observations or "receiver_probe] FAIL" in observations
    pages_ok = "[frontend_js] OK" in observations
    ui_failed = "[ui_audit] FAIL" in observations or ui_fix_pending

    if vm_failing:
        if turn % 5 == 0:
            return ImprovementPlan(
                agent_id="vera",
                channel="ops",
                action="triage",
                skill="deploy_status",
                message="Consolidated incident triage — then VM exec fixes on next turns.",
            )
        return ImprovementPlan(
            agent_id="vera",
            channel="ops",
            action="remediate",
            skill="vm_remediate",
            message="Running allowlisted curl/docker fix on the VM via receiver /exec.",
        )
    if "FAIL" in observations and "http_probe" in observations:
        return ImprovementPlan(
            agent_id="jordan",
            channel="engineering",
            action="probe",
            skill="http_probe",
            message="Running live health + search probes — something looks off on the VM.",
        )
    interval = max(2, settings.demo_ui_audit_interval)
    if not vm_failing and turn % interval == 1:
        return ImprovementPlan(
            agent_id="taylor",
            channel="qa",
            action="ui_audit",
            skill="ui_audit",
            message="Running browser UI audit — click search, controls, capture screenshots for the squad.",
        )
    if not has_index:
        return ImprovementPlan(
            agent_id="marco",
            channel="engineering",
            action="edit",
            file="static/index.html",
            lang="html",
            message="Bootstrap the Belief Observatory shell — episodic stream, SVG graph, CRS scrubber.",
        )
    if deploy_allowed and not pages_ok and turn % 8 == 0:
        return ImprovementPlan(
            agent_id="nina",
            channel="deploy",
            action="deploy",
            deploy=True,
            message="Shipping latest squad artifacts to VM + Pages.",
        )
    if turn % 18 == 0:
        return ImprovementPlan(
            agent_id="alex",
            channel="general",
            action="create_channel",
            new_channel_name="war-room",
            new_channel_topic="Fast coordination for incidents and launches",
            new_channel_emoji="🎯",
            message="Opening a war-room channel so the squad can coordinate without spamming #engineering.",
        )
    if turn % 22 == 0:
        return ImprovementPlan(
            agent_id="alex",
            channel="general",
            action="hire",
            new_agent_name="Quinn",
            new_agent_role="Platform Engineer",
            new_agent_channels=["engineering", "ops"],
            message="Hiring Quinn to help with VM/platform work alongside Vera.",
        )
    if turn % 3 == 0:
        return ImprovementPlan(
            agent_id="jordan",
            channel="engineering",
            action="query",
            query="What is the highest-impact UX or API fix for Belief Observatory right now?",
            message="Checking ACME memory for the next improvement priority.",
        )
    targets = [
        ("priya", "static/css/observatory.css", "css", "Refine observatory shell spacing and mobile layout."),
        ("priya", "static/css/observatory.css", "css", "Polish CRS meter and scrubber touch targets."),
        ("chen", "static/css/observatory.css", "css", "Tighten responsive stack below 900px."),
        ("priya", "static/css/observatory.css", "css", "Improve episode panel typography and contrast."),
    ]
    pick = targets[turn % len(targets)]
    return ImprovementPlan(
        agent_id=pick[0],
        channel="engineering",
        action="edit",
        file=pick[1],
        lang=pick[2],
        message=pick[3],
    )


async def plan_improvement(
    *,
    turn: int,
    observations: str,
    artifacts: dict[str, str],
    recent_thread: str,
    deploy_allowed: bool = True,
    deploy_block_reason: str | None = None,
    failure_sig: str = "ok",
    agents: list[DemoAgent] | None = None,
    channels: list[DemoChannel] | None = None,
    ui_fix_pending: bool = False,
) -> ImprovementPlan:
    squad_agents = agents or list(DEMO_AGENTS)
    squad_channels = channels or []
    agent_ids = [a.id for a in squad_agents]
    channel_ids = [c.id for c in squad_channels] or [
        "general",
        "engineering",
        "deploy",
        "ops",
    ]
    artifact_list = ", ".join(sorted(artifacts.keys())[:35]) or "(empty)"
    deploy_rule = (
        "- Deploy is ALLOWED when probes are green or after a code fix"
        if deploy_allowed
        else f"- Deploy is BLOCKED ({deploy_block_reason or 'cooldown/failures'}). "
        "NEVER set action=deploy or deploy=true. Edit code or run probes instead."
    )

    prompt = f"""{SKILL_CATALOG}

Squad lessons (already in ACME memory — follow strictly):
{SQUAD_LESSONS_PROMPT}

Turn #{turn}. Belief Observatory squad is in continuous improvement mode — keep shipping until a human pauses.

Recent Slack:
{recent_thread[:1800]}

Runtime observations:
{observations[:5000]}

Artifacts in repo: {artifact_list}

Pick the next highest-impact action. Respond with JSON only:
{{
  "agent_id": one of {agent_ids},
  "channel": one of {channel_ids},
  "action": "probe"|"edit"|"deploy"|"query"|"announce"|"triage"|"remediate"|"hire"|"create_channel"|"ui_audit",
  "message": "Slack message explaining what you did or will do",
  "file": "path/for/edit action or null",
  "lang": "css|javascript|html|python|markdown or null",
  "query": "question for acme_query or null",
  "skill": "which skill you used or null",
  "recipe": "vm recipe name or null",
  "command": "allowlisted shell on VM or null",
  "new_agent_name": "for hire action or null",
  "new_agent_role": "for hire action or null",
  "new_agent_channels": ["channel_ids"] or null,
  "new_channel_name": "for create_channel or null",
  "new_channel_topic": "for create_channel or null",
  "new_channel_emoji": "single emoji or null",
  "deploy": false
}}

Rules:
- static/index.html links: css/foo.css and js/bar.js ONLY — never /static/ prefix
- Do not edit pinned boot files (server.py, api/routes/*) — edit static/css and static/js
- Kai/Alex can hire specialists (hire) or open channels (create_channel) when the squad lacks skills
- When probes fail: Vera runs remediate (vm_exec) BEFORE redeploy
- Never repeat triage every turn — alternate remediate → edit → deploy → hire if stuck
- Prefer edit/probe when VM API or receiver probes fail — do NOT redeploy the same broken artifact set
- If GitHub Pages is healthy but VM API is down, run compose_restart / probe_site_health first
- Jordan uses probe/query; Taylor runs ui_audit on #qa then builders fix; Nina deploys only when allowed
- Vera owns #ops — triage once per incident, then remediate with real commands
- One concrete improvement per turn — no vague planning
{deploy_rule}
"""

    llm = get_llm_client()
    model = settings.demo_azure_deployment or None
    try:
        raw = await llm.generate(
            prompt,
            system="You are the Belief Observatory squad coordinator. Output valid JSON only.",
            model=model,
            temperature=0.35,
            timeout=30.0,
            json_mode=True,
        )
        data = _parse_plan(raw)
        agent_id = data.get("agent_id", "marco")
        if agent_id not in agent_ids:
            agent_id = agent_ids[0] if agent_ids else "marco"
        return ImprovementPlan(
            agent_id=agent_id,
            channel=data.get("channel", "engineering"),
            action=data.get("action", "announce"),
            message=data.get("message", "Continuing Belief Observatory improvements."),
            file=data.get("file"),
            lang=data.get("lang"),
            query=data.get("query"),
            skill=data.get("skill"),
            deploy=bool(data.get("deploy")),
            recipe=data.get("recipe"),
            command=data.get("command"),
            new_agent_name=data.get("new_agent_name"),
            new_agent_role=data.get("new_agent_role"),
            new_agent_channels=data.get("new_agent_channels"),
            new_channel_name=data.get("new_channel_name"),
            new_channel_topic=data.get("new_channel_topic"),
            new_channel_emoji=data.get("new_channel_emoji"),
        )
    except Exception:
        logger.exception("Improvement plan LLM failed — using heuristic")
        return _fallback_plan(
            turn=turn,
            observations=observations,
            artifacts=artifacts,
            deploy_allowed=deploy_allowed,
            failure_sig=failure_sig,
            ui_fix_pending=ui_fix_pending,
        )
