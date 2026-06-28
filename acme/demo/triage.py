"""Incident triage — dedupe spam and format Vera debug reports."""

from __future__ import annotations

import re
from typing import Any

from acme.demo.skills import SkillResult

_SPAM_PREFIXES = (
    "publish cooldown",
    "publish blocked",
    "redeploying",
    "github pages reachable",
    "fetched https://",
    "vm stack live",
    "shipping latest",
)

_DEDUP_AGENTS = frozenset({"nina", "sam", "jordan", "chen", "kai"})


def normalize_message(content: str) -> str:
    text = content.lower().strip()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\s+", " ", text)
    return text[:220]


def is_spam_duplicate(content: str, recent: list[str]) -> bool:
    norm = normalize_message(content)
    if not norm:
        return False
    if any(norm.startswith(p) for p in _SPAM_PREFIXES):
        return norm in recent
    return False


def should_dedup_agent(agent_id: str) -> bool:
    return agent_id in _DEDUP_AGENTS


def failure_signature(observations: str, skill_results: list[SkillResult]) -> str:
    fails = [r.skill for r in skill_results if not r.ok]
    if not fails:
        return "ok"
    return "|".join(sorted(set(fails)))


def format_triage_report(
    *,
    observations: str,
    skill_results: list[SkillResult],
    deploy_block_reason: str | None = None,
    signature: str | None = None,
) -> str:
    fails = [r for r in skill_results if not r.ok]
    lines = ["*Incident triage* — consolidated status (no repeat spam):"]
    if deploy_block_reason:
        lines.append(f"• Deploy gate: {deploy_block_reason}")
    if signature and signature != "ok":
        lines.append(f"• Active failure set: `{signature}`")
    for result in fails[:6]:
        lines.append(f"• `{result.skill}` — {result.summary[:120]}")
    if not fails and deploy_block_reason:
        lines.append("• Probes green; deploy blocked by policy/cooldown.")
    elif not fails:
        lines.append("• All runtime probes passed.")
    lines.append("Next: fix root cause once, then single deploy — not blind retries.")
    return "\n".join(lines)


def triage_detail(skill_results: list[SkillResult]) -> dict[str, Any]:
    return {
        "failing_skills": [r.skill for r in skill_results if not r.ok],
        "observations_preview": skill_results[0].summary if skill_results else "",
    }
