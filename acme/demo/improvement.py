"""Autonomous improvement planning — agents pick skills and file edits."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from acme.config import settings
from acme.demo.agents import AGENT_BY_ID, DEMO_AGENTS
from acme.demo.script import DemoBeat
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
) -> ImprovementPlan:
    agents_cycle = ["jordan", "marco", "chen", "priya", "nina", "sam"]
    agent_id = agents_cycle[turn % len(agents_cycle)]
    has_index = "static/index.html" in artifacts
    vm_failing = "http_probe] FAIL" in observations or "receiver_probe] FAIL" in observations
    pages_ok = "Pages-only mode OK" in observations

    if vm_failing:
        return ImprovementPlan(
            agent_id="vera",
            channel="ops",
            action="triage",
            skill="deploy_status",
            message="VM/receiver probes failing — posting deduped incident triage before any redeploy.",
        )
    if "FAIL" in observations and "http_probe" in observations:
        return ImprovementPlan(
            agent_id="jordan",
            channel="engineering",
            action="probe",
            skill="http_probe",
            message="Running live health + search probes — something looks off on the VM.",
        )
    if not has_index:
        return ImprovementPlan(
            agent_id="marco",
            channel="engineering",
            action="edit",
            file="static/index.html",
            lang="html",
            message="Bootstrap the Erebor product shell with Three.js canvas and omnibar.",
        )
    if deploy_allowed and not pages_ok and turn % 8 == 0:
        return ImprovementPlan(
            agent_id="nina",
            channel="deploy",
            action="deploy",
            deploy=True,
            message="Shipping latest squad artifacts to VM + Pages.",
        )
    if turn % 3 == 0:
        return ImprovementPlan(
            agent_id="jordan",
            channel="engineering",
            action="query",
            query="What is the highest-impact UX or API fix for Erebor right now?",
            message="Checking ACME memory for the next improvement priority.",
        )
    targets = [
        ("marco", "static/js/scene.js", "javascript", "Polish Three.js globe — nodes, arcs, damping."),
        ("priya", "static/css/shell.css", "css", "Refine obsidian shell spacing and mobile layout."),
        ("chen", "api/routes/intelligence.py", "python", "Harden OSS search fan-out and error handling."),
        ("marco", "static/js/app.js", "javascript", "Wire search results to globe selection + inspector."),
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
) -> ImprovementPlan:
    agent_ids = [a.id for a in DEMO_AGENTS]
    artifact_list = ", ".join(sorted(artifacts.keys())[:35]) or "(empty)"
    deploy_rule = (
        "- Deploy is ALLOWED when probes are green or after a code fix"
        if deploy_allowed
        else f"- Deploy is BLOCKED ({deploy_block_reason or 'cooldown/failures'}). "
        "NEVER set action=deploy or deploy=true. Edit code or run probes instead."
    )

    prompt = f"""{SKILL_CATALOG}

Turn #{turn}. Erebor squad is in continuous improvement mode — keep shipping until a human pauses.

Recent Slack:
{recent_thread[:1800]}

Runtime observations:
{observations[:5000]}

Artifacts in repo: {artifact_list}

Pick the next highest-impact action. Respond with JSON only:
{{
  "agent_id": one of {agent_ids},
  "channel": "general"|"engineering"|"design"|"product"|"deploy"|"ops",
  "action": "probe"|"edit"|"deploy"|"query"|"announce"|"triage",
  "message": "Slack message explaining what you did or will do",
  "file": "path/for/edit action or null",
  "lang": "css|javascript|html|python|markdown or null",
  "query": "question for acme_query or null",
  "skill": "which skill you used or null",
  "deploy": false
}}

Rules:
- Prefer edit/probe when VM API or receiver probes fail — do NOT redeploy the same broken artifact set
- If GitHub Pages is healthy but VM API is down, fix server.py/receiver code first; VM-only deploy later
- Jordan uses probe/query; Nina deploys only when allowed; Marco/Priya/Chen edit files
- Vera owns triage in #ops — one consolidated incident report, never repeat the same alert
- One concrete improvement per turn — no vague planning
{deploy_rule}
"""

    llm = get_llm_client()
    model = settings.demo_azure_deployment or None
    try:
        raw = await llm.generate(
            prompt,
            system="You are the Erebor squad coordinator. Output valid JSON only.",
            model=model,
            temperature=0.35,
            timeout=30.0,
            json_mode=True,
        )
        data = _parse_plan(raw)
        agent_id = data.get("agent_id", "marco")
        if agent_id not in AGENT_BY_ID:
            agent_id = "marco"
        return ImprovementPlan(
            agent_id=agent_id,
            channel=data.get("channel", "engineering"),
            action=data.get("action", "announce"),
            message=data.get("message", "Continuing Erebor improvements."),
            file=data.get("file"),
            lang=data.get("lang"),
            query=data.get("query"),
            skill=data.get("skill"),
            deploy=bool(data.get("deploy")),
        )
    except Exception:
        logger.exception("Improvement plan LLM failed — using heuristic")
        return _fallback_plan(
            turn=turn,
            observations=observations,
            artifacts=artifacts,
            deploy_allowed=deploy_allowed,
        )
